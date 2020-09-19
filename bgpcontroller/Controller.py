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
# from beeprint import pp
import time
import grpc
import queue
import attribute_pb2 as attrs
import capability_pb2 as caps
import gobgp_pb2 as gobgp
import exabgp_pb2 as exabgp
import exabgpapi_pb2 as exabgpapi
import exabgpapi_pb2_grpc as exaBGPChannel
from google.protobuf.any_pb2 import Any
from google.protobuf.timestamp_pb2 import Timestamp
from google.protobuf.json_format import MessageToJson
from google.protobuf.json_format import MessageToDict
from google.protobuf.empty_pb2 import Empty
from concurrent import futures



class Controller(exaBGPChannel.ControllerInterfaceServicer,
                 exaBGPChannel.ExabgpInterfaceServicer):
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
        self.grpc_addr = self.conf.grpc_address
        self.grpc_port = self.conf.grpc_port
        self.peers = self.conf.peers
        self.tables = self.conf.tables
        self.bgpspeakers = self.conf.bgpspeakers
        self.network.peers = self.peers

        # all peers start down
        self.status = {}
        for peer in self.peers:
            self.status[(peer.address, peer.asn)] = False
        # All speakers start down
        self.speakerstatus = {}
        for speaker in self.bgpspeakers:
            self.speakerstatus[(speaker.address)] = False
    
        self.log.info("DIMEJI TESTING: Speaker status at startup: %s" %self.speakerstatus)
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

        self.log.info("Starting gRPC server")
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=100),
                             options=(
                                 ('grpc.keepalive_time_ms',60000),
                                 # send keepalive ping every 60 seconds
                                 ('grpc.keepalive_timeout_ms',30000),
                                 ('grpc.keepalive_permit_without_calls',True),
                                 ('grpc.http2.max_pings_without_data',0),
                                 ('grpc.http2.min_time_between_pings_ms',60000),
                                 ('grpc.http2.min_ping_interval_without_data_ms',30000)
                             )
                            )
        exaBGPChannel.add_ControllerInterfaceServicer_to_server(self, server)
        exaBGPChannel.add_ExabgpInterfaceServicer_to_server(self, server)
        server.add_insecure_port(self.grpc_addr+':'+str(self.grpc_port))
        server.start()

        self.log.info("Starting BGP speakers")
        for speaker in self.bgpspeakers:
            self.log.debug("Starting BGPSpeaker %s" % speaker.name)
            speaker.daemon = True
            speaker.start()

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

        self.log.info("DIMEJI TESTING speaker status are starting: %s" %self.speakerstatus)
        # read local route information, for now this won't change
        self.read_local_routes(self.conf.local_routes)

        #self.log.info("Starting listener for ExaBGP messages")
        #self.bgp_connection.start()

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
            elif msgtype == "healthcheck":
                # 
                self.process_healthcheck_message(command)
            elif msgtype == "encode":
                # Receive routes to be announced or withdrawn from
                # peer processes and pass it off to the appropriate speaker process
                self.process_encode_message(command)
            else:
                self.log.warning("Ignoring unkown message type %s " % msgtype)
	    

    def SendUpdate(self, request, context):
        metadata = dict(context.invocation_metadata())
        update = MessageToDict(request)
        speaker = self._get_speaker(update["speakerId"])
        if speaker is None:
            self.log.warning("Ignoring update message from unknown speaker")
            return
        speaker.mailbox.put(("update", update))
        self.log.info("Update message: %s" %update)
        return Empty()

    def SendPeerState(self, request, context):
        metadata = dict(context.invocation_metadata())
        state = MessageToDict(request)
        speaker = self._get_speaker(state["speakerId"])
        if speaker is None:
            self.log.warning("Ignoring peer state message from unknown speaker")
            return
        speaker.mailbox.put(("peerstate", state))
        self.log.info("State message:  %s" %state)
        return Empty()

    def SendPeerOpen(self, request, context):
        metadata = dict(context.invocation_metadata())
        open_msg = MessageToDict(request)
        speaker = self._get_speaker(open_msg["speakerId"])
        if speaker is None:
            self.log.warning("Ignoring peer open message from unknown speaker")
            return
        speaker.mailbox.put(("peercap", open_msg))
        self.log.info("Open message: %s" %open_msg)
        return Empty()

    def SendPeerKeepalive(self, request, context):
        metadata = dict(context.invocation_metadata())
        state = MessageToDict(request)
        speaker = self._get_speaker(state["speakerId"])
        peer_as = state["peerAs"]
        peer_address = state["neighborAddress"]
        peer = self._get_peer(peer_as, peer_address)
        if speaker is None:
            self.log.warning("Ignoring keepalive from unknown speaker")
            return
        speaker.mailbox.put(("healthcheck", state))
        #self.log.info("Keepalive message: %s" %state)
        return Empty()

    def SendUpdateEoR(self, request, context):
        metadata = dict(context.invocation_metadata())
        update_eor = MessageToDict(request)
        speaker = self._get_speaker(update_eor["speakerId"])
        if speaker is None:
            self.log.warning("Ignoring update EOR message from unknown speaker")
            return
        speaker.mailbox.put(("update", update_eor))
        self.log.info("EOR message: %s" %update_eor)
        return Empty()

    def GetCtlrMsg(self, request, context):
        metadata = dict(context.invocation_metadata())
        try:
            message = self.outgoing_control_queue.get_nowait()
            # do something here
        except queue.Empty:
            msg = exabgp.ControllerToBGP()
            return msg
        return message

    def process_bgp_message(self, message):
        #peer_as = int(message["neighbor"]["asn"]["peer"])
        #peer_address = message["neighbor"]["address"]["peer"]
        #peer = self._get_peer(peer_as, peer_address)
        peer_as = int(message["peer"]["asn"])
        peer_address = message["peer"]["address"]
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
            self.log.info("DIMEJI_CONTROLLER_DEBUG process_control_message for table is %s" % message)
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

    def process_encode_message(self, message):
        # A route has to be announced or withdrawn to 
        # a peer. This function receives a route message
        # from a peer process and locates the right speaker
        # for peer that is connected to that speaker.
        peer = message['peer']
        for speaker in self.bgpspeakers:
           
            if peer in speaker.peers:
                if message['type'] == "advertise":
                    speaker.mailbox.put(("announce", message))
                    return

                if message['type'] == "withdraw":
                    speaker.mailbox.put(("withdraw", message))
                    return
        self.log.debug("Received route announcement for peer %s with no speaker" % peer)

    def process_healthcheck_message(self, message):
        # BGP speaker status change, update what we know about the speaker
        # and its peers.
        speaker = (message["speaker"]["address"])
        asn = (message["speaker"]["asn"])
        assert(speaker in self.speakerstatus)
        
        #self.log.info("DIMEJI TESTING Speaker status after receiving healthcheck %s" %self.speakerstatus)
        self.log.debug("controller status message: %s / %s" %
                (message["speaker"]["address"], message["status"]))

        # no change, ignore
        if self.speakerstatus[speaker] == message["status"]:
            return

        # calculate how many speakers we are missing now
        self.speakerstatus[speaker] = message["status"]
        degraded = len([x for x in self.speakerstatus.values() if x is False])
        speaker_obj = self._get_speaker(speaker)

        for peer_addr in speaker_obj.peers:
            peer = self._get_peer(asn, peer_addr)
            if peer is not None:
                peer.mailbox.put(("status", degraded))


    def _get_peer(self, asn, address):
        return next((x for x in self.peers
                    if x.asn == asn and x.address == address), None)

    def _get_table(self, name):
        return next((x for x in self.tables if x.name == name), None)

    def _get_speaker(self, address):
        return next((x for x in self.bgpspeakers if x.address == address), None)

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

