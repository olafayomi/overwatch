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

import csv
import sys
from multiprocessing import Queue
from threading import Thread
from argparse import ArgumentParser
import os
import logging

import BGPConnection
import ControlConnection
import Network
from RouteEntry import RouteEntry, ORIGIN_IGP
from ConfigurationFactory import ConfigFactory
from beeprint import pp

class Controller(object):
    def __init__(self, conf_file):
        self.log = logging.getLogger("Controller")
        self.internal_command_queue = Queue()
        self.outgoing_exabgp_queue = Queue()
        self.outgoing_control_queue = Queue()

        # Try to load the config file
        try:
            self.conf = ConfigFactory(self.internal_command_queue,
                    self.outgoing_exabgp_queue, self.outgoing_control_queue,
                    conf_file)
        except Exception:
            # If the file is invalid log an error and kill the app
            self.log.critical(
                    "Critical error occured while processing config file %s" %
                    conf_file)
            self.log.exception("--- STACK TRACE ---")
            exit(0)

        # Show debuging info from the configuration factory
        self.conf.debug()

        self.network = Network.NetworkManager(
                topology_config=self.conf.local_topology)
        self.asn = self.conf.asn
        self.peers = self.conf.peers
        self.tables = self.conf.tables
        self.network.peers = self.peers

        # all peers start down
        self.status = {}
        for peer in self.peers:
            self.status[(peer.address, peer.asn)] = False

        # listen for commands
        self.control_connection = Thread(
                target=ControlConnection.ControlConnection,
                name="Control thread",
                args=(self.outgoing_control_queue, self.internal_command_queue))
        self.control_connection.daemon = True

        # listen to exabgp messages
        self.bgp_connection = Thread(target=BGPConnection.BGPConnection,
                name="BGP thread",
                args=(self.outgoing_exabgp_queue, self.internal_command_queue))
        self.bgp_connection.daemon = True

    def read_local_routes(self, filename):
        if not os.path.isfile(filename):
            self.log.warning("Internal routes file %s dosen't exist" % filename)
            self.log.warning("No internal routes could be imported")
            return

        routes = []
        with open(filename) as infile:
            reader = csv.DictReader(infile, fieldnames=["node", "prefix"])
            for line in reader:
                if line["node"].startswith("#"):
                    continue
                try:
                    route = RouteEntry(ORIGIN_IGP, self.asn,
                            line["prefix"], line["node"])
                    routes.append(route)
                except IndexError as e:
                    self.log.critical("Poorly formed line in %s: %s" %
                            (filename, line))
                    sys.exit(1)

        # XXX should we limit which table routes go into? or rely on filters?
        # TODO use a better name for "from" that won't clash with table names?
        for table in self.tables:
            table.mailbox.put(("update", {
                "routes": routes,
                "from": "local",
                "asn": self.asn,
                "address": None,
                }))

    def run(self):
        self.log.debug("Running controller...")

        self.log.info("Starting local network manager")
        self.network.start()

        self.log.info("Starting peers")
        for peer in self.peers:
            self.log.debug("Starting Peer %s" % peer.name)
            peer.daemon = True
            peer.start()

        self.log.info("Starting routing tables")
        for table in self.tables:
            self.log.debug("Starting RouteTable %s" % table.name)
            table.daemon = True
            table.start()

        # read local route information, for now this won't change
        self.read_local_routes(self.conf.local_routes)

        self.log.info("Starting listener for ExaBGP messages")
        self.bgp_connection.start()

        self.log.info("Starting listener for command messages")
        self.control_connection.start()

        while True:
            msgtype, command = self.internal_command_queue.get()
            self.log.debug("DIMEJI Received message type %s  on internal_command_queue %s" %(msgtype,command))
            if msgtype == "bgp":
                # got a BGP message, pass it off to the appropriate peer process
                self.process_bgp_message(command)
            elif msgtype == "control":
                self.process_control_message(command)
            elif msgtype == "status":
                # update our internal peer status dictionary
                self.process_status_message(command)
            else:
                self.log.warning("Ignoring unkown message type %s " % msgtype)
	    

    def process_bgp_message(self, message):
        peer_as = int(message["neighbor"]["asn"]["peer"])
        peer_address = message["neighbor"]["address"]["peer"]
        peer = self._get_peer(peer_as, peer_address)
        if peer is None:
            self.log.warning("Ignoring message from unknown peer")
            return
        peer.mailbox.put(("bgp", message))

    def process_control_message(self, message):
        if "peer" in message:
            peer_asn = message["peer"]["asn"]
            peer_address = message["peer"]["address"]
            target = self._get_peer(peer_asn, peer_address)
        elif "table" in message:
            target = self._get_table(message["table"]["name"])
        else:
            target = None

        if target is None:
            self.log.warning("Ignoring message for unknown target")
            return

        if "action" in message:
            target.mailbox.put(
                    (message["action"], message.get("arguments", None))
            )

    def process_status_message(self, message):
        # peer status changed, update what we know about them
        peer = (message["peer"]["address"], message["peer"]["asn"])
        assert(peer in self.status)

        self.log.debug("controller status message: %s / %s" %
                (message["peer"]["asn"], message["status"]))

        # no change, ignore
        if self.status[peer] == message["status"]:
            return

        # calculate how many peers we are missing now
        self.status[peer] = message["status"]
        degraded = len([x for x in self.status.values() if x is False])

        # tell our peers that they may no longer have a full view of the routes
        for peer in self.peers:
            peer.mailbox.put(("status", degraded))

    def _get_peer(self, asn, address):
        return next((x for x in self.peers
                    if x.asn == asn and x.address == address), None)

    def _get_table(self, name):
        return next((x for x in self.tables if x.name == name), None)

if __name__ == "__main__":
    # Parse the arguments
    parser = ArgumentParser("Route Dissagregator")
    parser.add_argument("conf_file", metavar="config_file", type=str, help=
        "Path to the configuration file")
    parser.add_argument("--loglevel", default="DEBUG", type=str, help=
        "Set level of output (CRITICAL/ERROR/WARNING/INFO/DEBUG/NOTSET)")
    args = parser.parse_args()

    # Process the log level argument string to a logging value
    LOG_LEVEL = logging.DEBUG
    if args.loglevel.lower() == "critical":
        LOG_LEVEL = logging.CRITICAL
    elif args.loglevel.lower() == "error":
        LOG_LEVEL = logging.ERROR
    elif args.loglevel.lower() == "warning":
        LOG_LEVEL = logging.WARNING
    elif args.loglevel.lower() == "info":
        LOG_LEVEL = logging.INFO
    elif args.loglevel.lower() == "debug":
        LOG_LEVEL = logging.DEBUG
    elif args.loglevel.lower() == "notset":
        LOG_LEVEL = logging.NOTSET

    # Initiate the logging module for the execution
    logging.basicConfig(level=LOG_LEVEL,
            format="%(levelname).1s | %(name)-10s | %(message)s")

    # Initiate the controller
    controller = Controller(args.conf_file)
    controller.run()

