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

import logging
import time

from PolicyObject import PolicyObject, ACCEPT
from RouteEntry import RouteEntry
import messages_pb2 as pb


# what about prefixes inside aggregates where the AS set needs to be modified
# every time? or withdrawing the final prefix inside the aggregate


class RouteTable(PolicyObject):
    def __init__(self,
            name, control_queue,
            default_import=ACCEPT,
            default_export=ACCEPT):

        PolicyObject.__init__(self, name, control_queue, default_import,
                default_export)

        self.log = logging.getLogger("RouteTable")

        self.routes = {}
        self.pending = {}
        self.export_peers = []
        self.update_source = set()
        self.actions.update({
            pb.Message.UPDATE: self._process_update_message,
            pb.Message.RELOAD: self._process_reload_message,
        })
        # XXX can peer and table process update be merged into policy object?
        # and use a label or something for peer/table if I care?
        self._add_histogram("table_process_update_duration")
        self._add_histogram("table_update_peer_duration")

    def __str__(self):
        return "RouteTable(%s, %d import filters %d export filters)" % (
                self.name, len(self.import_filter), len(self.export_filter))

    def __repr__(self):
        return self.__str__()

    def add_export_peer(self, peers):
        if not isinstance(peers, list):
            peers = [peers]
        self.export_peers.extend(peers)

    def _process_reload_message(self, message):
        # Try to find the peer object from its attributes
        peer = None
        for _peer in self.export_peers:
            if _peer.name == message.reload.source:
                peer = _peer
                break

        if peer:
            # If the peer exists re-send (reload) the table routes
            self._update_peer(peer)
        # TODO do we want to do this one instantly?
        return None

    def _process_update_message(self, message):
        with self.metrics["table_process_update_duration"].time():
            peer = message.update.source
            routes = []

            # create the temporary route storage if needed
            if peer not in self.pending:
                self.pending[peer] = []

            buf = bytearray(message.update.routes)
            mv = memoryview(buf)
            offset = 0

            while offset < len(buf):
                route, length = RouteEntry.create_from_buffer(mv[offset:])
                offset += length
                routes.append(route)

            self._try_import_routes(self.pending[peer], routes)

            # when done, flip the pending routes into the main route dictionary
            # and update all the peers with the new routes
            if message.update.done:
                # filter the routes as they come in rather than waiting to do
                # them all just before we send them. Don't need to copy them
                # as we'll just request them again if we need to rerun filters
                mark = time.time()
                self.routes[peer] = [x for routes in self.filter_export_routes(
                        self.pending[peer],copy=False).values() for x in routes]
                self.log.debug("%s took %fs to filter %d routes",
                        self.name, time.time() - mark, len(self.routes[peer]))
                # clear out the temporary storage
                self.pending[peer] = []
                # track this peer as a source of the most recent updates
                self.update_source.add(peer)
                # trigger an update message to the peers of this table
                return self._update_peers
            return None

    def _try_import_routes(self, table, routes):
        # run all the routes through the filter to see which we should keep
        for route in routes:
            filtered = self.filter_import_route(route, copy=False)
            if filtered is not None:
                # each peer should only give us one route per prefix
                table.append(filtered)

    def _update_peers(self):
        """
            Update all export peers of this table with the table routes
        """
        self.log.debug("%s sending routes to peers", self.name)
        mark = time.time()
        for peer in self.export_peers:
            # Send the update to every peer in our table that needs it
            if (len(self.update_source) > 1 or
                        peer.name not in self.update_source):
                self._update_peer(peer)
        self.log.debug("%s sent routes to all peers in %f", self.name,
                time.time() - mark)
        self.update_source.clear()

    # XXX what if we have withdrawn all our routes...
    def _update_peer(self, peer):
        """
            Filter and send routes to a specific peer from this table
        """
        with self.metrics["table_update_peer_duration"].time():
            mark = time.time()

            combined = []
            for source_peer, routes in self.routes.items():
                # exclude routes we received from this source
                if source_peer != peer.name:
                    for route in routes:
                        if (peer.asn not in route.as_path() and
                                (route.as_set() is None or
                                 peer.asn not in route.as_set())):
                            combined.append(route)

            # if the peers that feed this table have all withdrawn their routes
            # then we still need to send an empty update to alert the others
            if len(combined) == 0:
                message = self._create_update_message()
                peer.mailbox.put(message.SerializeToString())
                return

            buf = bytearray(1024 * 1024 * 100)
            mv = memoryview(buf)
            count = 0
            while count < len(combined):
                offset = 0
                total = min(len(combined), count + self.batchsize)
                for i in range(count, total):
                    length = combined[i].save_to_buffer(mv[offset:])
                    if length < 0:
                        break
                    offset += length
                    i += 1
                count += self.batchsize
                message = self._create_update_message(
                        bytes(buf[0:offset]), count >= len(combined))
                peer.mailbox.put(message.SerializeToString())

            self.log.info("Table %s sent %d routes to %s in %fs",
                    self.name, len(combined), peer.name, time.time() - mark)
