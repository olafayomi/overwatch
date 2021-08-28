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
import srv6_explicit_path_pb2_grpc
import srv6_explicit_path_pb2
import dataplane_pb2
import dataplaneapi_pb2_grpc

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
        self.PARModules = self.conf.PARModules
        self.datapathID = self.conf.datapathID
        self.datapath = {}
       
        #self.initial_par = 0

        # all peers start down
        self.status = {}
        for peer in self.peers:
            self.status[(peer.address, peer.asn)] = False
        # All speakers start down
        self.speakerstatus = {}
        for speaker in self.bgpspeakers:
            self.speakerstatus[(speaker.address)] = False
    
        #self.log.info("DIMEJI TESTING: Speaker status at startup: %s" %self.speakerstatus)
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


        #dpchannel = grpc.insecure_channel(target='192.168.122.172:50055')
        #dpstub = srv6_explicit_path_pb2_grpc.SRv6ExplicitPathStub(dpchannel)
        #path_request = srv6_explicit_path_pb2.SRv6EPRequest()
        #path = path_request.path.add()
        ### Set destination, device, encapmode
        #path.destination = "2001:df15::/48"
        #path.device = "veth0"
        #path.encapmode = "inline"
        #srv6_segment = path.sr_path.add()
        #srv6_segment.segment = "2001:df9::1"
        #srv6_segment = path.sr_path.add()
        #srv6_segment.segment = "2001:df8::1"
        #response = dpstub.Create(path_request, metadata=([('ip', "192.168.122.43")]))
        #self.log.debug("Response from dp: %s" %response)

        self.log.info("Starting PAR modules")
        for parmodule in self.PARModules:
            self.log.debug("Starting PARModule %s" % parmodule.name)
            parmodule.daemon = True
            parmodule.start()
            for f in parmodule.flows:
                self.log.debug("%s: %s, %s, %s" %(parmodule.name, f.name, f.protocol, f.port))


        self.log.info("Starting BGP speakers")
        for speaker in self.bgpspeakers:
            self.log.debug("Starting BGPSpeaker %s" % speaker.name)
            speaker.daemon = True
            speaker.start()

        self.log.info("Starting peers")
        for peer in self.peers:
            self.log.debug("Starting Peer %s" % peer.name)
            peer.daemon = True
            peer.PARModules = self.PARModules
            parprefixes = []
            self.log.debug("CONTROLLER PAR WEIRDNESS: Peer: %s is enable_PAR: %s" %(peer.name, peer.enable_PAR))
            ### XXX: Pass PAR_prefixes to all peers (20201119)
            ### XXX: To disable, uncomment if statement below
            ### XXX: and indent for statement
            #if peer.enable_PAR is True:
            for module in self.PARModules:
                parprefixes += module.prefixes
                    #module.dpstub = dpstub
            peer.PAR_prefixes = parprefixes
                #if peer.address == "192.168.122.172":
                #    dpchannel = grpc.insecure_channel(target='192.168.122.172:50055')
                #    dpstub = srv6_explicit_path_pb2_grpc.SRv6ExplicitPathStub(dpchannel)
                #    path_request = srv6_explicit_path_pb2.SRv6EPRequest()
                ## Create a new path
                #    path = path_request.path.add()
                ## Set destination, device, encapmode
                #    path.destination = "2001:df15::/48"
                #    path.device = "veth0"
                #    path.encapmode = "inline"

                #    srv6_segment = path.sr_path.add()
                #    srv6_segment.segment = "2001:df9::1"
                #    srv6_segment = path.sr_path.add()
                #    srv6_segment.segment = "2001:df8::1"
                #    response = dpstub.Create(path_request, metadata=([('ip',"192.168.122.43")]))
                #    self.log.debug("PEER: %s sending dp message response : %s" %(peer.name,response))

            peer.start()
            for module in peer.PARModules:
                for f in module.flows:
                    self.log.debug("(%s %s): %s  %s" %(peer.name, module.name, f.name, f.protocol))

        self.log.info("Initiating connection to the datapath of PAR-enabled peers")
        for (addr, port) in self.datapathID:
            self.log.info(" Address: %s, Port: %s" %(addr, port))
            #dpchannel = grpc.insecure_channel(target=addr+':'+str(port))
            dpchannel = grpc.insecure_channel("[%s]:%s" %(addr, str(port)))
            srv6_stub = srv6_explicit_path_pb2_grpc.SRv6ExplicitPathStub(dpchannel)
            dp_state_stub = dataplaneapi_pb2_grpc.DataplaneStateStub(dpchannel)
            dp_config_stub = dataplaneapi_pb2_grpc.ConfigureDataplaneStub(dpchannel)
            self.datapath[addr] = [srv6_stub, dp_state_stub, dp_config_stub, 'NOT CONNECTED']

        self.log.info("Starting routing tables")
        for table in self.tables:
            self.log.debug("Starting RouteTable %s" % table.name)
            table.daemon = True
            table.start()

        #self.log.info("DIMEJI TESTING speaker status are starting: %s" %self.speakerstatus)
        # read local route information, for now this won't change
        self.read_local_routes(self.conf.local_routes)

        #self.log.info("Starting listener for ExaBGP messages")
        #self.bgp_connection.start()

        self.log.info("Starting listener for command messages")
        self.control_connection.start()

        #self.log.debug("Everything should be setup hopefully by now, invite Peer processes to send requests!!!!!!!!!")
        #self.log.debug("Nudging Peer processes for Interface request!!!")
        #for peer in self.peers:
        #    message = "interface"
        #    peer.mailbox.put(("interface-init", message))

        #for peer in self.peers:
        #    message = "rtables"
        #    peer.mailbox.put(("rtable-init", message))

        #for peer in self.peers:
        #    message = "flowmarks"
        #    peer.mailbox.put(("req-flowmark", message))


        while True:
            msgtype, command = self.internal_command_queue.get()
            #self.log.debug("DIMEJI Received message type %s  on internal_command_queue %s" %(msgtype,command))
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
            elif msgtype == "par-update":
                self.log.debug("DIMEJI Received par-update message on internal_command_queue %s" %command)
                self.process_par_message(command)
            elif msgtype == "steer":
                self.process_update_datapath(command)
                self.log.debug("DIMEJI CONTROLLER received PAR steer message on internal_command_queue %s" %command)
            elif msgtype == "manage-dataplane":
                self.process_dataplane_mgmt(command)
                self.log.debug("Controller has received a dataplane request from a peer process on internal_command_queue %s" %command)
            elif msgtype == "configure-dataplane": 
                self.process_config_dataplane(command)
                self.log.debug("Controller has received a dataplane configuration request from a peer process on internal_command_queue %s" %command)
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
        peer_as = open_msg["peerAs"]
        peer_address = open_msg["neighborAddress"]
        stub_list = self.datapath[peer_address]
        status = stub_list[3]
        if status != 'CONNECTED':
            peer = self._get_peer(peer_as, peer_address)
            self.log.debug("Everything should be setup hopefully by now, invite process for Peer %s to send requests!!!!!!!!!" %peer.name)
            self.log.debug("Nudging process for Peer %s  for Interface request!!!" %peer.name )
            message = "interface"
            peer.mailbox.put(("interface-init", message))
            #message = "rtables"
            #peer.mailbox.put(("rtable-init", message))
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
        self.log.debug("Keepalive message: %s" %state)
        if peer_address in self.datapath:
            stub_list = self.datapath[peer_address]
            status = stub_list[3]
            if status != 'CONFIGURED':
                peer = self._get_peer(peer_as, peer_address)
                self.log.info("DATAPLANE on %s still not connected or fully configured, trying again!!!!" %peer.name)
                self.log.debug("Everything should be setup hopefully by now, invite process for Peer %s to send requests!!!!!!!!!" %peer.name)
                self.log.debug("Nudging process for Peer %s  for Interface request!!!" %peer.name )
                message = "interface"
                peer.mailbox.put(("interface-init", message))
                #message = "rtables"
                #peer.mailbox.put(("rtable-init", message))
            
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
            #self.log.info("DIMEJI_CONTROLLER_DEBUG process_control_message for table is %s" % message)
            target = self._get_table(message["table"]["name"])
        else:
            target = None

        if target is None:
            self.log.warning("Ignoring message for unknown target")
            return

        if "action" in message:
            self.log.info("DIMEJI_CONTROLLER_DEBUG process_control_message is %s" % message)
            target.mailbox.put(
                    (message["action"], message.get("arguments", None))
            )

    def process_dataplane_mgmt(self, message):
        peer_addr = message["peer"]["address"]
        if message["action"] == "get-interfaces": 
            if peer_addr in self.datapath:
                stub_list = self.datapath[peer_addr]
                stub = stub_list[1]
                iface_req = Empty()
                try:
                    response = stub.GetIfaces(iface_req,metadata=([('ip', '2001:df40::1')]))
                except grpc.RpcError as e:
                    if grpc.StatusCode.UNIMPLEMENTED == e.code():
                        self.log.debug("WARNING: Dataplane on %s is not ready" %peer_addr)
                        return
                response_dict = MessageToDict(response)
                #self.datapath[peer_addr][3] = 'CONNECTED'
                peer = self._get_peer(self.asn, peer_addr)
                if peer:
                    self.log.debug("PROCESS_DATAPLANE_MGMT doing putting message for %s"  % peer_addr)
                    self.log.debug("PROCESS_DATAPLANE_MGMT XXXX  INTENDED RESPONSE: %s" %response_dict)
                    peer.mailbox.put(("interfaces", response_dict))
                    self.datapath[peer_addr][3] = 'CONNECTED'

        #if message["action"] == 


    def process_config_dataplane(self, message): 
        peer_addr = message["peer"]["address"]
        stub_list = self.datapath[peer_addr]
        stub = stub_list[2]
        status = stub_list[3]

        if status == 'NOT CONNECTED':
            self.log.debug("WARNING: Not proceeding with request for dataplane on %s" %peer_addr)
            return
    
        if message["action"] == "create-tables":
            if peer_addr in self.datapath:
                partrafficmod = message["par-modules"]
                rtablecreate = dataplane_pb2.PARFlows() 
                rtablecreate.flow.extend(partrafficmod)
                response = stub.CreateRouteTable(rtablecreate)
                if not response.CreatedAll:
                    self.log.warn("DP on PEER:%s unable to create tables for %s" %(peer_addr,rtablecreate.flow))
                dp_tables = []
                for table in response.created:
                    dp_tables.append((table.tableName, table.tableNo))
                peer = self._get_peer(self.asn, peer_addr)
                if peer:
                    self.log.debug("SENDING DP_TABLES!!!! :%s" %dp_tables)
                    if len(dp_tables) >= 0:
                        peer.mailbox.put(("dp-tables", dp_tables))

        if message["action"] == "create-flowmark-rules":
            if peer_addr in self.datapath:
                flows = message["flows"]
                self.log.debug("CONTROLLER process_config_dataplane PROCESSING flows message from datapath: %s" %flows)
                fwmark_req = dataplane_pb2.RequestFlowMark()
                iprules = []
                for name, details in flows.items():
                    if details[1] is None:
                        self.log.debug("PAR routetable number not yet set!!!")
                        return
                    iprule = dataplane_pb2.IPRule()
                    iprule.fwmark = details[0]
                    iprule.table = details[1]
                    iprules.append(iprule)
                fwmark_req.rule.extend(iprules)
                try:
                    fwmark_res = stub.FlowMark(fwmark_req)
                except grpc.RpcError as e:
                    if grpc.StatusCode.UNKNOWN == e.code():
                        self.log.debug("WARNING: Dataplane error on %s" %peer_addr)
                        return
                
                if not fwmark_res.applied:
                    self.log.warn("DP on PEER:%s unable to create these IP rules: %s" %(peer_addr,fwmark_res.failed))
                # Add iptable rules for successful ip rules
                ip6table_req = dataplane_pb2.RequestIP6TableRule() 
                ip6tables = []
                for name, details in flows.items():
                    for rule in fwmark_res.successful: 
                        if rule.fwmark == details[0]:
                            for iface in details[4]:
                                ip6table = dataplane_pb2.IP6TableRule() 
                                ip6table.intName = iface
                                ip6table.protocol = details[2]
                                ip6table.DPort = details[3]
                                ip6table.FwmarkNo = rule.fwmark
                                ip6tables.append(ip6table)
                ip6table_req.rules.extend(ip6tables)
                self.log.warn("IPtable rule number is %s" %len(ip6tables))
                self.log.warn("IPtables rules to be send: %s" %ip6tables)
                ip6table_res = stub.AddIp6tableRule(ip6table_req)

                if not ip6table_res.ip6tablecreated:
                    self.log.warn("DP on PEER:%s unable to create these iptable rules: %s" %(pper_addr, ip6table_res.failed))
                dpflows = []
                for ip6tab in ip6table_res.successful: 
                    for name, details in flows.items():
                        if ip6tab.FwmarkNo == details[0]:
                            tab_no = details[1] 

                    tup = (ip6tab.FwmarkNo, ip6tab.protocol, ip6tab.DPort, ip6tab.intName, tab_no)
                    dpflows.append(tup)
                peer = self._get_peer(self.asn, peer_addr) 
                if peer:
                    self.log.debug("SENDING DPFLOWS!!!!! :%s" %dpflows)
                    if len(dpflows) >= 0:
                        peer.mailbox.put(("dp-flowmarks", dpflows))
                        self.datapath[peer_addr][3] = 'CONFIGURED'

        
    def process_update_datapath(self, message):
        self.log.info("DIMEJI_CONTROLLER_DEBUG_BEGIN_PROCESSING process_update_datapath message is %s" %message)
        peer_addr = message["peer"]["address"]
        if message["action"] == "Replace":
            if peer_addr in self.datapath:
                stub_list = self.datapath[peer_addr]
                stub = stub_list[0]
                path_request = srv6_explicit_path_pb2.SRv6EPRequest()
                path = path_request.path.add() 
                path.destination = message["path"]["destination"]
                path.device = message["path"]["device"]
                path.encapmode = message["path"]["encapmode"]
                if 'table' in message["path"]:
                    path.table = message["path"]["table"]
                    #self.initial_par += 1
                    #if self.initial_par > 1:
                    #    self.log.info("DIMEJI_CONTROLLER_DEBUG NOT SENDING SEGMENTS TO DP. Count: %s" %self.initial_par)
                    #    return
                for segs in message["path"]["segments"]:
                    srv6_segment = path.sr_path.add()
                    srv6_segment.segment = segs
                #response = stub.Replace(path_request, metadata=([('ip','192.168.122.43')]))
                response = stub.Replace(path_request, metadata=([('ip','2001:df23::1')]))
                self.log.info("DIMEJI_CONTROLLER_DEBUG Controller received response %s after sending updating datapath to add segs on peer %s" %(response, peer_addr))
            else:
                self.log.info("DIMEJI_CONTROLLER_DEUBG Controller received STEER message from %s which is not PAR-enabled!!!!!!" %peer_addr)
        
        if message["action"] == "Remove":
            if peer_addr in self.datapath:
                stub_list = self.datapath[peer_addr]
                stub = stub_list[0]
                path_request = srv6_explicit_path_pb2.SRv6EPRequest()
                path = path_request.path.add() 
                path.destination = message["path"]["destination"]
                path.device = message["path"]["device"]
                path.encapmode = message["path"]["encapmode"]
                if 'table' in message["path"]:
                    path.table = message["path"]["table"]
                for segs in message["path"]["segments"]:
                    srv6_segment = path.sr_path.add()
                    srv6_segment.segment = segs
                #response = stub.Replace(path_request, metadata=([('ip','192.168.122.43')]))
                response = stub.Remove(path_request, metadata=([('ip','2001:df23::1')]))
                self.log.info("DIMEJI_CONTROLLER_DEBUG Controller received response %s after sending updating datapath to remove segs on peer %s" %(response, peer_addr))
            else:
                self.log.info("DIMEJI_CONTROLLER_DEUBG Controller received STEER message from %s which is not PAR-enabled!!!!!!" %peer_addr)
        self.log.info("DIMEJI_CONTROLLER_DEBUG_END_PROCESSING process_update_datapath")

    def process_status_message(self, message):
        # peer status changed, update what we know about them
        peer = (message["peer"]["address"], message["peer"]["asn"])
        assert(peer in self.status)

        self.log.debug("Controller process_status_message. Status for peer %s changed to %s"
                %(message["peer"]["address"], message["status"]))
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
            
    def process_par_message(self, message):
        # Inform PAR enabled peers that a better route
        # is available for the prefixe monitored.
        for peer in self.peers:
            if peer.enable_PAR is False:
                continue
            self.log.info("DIMEJI_DEBUG_CONTROLLER: _process_par_message %s" % message)
            peer.mailbox.put(("par", message))
        return

    def process_encode_message(self, message):
        # A route has to be announced or withdrawn to 
        # a peer. This function receives a route message
        # from a peer process and locates the right speaker
        # for peer that is connected to that speaker.
        peer = message['peer']
        for speaker in self.bgpspeakers:
           
            if peer not in speaker.peers:
                return
            else:
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
        
        self.log.debug("DIMEJI TESTING Speaker status after receiving healthcheck %s" %self.speakerstatus)
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
            format="%(asctime)s| %(levelname).1s | %(name)-10s | %(message)s")

    # Initiate the controller
    controller = Controller(args.conf_file)
    controller.run()

