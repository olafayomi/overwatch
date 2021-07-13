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
import copy
import grpc
import json
import srv6_explicit_path_pb2_grpc
import srv6_explicit_path_pb2
import time
class Peer(PolicyObject):
    def __init__(self, name, asn, address, control_queue,
            internal_command_queue,
            preference=DEFAULT_LOCAL_PREF,
            default_import=ACCEPT,
            default_export=ACCEPT,
            par=False):

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
        self.enable_PAR = par
        self.PAR_prefixes = []
        self.PARModules = []
        self.interfaces = []

        # XXX: List of tables we are receive routes from (needed to
        # send reload message to correct tables)
        self.import_tables = []

        self.actions.update({
            "topology": self._process_topology_message,
            "topolinks": self._process_topology_links_message,
            "update": self._process_table_update,
            "debug": self._process_debug_message,
            "status": self._process_status_message,
            "par": self._process_par_update,
        })

        # routes that we are in the process of receiving from a table
        self.pending = {}
        # routes that we are currently exporting
        self.exported = set()
        # routes that were received and accepted from the peer
        # that this process represents.
        self.received = {}
        # routes received from all the tables that we are involved with
        self.adj_ribs_in = {}
        # routes received from all the tables that we are involved with 
        # before processing for PAR routes 
        self.pre_adj_ribs_in = {}

        # PAR routes
        self.par_ribs_in = {}


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
        #self.log.info("DIMEJI_DEBUG_PEER _do_export_routes printing self.adj_ribs_in for %s" %self.name)
        #for table, routes in self.adj_ribs_in.items():
        #    self.log.info("DIMEJI_DEBUG_PEER_YYYYYYYYYY _do_export_routes TABLE: %s, ROUTES: %s" %(table, routes))

        # XXX: Enabling PAR for specific prefixes 20201120
        #if self.enable_PAR is True:
        #    par_table_name = []
        #    for module in self.PARModules:
        #        par_table_name.append(module.name)
        #    self.pre_adj_ribs_in = copy.deepcopy(self.adj_ribs_in)
        #    for table, routes in self.adj_ribs_in.items():
        #        if table not in par_table_name:
        #            for prefix in self.PAR_prefixes:
        #                if prefix in routes:
        #                    #self.log.info("DIMEJI_DEBUG_PEER_JDHGDDH _do_export_routes  %s   Popping %s routes from other tables" %(self.name, str(prefix)))
        #                    routes.pop(prefix)
            
        # XXX massage this to list of tuples because that's what old code wants
        # XXX removing this would save a ton of memory!
        # XXX what is this actually doing and why? going from dict of
        # prefix:routes to tuple prefix,route?

        
        # XXX: Remove this because now we hide paths. 20201120

        #if self.enable_PAR is True:
        #    adj_export_routes = self.filter_export_routes(self.adj_ribs_in)
        #    par_export_routes = self.filter_export_routes(self.par_ribs_in)
        #    export_routes = {**par_export_routes, **adj_export_routes}
        #else:
        export_routes = self.filter_export_routes(self.adj_ribs_in)

        # at this point we have all the routes that might be relevant to us
        # and we need to figure out which ones we actually want to advertise
        export_routes = self.routing.apply(export_routes)

        if len(export_routes) == 0:
            # XXX: IF ROUTES ARE NO LONGER EXPORTABLE TO THE PEER
            # WITHDRAW ALL ROUTES, IF ANY, BEFORE CLEARING THE EXPOTED
            # ROUTES.
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
            edges = list(self.routing.topology.graph.edges)
            dest_node = ""
            for edge in edges:
                edge_data = self.routing.topology.graph.get_edge_data(edge[0], edge[1])
                if route.nexthop == edge_data['dest_addr']:
                    dest_node = edge[1]
                    break

            if dest_node:
                segments = self.routing.topology.get_segments_list(self.name, dest_node)
                self.log.info("TESTING FOR FULL SRV6 FOR ALL ROUTES XXXXXXX: SEGMENT %s RETURNED to node %s for _process_par_update in PEER %s", segments, dest_node, self.name)
                datapath = [
                            {
                              "paths": [
                                {
                                  "device": self.interfaces[0],
                                  "destination": str(prefix),
                                  "encapmode": "encap",
                                  "segments": segments,
                                }
                              ]
                            }
                           ]
                self.internal_command_queue.put(("steer", {
                    "path": datapath[0]["paths"][0],
                    "peer": {
                              "address": self.address,
                              "asn": self.asn,
                            },
                    "action": "Remove"
                }))

            # XXX: I need to fix this... Routes that are still valid should not be removed
            #      from the PAR module list
            # XXX:     Could be removed 20201120
            #if prefix in self.PAR_prefixes:
            #    self.log.info("DIMEJI_DEBUG_PEER _do_export_routes length of pre_adj_ribs_in is %s\n\n\n" %len(self.pre_adj_ribs_in))
            #    rib_len = len(self.pre_adj_ribs_in)
            #    del_route = []
            #    count = 0
            #    for table, routes in self.pre_adj_ribs_in.items():
            #        if prefix not in routes:
            #            rib_len -= 1
            #            continue

            #        if route not in routes[prefix]:
            #            count += 1
            #            del_route.append(count)
            #    if rib_len != len(del_route):
            #        message = (("remove", {
            #                    "route": route,
            #                    "prefix": prefix,
            #                    "from": self.name
            #                  }))
            #        for parmodule in self.PARModules:
            #            self.log.debug("PEER WEIRDNESS DEBUG PAR route delete XXXX Peer %s removing route: %s in _do_export_routes\n\n" %(self.name, route))
            #            parmodule.mailbox.put(message)
        
        # announce all the routes that haven't been advertised before
        for prefix, route in full_routes.difference(self.exported):
            self._do_announce(prefix, route)
            self.log.info("I WANT TO TEST SOMETHING SEE PREFIX: %s, SEE ROUTE: %s", prefix, route)
            self.log.info("AFTER WHICH NEXTHOP is %s", route.nexthop)
            edges = list(self.routing.topology.graph.edges)
            dest_node = ""
            for edge in edges:
                edge_data = self.routing.topology.graph.get_edge_data(edge[0], edge[1])
                if route.nexthop == edge_data['dest_addr']:
                    dest_node = edge[1]
                    break

            if dest_node:
                segments = self.routing.topology.get_segments_list(self.name, dest_node)
                self.log.info("TESTING FOR FULL SRV6 FOR ALL ROUTES XXXXXXX: SEGMENT %s RETURNED to node %s for _process_par_update in PEER %s", segments, dest_node, self.name)
                datapath = [
                            {
                              "paths": [
                                {
                                  "device": self.interfaces[0],
                                  "destination": str(prefix),
                                  "encapmode": "encap",
                                  "segments": segments,
                                }
                              ]
                            }
                           ]
                self.internal_command_queue.put(("steer", {
                    "path": datapath[0]["paths"][0],
                    "peer": {
                              "address": self.address,
                              "asn": self.asn,
                            },
                    "action": "Replace"
                }))
            
            ### XXX: Disable adding routes to PAR modules
            ### XXX: Done 20201119
            #if prefix in self.PAR_prefixes:
            #    addroute = { prefix: [route] }
            #    message = (("add", { "routes": addroute,
            #                         "from": self.name}))
            #    for parmodule in self.PARModules:
            #        self.log.debug("PEER DIMEJI DEBUG WEIRDNESS XXXXX _do_export peer %s adding routes to PAR" %(self.name))
            #        parmodule.mailbox.put(message)

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

    def _do_export_pa_routes(self, refresh=False):
        pass

    def filter_export_routes(self, export_routes):
        filtered_routes = defaultdict(list)
        # unpack the routes from different tables
        for table in export_routes.values():
            for prefix, routes in table.items():
                #self.log.info("DIMEJI_DEBUG_PEER filter_export_routes printing routes in export_routes: %s and length is %s " % (routes, len(routes)))
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
        #self.log.info("DIMEJI_PEER_DEBUG: self.received.values() is %s" % self.received.values())
        for route in self.received.values():
            # work on a copy of the routes so the original unmodified routes
            # can be run through filters again later if required
            filtered = self.filter_import_route(route, copy=True)
            if filtered is not None:
                # add the new route to the list to be announced
                filtered_routes.append(filtered)
        #self.log.info("DIMEJI_PEER_DEBUG: filtered_routes is %s" % filtered_routes)
        return filtered_routes

    def _update_tables_with_routes(self):
        # run the received routes through filters and send to the tables
        message = (("update", {
                    "routes": self._get_filtered_routes(),
                    "from": self.name,
                    "asn": self.asn,
                    "address": self.address,
                    }))
        ### XXX: Added on 20201119
        ### XXX: Testing pushing routes directly to PARModule
        par_msg = (("add", {
                    "routes": self._get_filtered_routes(),
                    "from": self.name
                    }))

        #self.log.info("DIMEJI_PEER_DEBUG _update_tables_with_routes message: %s" % str(message))
        for table in self.export_tables:
            #self.log.info("DIMEJI_PEER_DEBUG _update_tables_with_routes message: %s" % str(message))
            table.mailbox.put(message)
        
        ### XXX: Added on 20201119
        ### XXX: Testing pushing routes directly to PARModule
        for parmodule in self.PARModules:
            self.log.debug("PEER DIMEJI WEIRDNESS DEBUG: Peer %s is adding route to parmodule in _update_tables_with_routes " %(self.name))
            parmodule.mailbox.put(par_msg)
                   
    def _process_table_update(self, message):
        # XXX: check if we can export this prefix, otherwise skip checks
        imp_routes = {}
        for prefix in message["routes"]:
            #self.log.info("DIMEJI_DEBUG_PEER _process_table_update: prefix : %s is type %s" % (prefix,type(prefix)))

            if self._can_import_prefix(prefix):
                imp_routes[prefix] = message["routes"][prefix]

        #self.log.info("DIMEJI_PEER_DEBUG _process_table_update message: %s" % message)
        # No routes can be imported, stop the update process
        if len(imp_routes) == 0:
            return None
        #self.log.info("DIMEJI_PEER_DEBUG _process_table_update message: %s" % message)
        # clobber the old routes from this table with the new lot
        self.adj_ribs_in[message["from"]] = imp_routes
        ### XXX: Disabling adding of routes to PAR module here
        ### XXX: Done 20201119
        #message = (("add", {
        #             "routes": imp_routes,
        #             "from": self.name
        #             }))
        #for parmodule in self.PARModules:
        #    self.log.debug("PEER DIMEJI WEIRDNESS DEBUG: Peer %s is adding route to parmodule in _process_table_update " %(self.name))
        #    parmodule.mailbox.put(message)

        if self.enable_PAR is True:
            #self.log.info("DIMEJI_DEBUG_PEER_YYSYDYDSYSYS _process_table_update requesting par-update peer: %s" %self.name)
            for module in self.PARModules:
                #self.log.info("DIMEJI_DEBUG_PEER_DYDGDSKJHDKHJDDD _do_export_routes      %s          Sending message to PAR Module: %s" %(self.name, module.name))
                #if module.name not in self.adj_ribs_in:
                #    self.adj_ribs_in[module.name] = {}
                message = (("get", {
                            "from": self.address,
                            "routes": self.adj_ribs_in,
                          }))
                module.mailbox.put(message)
                #self.log.info("DIMEJI_DEBUG_PEER_DYDGDSKJHDKHJDDD _process_table_update      %s          Sent message to PAR Module: %s" %(self.name, module.name))
                
            self.pre_adj_ribs_in = copy.deepcopy(self.adj_ribs_in)
        return self._do_export_routes

    def _process_par_update(self, message):
        # XXX: check if we can export this prefix, otherwise skip checks
        imp_routes = {}
        for prefix in message["routes"]: 
            self.log.info("DIMEJI_DEBUG_PEER _process_par_update: prefix : %s is type %s" % (prefix,type(prefix)))
            #stuff = message["routes"][prefix]
            #self.log.info("DIMEJI_DEBUG_PEER XXXXXXXXXXXXXXXYYYYYYYYYYYYYYYYYYYYYYYY _process_par_update: routeprefix is %s and type is: %s\n\n\n" %(stuff, type(stuff)))
            if len(message["routes"][prefix]) != 1:
                return None
            route, node = message["routes"][prefix][0]
            self.log.info("DIMEJI_DEBUG_PEER XXXXXXXXXXXXXXXXXYYYYYY _process_par_update IN PEER %s: %s and route %s\n\n\n" %(self.name,node, route))
            
            if self._can_import_prefix(prefix):
                imp_routes[prefix] = [route]
                #message["routes"][prefix]

        if len(imp_routes) == 0:
            return None
        
        if node == self.name:
            self.log.info("DIMEJI_DEBUG_PEER XDNXKASHDNCSHDHGSKDKSCBSBSG _process_par_update: node is the same\n\n\n")
            return None

       
        #self.log.info("DIMEJI_PEER_DEBUG _process_par_update message: %s" % message)
        self.par_ribs_in[message["type"]] = imp_routes
        #### Segment routing experiments
        segments = self.routing.topology.get_segments_list(self.name, node)

        #no_of_nodes, list_nodes = self.routing.topology.returnGraph()
        #self.log.info("DIMEJI_DEBUG_PEER XVSGDGSDSSYXNXNXFDF _process_par_update: number of nodes from graph is %s and list of nodes in graph is %s", no_of_nodes, list_nodes)

        if segments is None:
            self.log.info("DIMEJI_DEBUG_PEER No segments returned from network _process_par_update!!!")
            return None
        else:
            self.log.info("DIMEJI_DEBUG_PEER: SEGMENT %s RETURNED to node %s for _process_par_update in PEER %s", segments, node, self.name)

        if len(imp_routes) > 1:
            return None
        # XXX: Set routing table for PAR in LINUX to 201
        rtable = 201
        for prefix, routes in imp_routes.items():
            for route in routes:
                nexthop = route.nexthop
                self.log.info("DIMEJI_PEER_DEBUG _process_par_update NEXTHOP value in route: %s" % nexthop)
            if len(routes) > 1:
                return None
            datapath = [
                        {
                          "paths": [
                            {
                               #"device": "as3r2-eth1",
                               "device": self.interfaces[0],
                               "destination": str(prefix),
                               "encapmode": "encap",
                               "segments": segments,
                               "table": rtable
                            }
                          ]
                        }
                       ]
        self.internal_command_queue.put(("steer", {
            "path": datapath[0]["paths"][0],
            "peer": {
                      "address": self.address,
                      "asn": self.asn,
                    },
            "action": "Replace"
        }))
        return
        #return self._do_export_routes

    # XXX topology messages are a pickled data structure wrapped in a protobuf
    # to make the transition easier. They should probably be made into proper
    # protobuf messages sometime.
    def _process_topology_message(self, message):
        self.log.debug("Topology update received by %s" % self.name)

        # update topology with the new one
        self.routing.set_topology(message)

        # re-evaluate what we are exporting based on the new topology
        # XXX Todo: re-evaluate PAR routes too based on new topology.
        if len(self.adj_ribs_in) > 0:
            return self._do_export_routes
        return None

    def _process_topology_links_message(self, message):
        self.log.debug("Topology links update received by %s" % self.name)

        # update topology with new links
        self.routing.topology.createGraph(message)

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
                #for prefix, route in self.exported:
                #    self._do_withdraw(prefix, route)
                # Check if this makes the withdrawal of routes any faster!!!
                self.exported.clear()
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

