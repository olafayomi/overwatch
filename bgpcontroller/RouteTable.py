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
from collections import defaultdict

from PolicyObject import PolicyObject, ACCEPT

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
        self.export_peers = []
        self.update_source = None
        self.actions.update({
            "update": self._process_update_message,
            "reload": self._process_reload_message,
            "debug": self._process_debug_message,
        })

    def __str__(self):
        return "RouteTable(%s, %d import filters %d export filters)" % (
                self.name, len(self.import_filter), len(self.export_filter))

    def __repr__(self):
        return self.__str__()

    def add_export_peer(self, peers):
        if not isinstance(peers, list):
            peers = [peers]
        self.export_peers.extend(peers)

    def _process_debug_message(self, message):
        self.log.debug(self)
        return None

    def _process_reload_message(self, message):
        # Try to find the peer object from its attributes
        peer = None
        for _peer in self.export_peers:
            if _peer.name == message["from"]:
                peer = _peer
                break

        if peer:
            # If the peer exists re-send (reload) the table routes
            self._update_peer(peer)
        # TODO do we want to do this one instantly?
        return None

    def _process_update_message(self, message):
        #self.log.info("DIMEJI_ROUTETABLE_DEBUG _process_update_message is %s" % message)
        peer = message.get("from")
        # clear all the routes we received from this peer
        self.routes[peer] = []
        # update routes from this peer by running through the filters.
        if isinstance(message["routes"], list):
            # routes from a peer are just a list
            self._try_import_routes(self.routes[peer], message["routes"])
        elif isinstance(message["routes"], dict):
            # routes from a table are a dictionary of lists
            for routes in message["routes"].values():
                self._try_import_routes(self.routes[peer], routes)
        #self.log.info("DIMEJI_ROUTETABLE_DEBUG _process_update_message print all routes in table:\n")
        #for peer, routes in self.routes.items():
        #    self.log.info("DIMEJI_ROUTETABLE_ROUTES_XXXX Peer: %s, Route: %s" %(peer, routes))
        # update all the peers with the new routes we received, and flag
        # the peer as the source of the update so the table doesn't send
        # a pointless update back. If multiple peers are updated then all
        # peers will need updates. We save the source peer rather than
        # passing it as an argument because we don't know what will happen
        # between now and the update callback triggering
        self.update_source = peer if self.update_source is None else None
        return self._update_peers

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
        #self.log.info("DIMEJI_ROUTETABLE_DEBUG _update_peers for table :%s" % self.name)
        mark = time.time()
        for peer in self.export_peers:
            # Send the update to every peer in our table that needs it
            if self.update_source != peer.name:
                self._update_peer(peer, mark=mark)
        self.update_source = None

    # XXX what if we have withdrawn all our routes...
    def _update_peer(self, peer, mark=None):
        """
            Filter and send routes to a specific peer from this table
        """
        if mark is None:
            mark = time.time()

        # build a set of routes to send to a specific peer
        combined = defaultdict(list)
        for source_peer, routes in self.routes.items():
            # exclude routes we received from this source
            if source_peer != peer.name:
                for route in routes:
                    try:
                        # if a peer, exclude routes that traverse its ASN
                        if (peer.asn not in route.as_path() and
                                (route.as_set() is None or
                                 peer.asn not in route.as_set())):
                            combined[route.prefix].append(route)
                    except AttributeError:
                        # otherwise just add it to the list
                        combined[route.prefix].append(route)

        filtered_routes = self.filter_export_routes(combined)
        self.log.info("Table %s filtered routes for %s in %fs" % (
                self.name, peer.name, time.time() - mark))

        mark = time.time()
        peer.mailbox.put(("update", {
                    "from": self.name,
                    "routes": filtered_routes
                    }))
        self.log.info("Table %s sent %d routes to %s in %fs" % (
                self.name, len(filtered_routes), peer.name,
                time.time() - mark))
        del filtered_routes
        del combined
