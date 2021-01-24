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

import csv
import sys
import logging
from collections import defaultdict
from multiprocessing import Process, Queue
from queue import Empty
from ctypes import cdll, byref, create_string_buffer

from pyospf import main as pyospf
import networkx as nx


class Network(object):
    def __init__(self, topology=None):
        self.log = logging.getLogger("Network")
        self.links = defaultdict(list)
        self.graph = nx.DiGraph()
        if topology is None:
            self.topology = {}
        else:
            self.topology = topology

    def reset(self):
        self.links = defaultdict(list)
        self.topology = {}
        self.graph.clear()

    def update(self):
        # update our path costs
        try:
            self._all_pairs_shortest_path()
        except Exception:
            # XXX: If the topo links are invalid just reset the topo elements
            # We may not have complete information from our dynamic protocol
            # or static info may not have required dynamic topo links yet.

            # XXX: This assumes that even if we have info about parts of our
            # topology we will not advertise any prefixes. Is this the
            # behaviour we want? Should we advertise if we know a part of the
            # topology but not the entire picture.

            # XXX: CURRENTLY IF WE HAVE A LINK THAT IS ISOLATED (DOESN'T
            # CONNECT TO THE OTHER LINKS) OR WE HAVE NON CONNECTABLE LINKS,
            # WE WILL RESET OUR TOPOLOGY AND WITHDRAW ANY ADVERTISED PREFIXES.
            self.log.debug("Topology update failed, resetting (may be temp incomplete)")
            self.reset()

        # update graph
        try:
            self.createGraph(self.links)
        except Exception:
            self.log.debug("Failed to update network graph, resetting!!!!")
            self.reset()

    def add_link(self, source, destination, cost, address):
        self.links[source].append((destination, cost, address))

    def remove_link(self, source, destination, cost):
        if source not in self.links or destination not in self.links:
            self.log.warning("MISSING NODE")
            return
        try:
            self.links[source].remove((destination, cost))
        except ValueError:
            self.log.warning("MISSING LINK")

    def createGraph(self, links):
        self.graph.clear()
        for src, dstlist in links.items():
            for dstvalue in dstlist:
                dst, cost, dst_addr = dstvalue
                self.graph.add_edge(src, dst,  cost=cost,
                                    dest_addr=dst_addr)
        self.log.debug("TOPOLOGY GRAPH:")
        for edge in list(self.graph.edges):
            edge_data = self.graph.get_edge_data(edge[0], edge[1])
            cost = edge_data['cost']
            dst_addr = edge_data['dest_addr']
            self.log.debug("Node %s ------> Node %s, Cost: %s, Nexthop: %s",
                           edge[0], edge[1], cost, dst_addr)

    def _all_pairs_shortest_path(self):
        nexthop = {}
        nexthop_address = {}
        cost = {}

        # initialise minimum cost between nodes to infinity, with no nexthop
        for src in self.links:
            cost[src] = {}
            nexthop[src] = {}
            nexthop_address[src] = {}
            for dst in self.links:
                nexthop_address[src][dst] = None
                if src == dst:
                    cost[src][dst] = 0
                    nexthop[src][dst] = dst
                else:
                    cost[src][dst] = sys.maxsize
                    nexthop[src][dst] = None

        # set weights and nexthops for adjacent nodes
        for src in self.links:
            for dst, linkcost, address in self.links[src]:
                cost[src][dst] = linkcost
                nexthop[src][dst] = dst
                nexthop_address[src][dst] = address

        # run Floyd-Warshall to update costs and nexthop across all nodes
        for k in self.links:
            for i in self.links:
                for j in self.links:
                    if cost[i][j] > cost[i][k] + cost[k][j]:
                        cost[i][j] = cost[i][k] + cost[k][j]
                        nexthop[i][j] = nexthop[i][k]

        # build up a dictionary of (nexthop, cost) tuples to pass to Peers
        for src in nexthop.keys():
            if src not in self.topology:
                self.topology[src] = {}
            for dst in nexthop.keys():
                if src == dst:
                    continue
                hop = nexthop[src][dst]
                address = nexthop_address[src][hop]
                self.topology[src][dst] = (address, cost[src][dst])

        self.log.debug("TOPOLOGY:")
        for src in self.topology:
            self.log.debug("    %s", src)
            for dst in self.topology[src]:
                self.log.debug("        %s %s", dst, self.topology[src][dst])
        self.log.debug("TOPOLOGY LINKS:")
        for src in self.links:
            self.log.debug("    %s", src)
            for dst in self.links[src]:
                self.log.debug("        %s", dst)
        #self.log.debug("LINKS: %s" %self.links)

    def get_next_hop(self, src, dst):
        try:
            return self.topology[src][dst][0]
        except KeyError:
            return None

    def get_path_cost(self, src, dst):
        try:
            return self.topology[src][dst][1]
        except KeyError:
            return None

    def returnGraph(self):
        number_of_nodes = self.graph.number_of_nodes()
        list_of_nodes = list(self.graph.nodes())
        return number_of_nodes, list_of_nodes
        
    def get_segments_list(self, src, dst):
        unique_single_paths = set(tuple(path)
                                  for path in nx.all_simple_paths(
                                     self.graph, source=src, target=dst))
        combined_single_paths = []
        for path in unique_single_paths:
            pairs = [path[i: i + 2] for i in range(len(path) - 1)]
            combined_single_paths.append([
                (pair, self.graph[pair[0]][pair[1]])
                for pair in pairs])
        try:
            shortest_path = min(combined_single_paths, key=len)
        except ValueError:
            return None

        segments = []
        for edge in shortest_path:
            nodes, attrs = edge
            segments.append(attrs['dest_addr'])
        segments.reverse()
        return segments


