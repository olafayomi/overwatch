#!/usr/bin/env python

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

from collections import defaultdict
from abc import abstractmethod

from RouteEntry import RouteEntry, DEFAULT_LOCAL_PREF
from PolicyObject import PolicyObject, ACCEPT
from Routing import BGPDefaultRouting

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
            "topology": self._process_topology_message,
            "update": self._process_table_update,
            "debug": self._process_debug_message,
            "status": self._process_status_message,

        })

        # routes that we are in the process of receiving from a table
        self.pending = {}
        # routes that we are currently exporting
        self.exported = set()
        # routes that were received and accepted from the peer
        self.received = {}
        # routes received from all the tables that we are involved with
        self.adj_ribs_in = {}


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
            return

        # XXX massage this to list of tuples because that's what old code wants
        # XXX removing this would save a ton of memory!
        # XXX what is this actually doing and why? going from dict of
        # prefix:routes to tuple prefix,route?
        export_routes = self.filter_export_routes(self.adj_ribs_in)

        # at this point we have all the routes that might be relevant to us
        # and we need to figure out which ones we actually want to advertise
        export_routes = self.routing.apply(export_routes)

        if len(export_routes) == 0:
            # XXX: IF ROUTES ARE NO LONGER EXPORTABLE TO THE PEER
            # WITHDRAW ALL ROUTES, IF ANY, BEFORE CLEARING THE EXPOTED
            # ROUTES.
            for prefix, route in self.exported:
                self._do_withdraw(prefix, route)

            self.exported.clear()
            return

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
        filtered_routes = defaultdict(list)
        # unpack the routes from different tables
        for table in export_routes.values():
            for prefix, routes in table.items():
                for route in routes:
                    # exclude duplicates - a route might arrive from many tables
                    if route not in filtered_routes[prefix]:
                        filtered_routes[prefix].append(route)

        # perform normal filtering using all attached filters, which will
        # generate us a copy of the routes, leaving the originals untouched
        filtered_routes = super(Peer,self).filter_export_routes(filtered_routes)

        # fix the nexthop value which will be pointing to a router
        # id rather than an address, and may not even be directly
        # adjacent to this peer
        if self.routing.topology:
            for prefix, routes in filtered_routes.items():
                for route in routes:
                    nexthop = self.routing.topology.get_next_hop(
                            self.address, route.nexthop)
                    if nexthop:
                        route.set_nexthop(nexthop)
        return filtered_routes

    def _get_filtered_routes(self):
        filtered_routes = []
        self.log.info("DIMEJI_PEER_DEBUG: self.received.values() is %s" % self.received.values())
        for route in self.received.values():
            # work on a copy of the routes so the original unmodified routes
            # can be run through filters again later if required
            filtered = self.filter_import_route(route, copy=True)
            if filtered is not None:
                # add the new route to the list to be announced
                filtered_routes.append(filtered)
        self.log.info("DIMEJI_PEER_DEBUG: filtered_routes is %s" % filtered_routes)
        return filtered_routes

    def _update_tables_with_routes(self):
        # run the received routes through filters and send to the tables
        message = (("update", {
                    "routes": self._get_filtered_routes(),
                    "from": self.name,
                    "asn": self.asn,
                    "address": self.address,
                    }))
        #self.log.info("DIMEJI_PEER_DEBUG _update_tables_with_routes message: %s" % str(message))
        for table in self.export_tables:
            self.log.info("DIMEJI_PEER_DEBUG _update_tables_with_routes message: %s" % str(message))
            table.mailbox.put(message)

    def _process_table_update(self, message):
        # XXX: check if we can export this prefix, otherwise skip checks
        imp_routes = {}
        for prefix in message["routes"]:
            if self._can_import_prefix(prefix):
                imp_routes[prefix] = message["routes"][prefix]

        self.log.info("DIMEJI_PEER_DEBUG _process_table_update message: %s" % message)
        # No routes can be imported, stop the update process
        if len(imp_routes) == 0:
            return None
        #self.log.info("DIMEJI_PEER_DEBUG _process_table_update message: %s" % message)
        # clobber the old routes from this table with the new lot
        self.adj_ribs_in[message["from"]] = imp_routes
        return self._do_export_routes

    # XXX topology messages are a pickled data structure wrapped in a protobuf
    # to make the transition easier. They should probably be made into proper
    # protobuf messages sometime.
    def _process_topology_message(self, message):
        self.log.debug("Topology update received by %s" % self.name)

        # update topology with the new one
        self.routing.set_topology(message)

        # re-evaluate what we are exporting based on the new topology
        if len(self.adj_ribs_in) > 0:
            return self._do_export_routes
        return None

    def _process_debug_message(self, message):
        self.log.debug(self)
        return None

    def _process_status_message(self, message):
        # some of our other peers have changed status, so our routing table
        # may not be as good as it was, but should still be announced. Update
        # the routes we send to our peer to reflect that we might be degraded.
        self.log.debug("%s told to change status: %s" % (self.name, message))
        self.degraded = message
        # XXX peers disappearing should cause routes to be withdrawn, updating
        # our tables and causing this peer to export... if we can be certain
        # this message arrives before the route update then we don't need to
        # do an export here
        return self._do_export_routes

    def _reload_import_filters(self):
        if len(self.received) == 0:
            return
        self._update_tables_with_routes()

    # BGP Connection changed state, tell the controller about it
    def _state_change(self, status):
        if self.active != status:
            self.active = status
            # Make sure we remove routes that have been received from this peer
            # so they don't linger around
            if self.active is False:
                self.received.clear()
                self._update_tables_with_routes()
            # tell the controller the new status of this peer
            self.log.debug("%s signalling controller new status: %s" %
                    (self.name, status))
            self.internal_command_queue.put(("status", {
                "peer": {
                    "address": self.address,
                    "asn": self.asn,
                },
                "status": status,
            }))

    def _reload_from_tables(self):
        message = (("reload", {
                    "from": self.name,
                    "asn": self.asn,
                    "address": self.address,
                    }))
        for table in self.import_tables:
            table.mailbox.put(message)

