# Copyright (c) 2020, WAND Network Research Group
#                     Department of Computer Science
#                     University of Waikato
#                     Hamilton
#                     New Zealand
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330,
# Boston,  MA 02111-1307  USA
#
# @Author : Brendon Jones (Original Disaggregated Router)
# @Author : Dimeji Fayomi

import pickle
import time
from collections import defaultdict
from abc import abstractmethod

from RouteEntry import RouteEntry, DEFAULT_LOCAL_PREF
from PolicyObject import PolicyObject, ACCEPT
from Routing import BGPDefaultRouting
import messages_pb2 as pb


class Peer(PolicyObject):
    def __init__(self, name, asn, address, control_queue,
            internal_command_queue,
            preference=DEFAULT_LOCAL_PREF,
            default_import=ACCEPT,
            default_export=ACCEPT):

        super(Peer, self).__init__(name, control_queue, default_import,
                default_export)

        # XXX: The self.log attribute is defined by the inheriting classes.
        # This will allow us to specify the correct name for each peer type
        # used, currently BGPPeers and SDNPeers.

        self.asn = asn
        self.address = address
        self.preference = preference
        self.internal_command_queue = internal_command_queue
        self.routing = BGPDefaultRouting(self.address)
        self.export_tables = []
        self.active = False
        self.degraded = 0

        # XXX: List of tables we are receive routes from (needed to
        # send reload message to correct tables)
        self.import_tables = []

        self.actions.update({
            pb.Message.TOPOLOGY: self._process_topology_message,
            pb.Message.UPDATE: self._process_table_update,
            pb.Message.STATUS: self._process_status_message,
        })

        # routes that we are in the process of receiving from a table
        self.pending = {}
        # routes that we are currently exporting
        self.exported = set()
        # routes that were received and accepted from the peer
        self.received = []
        # routes received from all the tables that we are involved with
        self.adj_ribs_in = {}

        # Peer metrics to track
        self._add_gauge("peer_prefix_received_current", 0)
        self._add_gauge("peer_prefix_accepted_current", 0)
        self._add_gauge("peer_prefix_exported_current", 0)
        self._add_gauge("peer_prefix_adj_ribs_in_current", 0)
        self._add_gauge("peer_state", 0)
        self._add_gauge("peer_state_last_change_timestamp", "now")
        self._add_gauge("peer_last_import_timestamp", -1)
        self._add_gauge("peer_last_export_timestamp", -1)
        self._add_gauge("peer_first_import_timestamp", -1)
        self._add_histogram("peer_process_bgp_update_duration")
        self._add_histogram("peer_process_table_update_duration")
        self._add_histogram("peer_update_tables_duration")

    def add_import_tables(self, tables):
        if not isinstance(tables, list):
            tables = [tables]
        self.import_tables.extend(tables)

    @abstractmethod
    def _do_announce(self, prefix, route):
        pass

    @abstractmethod
    def _do_withdraw(self, prefix, route):
        pass

    def _do_export_routes(self, refresh=False):
        # if the peer isn't connected then don't bother trying to export routes
        if self.active is False:
            self.log.debug("Peer %s is not connected, not exporting routes" %
                    self.name)
            return

        # if there is no topology then don't bother trying to export routes
        if self.routing.topology is None:
            self.log.debug("Peer %s is missing topology, not exporting routes" %
                    self.name)
            return

        if refresh:
            # This is a route refresh, announce all the routes that we are
            # currently exporting
            for (prefix, route) in self.exported:
                self._do_announce(prefix, route)
            self.metrics["peer_prefix_exported_current"].set(len(self.exported))
            self.metrics["peer_last_export_timestamp"].set_to_current_time()
            return

        # XXX massage this to list of tuples because that's what old code wants
        # XXX removing this would save a ton of memory!
        # XXX what is this actually doing and why? going from dict of
        # prefix:routes to tuple prefix,route?
        export_routes = self.filter_export_routes(self.adj_ribs_in)

        # at this point we have all the routes that might be relevant to us
        # and we need to figure out which ones we actually want to advertise
        export_routes = self.routing.apply(export_routes)

        full_routes = []
        for prefix, routes in export_routes.items():
            for route in routes:
                if self.degraded:
                    # add communities if we are degraded in some way
                    route.add_communities([(self.asn, self.degraded)])
                full_routes.append((prefix, route))
        full_routes = set(full_routes)
        del export_routes

        # withdraw all the routes that were advertised but no longer are
        for prefix, route in self.exported.difference(full_routes):
            self._do_withdraw(prefix, route)

        # announce all the routes that haven't been advertised before
        for prefix, route in full_routes.difference(self.exported):
            self._do_announce(prefix, route)

        # record the routes we last exported so we can check for changes
        self.exported = full_routes
        self.metrics["peer_prefix_exported_current"].set(len(self.exported))
        self.metrics["peer_last_export_timestamp"].set_to_current_time()

        self.log.info("Finished exporting routes to peer %s", self.name)

    @abstractmethod
    def _can_import_prefix(self, route):
        """
            Check if we can import a specific prefix, by default all prefixes
            are importable. This method should be overwritten in inheriting
            classes to implement this differently. i.e. BGP peers will do a
            negotiated AFI/SAFI check.
        """
        return True

    def filter_export_routes(self, export_routes):
        # XXX start the filter metric timer here rather than in PolicyObject?
        filtered_routes = defaultdict(list)
        mark = time.time()
        # unpack the routes from different tables
        flattened = [x for routes in export_routes.values() for x in routes]
        # exclude duplicates - a route might arrive from many tables
        # XXX removing duplicates is slow, at least 25 times slower than just
        # building the list in the first place
        flattened = set(flattened)
        self.log.debug("%s took %fs to flatten %d routes", self.name,
                time.time() - mark, len(flattened))

        # report number of unique prefixes before they get filtered
        self.metrics["peer_prefix_adj_ribs_in_current"].set(
                len(flattened))

        # perform normal filtering using all attached filters, which will
        # generate us a copy of the routes, leaving the originals untouched
        mark = time.time()
        filtered_routes = super(Peer, self).filter_export_routes(flattened)
        self.log.debug("%s took %fs to filter %d routes", self.name,
                time.time() - mark, len(filtered_routes))

        # fix the nexthop value which will be pointing to a router
        # id rather than an address, and may not even be directly
        # adjacent to this peer
        # XXX and only needs to be done if topology is dirty
        # XXX can we just get a full reload if the topology changes?
        if self.routing.topology:
            mark = time.time()
            for prefix, routes in filtered_routes.items():
                for route in routes:
                    nexthop = self.routing.topology.get_next_hop(
                            self.address, route.nexthop)
                    if nexthop:
                        route.set_nexthop(nexthop)
            self.log.debug("%s took %fs to fix %d nexthops",
                    self.name, time.time() - mark, len(filtered_routes))
        return filtered_routes

    def _update_tables_with_routes(self):
        with self.metrics["peer_update_tables_duration"].time():
            # if there are no routes received, send an empty update message
            # to show that they have all been withdrawn
            if len(self.received) == 0:
                message = self._create_update_message()
                message = message.SerializeToString()
                for table in self.export_tables:
                    self.log.debug("peer %s sending 0 routes to table %s",
                            self.name, table.name)
                    table.mailbox.put(message)
                return

            # for now we'll try a 100MB buffer, should be enough to hold a
            # few hundred thousand route entries, depending on aspath etc but
            # not so much that we will use up all the memory on the system
            buf = bytearray(1024 * 1024 * 100)
            mv = memoryview(buf)
            count = 0
            while count < len(self.received):
                offset = 0
                # add the smaller of the batchsize and the number remaining
                total = min(len(self.received), count + self.batchsize)
                for count in range(count, total):
                    length = self.received[count].save_to_buffer(mv[offset:])
                    # negative length means buffer ran out of space, send it
                    if length < 0:
                        break
                    offset += length
                    count += 1

                # send the message containing this batch of routes
                message = self._create_update_message(
                        bytes(buf[0:offset]), count >= len(self.received))
                message = message.SerializeToString()
                for table in self.export_tables:
                    self.log.debug("peer %s sending %d routes to table %s",
                            self.name, count, table.name)
                    table.mailbox.put(message)

    def _process_table_update(self, message):
        with self.metrics["peer_process_table_update_duration"].time():
            table = message.update.source
            if table not in self.pending:
                self.pending[table] = []

            # create a memory view around the route buffer so we can index it
            # easily without having to create copies of data
            buf = bytearray(message.update.routes)
            mv = memoryview(buf)
            offset = 0

            # read all the routes from the message and temporarily store them
            # till the full update has arrived
            while offset < len(buf):
                route, length = RouteEntry.create_from_buffer(mv[offset:])
                offset += length
                if self._can_import_prefix(route.prefix):
                    self.pending[table].append(route)

            # when done, flip the pending routes into the available routes and
            # trigger an update
            if message.update.done:
                self.adj_ribs_in[table] = self.pending[table]
                self.pending[table] = []
                return self._do_export_routes

            # otherwise wait till the rest of the update arrives
            return None

    # XXX topology messages are a pickled data structure wrapped in a protobuf
    # to make the transition easier. They should probably be made into proper
    # protobuf messages sometime.
    def _process_topology_message(self, message):
        self.log.debug("Topology update received by %s" % self.name)

        # update topology with the new one
        self.routing.set_topology(pickle.loads(message.topology.network))

        # re-evaluate what we are exporting based on the new topology
        if len(self.adj_ribs_in) > 0:
            return self._do_export_routes
        return None

    def _process_status_message(self, message):
        # some of our other peers have changed status, so our routing table
        # may not be as good as it was, but should still be announced. Update
        # the routes we send to our peer to reflect that we might be degraded.
        self.log.debug("%s told to change status: %s", self.name,
                message.status.status)
        self.degraded = message.status.status
        # if we haven't exported any routes yet, then we don't need to update
        # the communities on those routes
        if len(self.exported) > 0:
            # XXX peers disappearing should cause routes to be withdrawn,
            # updating our tables and causing this peer to export... if we
            # can be certain this message arrives before the route update then
            # we don't need to do an export here
            return self._do_export_routes
        return None

    def _reload_import_filters(self):
        if len(self.received) == 0:
            return
        self._update_tables_with_routes()

    # BGP Connection changed state, tell the controller about it
    def _state_change(self, status):
        if self.active != status:
            self.metrics["peer_state"].set(status)
            self.metrics["peer_state_last_change_timestamp"].set_to_current_time()
            self.active = status
            # tell the controller the new status of this peer
            self.log.debug("%s signalling controller new status: %s" %
                    (self.name, status))

            message = pb.Message()
            message.type = pb.Message.STATUS
            message.status.address = self.address
            message.status.asn = self.asn
            message.status.status = status
            self.internal_command_queue.put(message.SerializeToString())

    def _reload_from_tables(self):
        message = pb.Message()
        message.type = pb.Message.RELOAD
        message.reload.source = self.name
        message.reload.asn = self.asn
        message.reload.address = self.address
        for table in self.import_tables:
            table.mailbox.put(message.SerializeToString())