class NetworkManager(Process):
    def __init__(self, topology_config=[{"static_file": "topology.csv"}]):
        Process.__init__(self, name="network")

        self.log = logging.getLogger("NetworkMan")

        self._network = Network()
        self._actions = {
            "build_topology": self._build_topo
        }
        self.peers = []
        self.mailbox = Queue()
        self.daemon = True

        # XXX: Please note that once we process the config file and
        # spawn the listeners and extract the static files the topology
        # config object will be deleted !
        self._topology_config = topology_config
        self._static_files = []

    def _build_topo(self, message):
        """
            Build or update the topology form a topology message. The expected
            topology format is as follows:

            {RouterID:
            [
                (Destination RID,
                 IP to destination,
                 cost),
                ...
            ],

            ...

            }
        """
        # Backup the old topology and clear the links and topo objects
        links = self._network.links
        topology = self._network.topology
        topoGraph = self._network.graph
        self._network.reset()

        # Re-load the static topology info
        self._load_static_topology()

        # Iterate through the links and add them
        for rid in message:
            links = message[rid]
            for link in links:
                peer_rid = link[0]
                ip = link[1]
                cost = link[2]

                self._network.add_link(
                    rid,
                    peer_rid,
                    cost,
                    ip
                )

        # Check if the new links are the same as before (need to recompute topo)
        if self._network.links == links:
            # Topo has not changed restore the old values
            self._network.topology = topology
            del links
            del topology
            del topoGraph
            self.log.debug("Links have not changed, keeping old topo")
        else:
            self.log.debug("Links have changed, recalculating topo")
            del links
            del topology
            del topoGraph

            # Recompute the topology, links are different
            self._network.update()
            self._update()

    def _spawn_dynamic_listeners(self):
        """
            Process the config file to spawn all dynamic topology processes
            protocols and extract the static files we will use to load static
            topo info from. This method will automatically start all the
            spawned dynamic topo listeners once created.
        """
        for topo in self._topology_config:
            if "protocol" in topo:
                proto = topo["protocol"]
                if proto == "ospf":
                    self.log.debug("Starting OSPF listener")
                    topo_listen = pyospf.Listener(self.mailbox, topo["config"])
                    topo_listen.daemon = True
                    topo_listen.start()
                else:
                    self.log.debug("Unknown protocol for dynamic topo %s",
                            proto)
            elif "static_file" in topo:
                self._static_files.append(topo["static_file"])

        del self._topology_config

    def start(self):
        """
            Override the default start method to initiate any dynamic topology
            objects and start the separate network process.
        """

        self._spawn_dynamic_listeners()
        super(NetworkManager, self).start()

    def run(self):
        libc = cdll.LoadLibrary("libc.so.6")
        buff = create_string_buffer(len("network"))
        buff.value = ("network").encode()
        libc.prctl(15, byref(buff), 0, 0, 0)

        # Load the static topology and build the initial network
        self._load_static_topology()
        self._network.update()
        self._update()

        while True:
            try:
                # XXX trying not to block forever so that the child can get
                # messages about the parent dying, but this doesn't work well
                msgtype, message = self.mailbox.get(block=True, timeout=1)
            except Empty:
                continue

            if msgtype in self._actions:
                self._actions[msgtype](message)
            else:
                self.log.warning("Ignoring unknown message type %s", msgtype)
            del message

    def _load_static_topology(self):
        """
            Load the static topology information from the static topo files.
        """
        for filename in self._static_files:
            self._read_local_topology(filename)

    def _read_local_topology(self, filename):
        """
            Iterate through a static topology CSV file and build up the
            topology links. No longer updates and builds the topology
            automatically, we can have more than one source of topo info!
        """
        with open(filename) as infile:
            reader = csv.DictReader(infile,
                    fieldnames=["source", "destination", "cost", "address"])
            for line in reader:
                if line["source"].startswith("#"):
                    continue
                self._network.add_link(
                    line["source"],
                    line["destination"],
                    int(line["cost"]),
                    line["address"]
                )

    def _update(self):
        # let all the peers know so they can update BGP to match new topology
        for peer in self.peers:
            peer.mailbox.put(("topology", self._network.topology))
            peer.mailbox.put(("topolinks", self._network.links))

    #def __str__(self):
        #return "\n".join([str(x) for x in self.nodes])
