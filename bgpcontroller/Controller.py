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
from threading import Thread
from argparse import ArgumentParser
import os
import logging
import json

import BGPConnection
import ControlConnection
import Network
from RouteEntry import RouteEntry, ORIGIN_IGP
from ConfigurationFactory import ConfigFactory
from Metrics import PrometheusClient
import multiprocessing36 as mp36
from ForkingPicklerNoOp import PickleNoOpReducer
import messages_pb2 as pb

class Controller(object):
    def __init__(self, conf_file):
        # set multiprocessing queue to use a custom noop pickling function
        ctx = mp36.get_context()
        ctx.reducer = PickleNoOpReducer()

        self.log = logging.getLogger("Controller")
        self.internal_command_queue = mp36.Queue()
        self.outgoing_exabgp_queue = mp36.Queue()
        self.outgoing_control_queue = mp36.Queue()

        # Try to load the config file
        try:
            self.conf = ConfigFactory(self.internal_command_queue,
                    self.outgoing_exabgp_queue, self.outgoing_control_queue,
                    conf_file)
        except Exception:
            # If the file is invalid log an error and kill the app
            self.log.critical(
                    "Critical error occurred while processing config file %s",
                    conf_file)
            self.log.exception("--- STACK TRACE ---")
            exit(0)

        # Show debugging info from the configuration factory
        self.conf.debug()

        # TODO allow configuration of location, or if we even do metrics
        self.metrics = PrometheusClient()

        self.network = Network.NetworkManager(
                topology_config=self.conf.local_topology)
        self.asn = self.conf.asn
        self.peers = self.conf.peers
        self.tables = self.conf.tables
        self.network.peers = self.peers
        self.batchsize = 500000

        # all peers start down
        self.status = {}
        for peer in self.peers:
            self.status[(peer.address, peer.asn)] = False

        # listen for commands
        #self.control_connection = Thread(
        #        target=ControlConnection.ControlConnection,
        #        name="Control thread",
        #        args=(self.outgoing_control_queue, self.internal_command_queue))
        #self.control_connection.daemon = True

        # listen to exabgp messages
        self.bgp_connection = Thread(target=BGPConnection.BGPConnection,
                name="BGP thread",
                args=(self.outgoing_exabgp_queue, self.internal_command_queue))
        self.bgp_connection.daemon = True

    def read_local_routes(self, filename):
        if not os.path.isfile(filename):
            self.log.warning("Internal routes file %s doesn't exist", filename)
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
                    self.log.critical("Poorly formed line in %s: %s",
                            filename, line)
                    sys.exit(1)

        # XXX should we limit which table routes go into? or rely on filters?
        # TODO use a better name for "from" that won't clash with table names?
        buf = bytearray(1024 * 1024 * 100)
        mv = memoryview(buf)
        count = 0
        while count < len(routes):
            offset = 0
            # add the smaller of the batchsize and the number remaining
            total = min(len(routes), count + self.batchsize)
            for count in range(count, total):
                length = routes[count].save_to_buffer(mv[offset:])
                # negative length means buffer ran out of space, send it
                if length < 0:
                    break
                offset += length
                count += 1

            # send the message containing this batch of routes
            message = pb.Message()
            message.type = pb.Message.UPDATE
            message.update.source = "local"
            message.update.asn = self.asn
            message.update.address = ""
            message.update.routes = bytes(buf[0:offset])
            message.update.done = True
            message = message.SerializeToString()

            for table in self.tables:
                table.mailbox.put(message)

    def run(self):
        self.log.debug("Running controller...")

        self.log.info("Starting metrics endpoint")
        self.metrics.start()

        self.log.info("Starting local network manager")
        self.network.start()

        self.log.info("Starting peers")
        for peer in self.peers:
            self.log.debug("Starting Peer %s", peer.name)
            peer.daemon = True
            peer.start()

        self.log.info("Starting routing tables")
        for table in self.tables:
            self.log.debug("Starting RouteTable %s", table.name)
            table.daemon = True
            table.start()

        # read local route information, for now this won't change
        self.read_local_routes(self.conf.local_routes)

        self.log.info("Starting listener for ExaBGP messages")
        self.bgp_connection.start()

        #self.log.info("Starting listener for command messages")
        #self.control_connection.start()

        while True:
            serialised = self.internal_command_queue.get()
            message = pb.Message()
            message.ParseFromString(serialised)
            if message.type == pb.Message.BGP:
                # got a BGP message, pass it off to the right peer process
                self.process_bgp_message(message)
            #elif message.type == pb.Message.CONTROL:
            #    # got control message, deal with it ourselves
            #    self.process_control_message(message)
            elif message.type == pb.Message.STATUS:
                # update our internal peer status dictionary
                self.process_status_message(message)
            else:
                self.log.warning("Ignoring unknown message type %s",
                        message.type)

    def process_bgp_message(self, message):
        # parse the json to figure out who this bgp message is intended for
        parsed = json.loads(message.bgp.json)
        peer_as = int(parsed["neighbor"]["asn"]["peer"])
        peer_address = parsed["neighbor"]["address"]["peer"]
        peer = self._get_peer(peer_as, peer_address)
        if peer is None:
            self.log.warning("Ignoring message from unknown peer")
            return
        # send the original message on
        peer.mailbox.put(message.SerializeToString())

    #def process_control_message(self, message):
    #    if "peer" in message:
    #        peer_asn = message["peer"]["asn"]
    #        peer_address = message["peer"]["address"]
    #        target = self._get_peer(peer_asn, peer_address)
    #    elif "table" in message:
    #        target = self._get_table(message["table"]["name"])
    #    else:
    #        target = None
    #
    #    if target is None:
    #        self.log.warning("Ignoring message for unknown target")
    #        return
    #
    #    if "action" in message:
    #        target.mailbox.put(
    #                (message["action"], message.get("arguments", None))
    #        )

    def process_status_message(self, message):
        # peer status changed, update what we know about them
        frompeer = (message.status.address, message.status.asn)
        assert(frompeer in self.status)

        self.log.debug("controller status message: %s / %s",
                message.status.asn, message.status.status)

        # no change, ignore
        if self.status[frompeer] == message.status.status:
            return

        # calculate how many peers we are missing now
        self.status[frompeer] = message.status.status
        degraded = len([x for x in self.status.values() if x is False])

        action = pb.Message()
        action.type = pb.Message.STATUS
        action.status.status = degraded

        # tell our peers that they may no longer have a full view of the routes
        for topeer in self.peers:
            topeer.mailbox.put(action.SerializeToString())

    def _get_peer(self, asn, address):
        return next((x for x in self.peers
                    if x.asn == asn and x.address == address), None)

    def _get_table(self, name):
        return next((x for x in self.tables if x.name == name), None)

if __name__ == "__main__":
    # Parse the arguments
    parser = ArgumentParser()
    parser.add_argument("configfile", metavar="configfile", type=str,
            help="path to the configuration file")
    parser.add_argument("--loglevel", default="info", type=str,
            choices=["critical", "error", "warning", "info", "debug"],
            help="set minimum log level of output")
    parser.add_argument("--prometheus_dir", default="/var/run/bgpsdn/",
            type=str, help="temporary directory used to store runtime metrics")
    args = parser.parse_args()

    # Process the log level argument string to a logging value
    if args.loglevel == "critical":
        log_level = logging.CRITICAL
    elif args.loglevel == "error":
        log_level = logging.ERROR
    elif args.loglevel == "warning":
        log_level = logging.WARNING
    elif args.loglevel == "info":
        log_level = logging.INFO
    elif args.loglevel == "debug":
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    # Initialise the logging module for the execution
    logging.basicConfig(level=log_level,
            format="%(levelname).1s | %(name)-10s | %(message)s")

    # set up the environment so that multiprocessing prometheus will work
    os.environ["prometheus_multiproc_dir"] = args.prometheus_dir

    # Initialise the controller
    controller = Controller(args.configfile)
    controller.run()
