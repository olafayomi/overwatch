#!/usr/bin/env python

import networkx as nx
import sys
import re
import time
import inspect
import csv
import matplotlib.pyplot as plt
import matplotlib.mlab as mlab
import numpy
from networkx import path_graph, random_layout
import argparse
import logging
from collections import defaultdict
from multiprocessing import Process, Queue
from queue import Empty
from ctypes import cdll, byref, create_string_buffer

from pyospf import main as pyospf


class Network(object):
    def __init__(self, topology=None):
        self.log = logging.getLogger("Network")
        self.links = defaultdict(list)
        if topology is None:
            self.topology = {}
        else:
            self.topology = topology

    def reset(self):
        self.links = defaultdict(list)
        self.topology = {}

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

    def debug(self):

        self.log.info("TOPOLOGY:")
        for src in self.topology:
            self.log.info("    %s", src)
            for dst in self.topology[src]:
                self.log.info("        %s %s", dst, self.topology[src][dst])
        self.log.debug("TOPOLOGY LINKS:")
        for src in self.links:
            self.log.info("    %s", src)
            for dst in self.links[src]:
                self.log.info("        %s", dst)
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


def _read_local_topology(filename, network):
    with open(filename) as infile:
        reader = csv.DictReader(infile,
                 fieldnames=["source", "destination", "cost", "address"])
        for line in reader:
            if line["source"].startswith("#"):
                continue
            network.add_link(
                    line["source"],
                    line["destination"],
                    int(line["cost"]),
                    line["address"]
            )
            

def createGraph(links):
    topoGraph = nx.DiGraph()
    for src, dstlist in links.items():
        for dstvalue in dstlist:
            dst, cost, dst_addr = dstvalue
            topoGraph.add_edge(src, dst, cost=cost,
                               dest_addr=dst_addr)
    return topoGraph

def drawNetTopo(graph):
    plt.subplot(111)
    pos = nx.spring_layout(graph)
    nodes = nx.draw_networkx_nodes(graph, pos, with_labels=True)
    M = graph.number_of_edges()
    edge_colors = range(2, M + 2)
    edge_alphas = [(5 + i) / (M + 4) for i in range(M)]
    edges = nx.draw_networkx_edges(graph, pos, edge_color=edge_colors)
    nodeList = list(graph.nodes)
    labels = {}
    for node in nodeList:
        print("Node is %s" %node)
        if type(node) != str:
            lnode = str(node)
            labels[node] = lnode
        
    nx.draw_networkx_labels(graph, pos, labels, font_weight='bold')
    plt.savefig("NetTopo.png")



if __name__ == "__main__":
    argParser = argparse.ArgumentParser(
            description='Create a directed graph with the topology data',
            usage='%(prog)s [-I topology.data ]')
    argParser.add_argument('-I', dest='topodata', help='topology.csv file',
                           default=None)
    args = argParser.parse_args()

    if (args.topodata is None):
        print("CSV file for topology not supplied!!!\n")
        sys.exit(-1)

    network = Network()
    _read_local_topology(args.topodata, network)
    #network.update()
    topolinks = network.links

    #for src in topolinks: 
    #    print("%s %s" %(src,network.links[src]))
    topo = createGraph(topolinks)
    #for node in topo.nodes:
    #   print("Node: %s, type: %s" %(node,type(node)))
    paths =  nx.all_simple_paths(topo, source='uow', target='vuw')
    for path in paths:
        print(path)
    print("\n")
    unique_single_paths = set(tuple(path) for path in nx.all_simple_paths(topo, source='uow', target='vuw'))

    combined_single_paths = []
    for path in unique_single_paths: 
        pairs = [path[i: i + 2] for i in range(len(path) -1)]
        combined_single_paths.append([
            (pair, topo[pair[0]][pair[1]])
            for pair in pairs])

    shortest_path_len = min(map(len, combined_single_paths))
    shortest_path = min(combined_single_paths, key=len)
    segments = [] 
    for edge in shortest_path:
        nodes, attrs = edge
        segments.append(attrs['dest_addr'])
    print("Shortest path length is %s" % shortest_path_len)
    print("Shortest path is %s" % shortest_path)
    print("Segments to use is %s" % segments)
    segments.reverse()
    print("Reversed segments: %s" %segments)
    print("\n")
    for path in combined_single_paths:
        print(path)
        print("length of path is %s" %len(path))
        print("\n")


    
    for path  in combined_single_paths: 
        for edge in path:
            nodes, attributes = edge
            print(edge)
            print("Edge cost: %s" %attributes['cost'])
            print("Address to reach head node: %s" %attributes['dest_addr'])
            
        print("\n")
    #print(combined_single_paths)




    #path_edges = all_simple_edge_paths(topo, source='tait', target='uow')
    #for edge in path_edges:
    #    print(edge)
    #drawNetTopo(topo)
    #network.debug()

