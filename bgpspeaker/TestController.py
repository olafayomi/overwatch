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
# @Author : Dimeji Fayomi


import time
import grpc
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
from google.protobuf import empty_pb2
# from google.protobuf.empty_pb2 import Empty
from concurrent import futures
import beeprint

_ONE_DAY_IN_SECONDS = 60 * 60 * 24
metadata = [('ip', '127.0.0.1')]


class Controller(exaBGPChannel.ControllerInterfaceServicer):

    def SendUpdate(self, request, context):
        metadata = dict(context.invocation_metadata())
        print("Update received")
        print(metadata)
        update = MessageToDict(request)
        print("Update message: %s\n" % update)
        return empty_pb2.Empty()

    def SendPeerState(self, request, context):
        metadata = dict(context.invocation_metadata())
        print("Peer state message received")
        print(metadata)
        state = MessageToDict(request)
        print("State message: %s\n" % state)
        return empty_pb2.Empty()

    def SendPeerOpen(self, request, context):
        metadata = dict(context.invocation_metadata())
        print("Open message received")
        print(metadata)
        state = MessageToDict(request)
        print("Open message: %s\n" % state)
        return empty_pb2.Empty()

    def SendPeerKeepalive(self, request, context):
        metadata = dict(context.invocation_metadata())
        print("Keepalive received")
        print(metadata)
        state = MessageToDict(request)
        print("Keepalive messages: %s\n" % state)
        return empty_pb2.Empty()

    def SendUpdateEoR(self, request, context):
        metadata = dict(context.invocation_metadata())
        print("EOR message received")
        print(metadata)
        state = MessageToDict(request)
        print("EOR message: %s\n" % state)
        return empty_pb2.Empty()

    def GetPeerAddr(self, request, context):
        metadata = dict(context.invocation_metadata())
        print("GoBGP Proxy request for peer details received")
        print(metadata)
        addr = 42
        for i in range(2):
            peer = exabgp.GoBGPAddPeer()
            peer.peer_as = 64496
            peer.local_as = 64496
            addr += 1
            peer.peer_addr = '192.168.122.'+str(addr)
            peer.speaker_id = '192.168.122.172'
            yield peer

        



messages = [('170.0.0.0/24', 'announce', 'self', 'external',
             '100 200 400'),
            ('175.0.0.0/24', 'announce', 'self', 'incomplete', '100 200'),
            ('180.0.0.0/24', 'announce', 'self', 'incomplete', '200')]


class UpdatePeer(exaBGPChannel.ExabgpInterfaceServicer):

    def GetCtlrMsg(self, request, context):
        metadata = dict(context.invocation_metadata())
        if len(messages) != 0:
            route = messages.pop()
            msg = exabgp.ControllerToBGP()
            msg.peer_as = 64496
            msg.neighbor_address = "192.168.122.172"
            if route[1] == "announce":
                msg.msgtype = 0
            else:
                msg.msgtype = 1
            nh = gobgp.NexthopAction()
            nlri = exabgp.ExaNLRI()
            pattrs = []

            nlri.prefix.append(route[0])

            if route[2] == "self":
                nh.self = True
                nh.address = '192.168.122.43'
            else:
                nh.self = False
                nh.address = route[2]

            if route[3] == "external":
                originattr = attrs.OriginAttribute()
                originattr.origin = 1
                any_attrs = Any()
                any_attrs.Pack(originattr)
                msg.pattrs.append(any_attrs)
            elif route[3] == "internal":
                originattr = attrs.OriginAttribute()
                originattr.origin = 0
                any_attrs = Any()
                any_attrs.Pack(originattr)
                msg.pattrs.append(any_attrs)
            else:
                originattr = attrs.OriginAttribute()
                originattr.origin = 2
                any_attrs = Any()
                any_attrs.Pack(originattr)
                msg.pattrs.append(any_attrs)

            msg.nlri.MergeFrom(nlri)
            msg.nexthop.MergeFrom(nh)
        else:
            msg = exabgp.ControllerToBGP()
        print("ROUTE UPDATE SENT\n")
        return msg



def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    exaBGPChannel.add_ControllerInterfaceServicer_to_server(Controller(),
                                                            server)
    exaBGPChannel.add_ExabgpInterfaceServicer_to_server(UpdatePeer(),
                                                        server)
    server.add_insecure_port('127.0.0.1:50051')
    server.start()
    try:
        while True:
            time.sleep(_ONE_DAY_IN_SECONDS)
    except KeyboardInterrupt:
        server.stop(0)


def CreateExaBGPStub():
    channel = grpc.insecure_channel('localhost:50052')
    try:
        grpc.channel_ready_future(channel).result(timeout=30)
    except grpc.FutureTimeoutError:
        print("Error connecting to ExaBGP server")
    else:
        stub = exaBGPChannel.ExabgpInterfaceStub(channel)
        return stub


def SendMessage():
    messages = [('170.0.0.0/24', 'announce', 'self', 'external',
                 '100 200 400'),
                ('175.0.0.0/24', 'announce', 'self', 'incomplete', '100 200'),
                ('180.0.0.0/24', 'announce', 'self', 'incomplete', '200')]
    exaStub = CreateExaBGPStub()
    if len(messages) != 0:
        route = messages.pop()
        msg = exabgp.ControllerToBGP()
        msg.peer_as = 64496
        msg.neighbor_address = "192.168.122.172"
        if route[1] == "announce":
            msg.msgtype = 0
        else:
            msg.msgtype = 1
        nh = gobgp.NexthopAction()
        nlri = exabgp.ExaNLRI()
        pattrs = []

        nlri.prefix.append(route[0])

        if route[2] == "self":
            nh.self = True
            nh.address = '192.168.122.43'
        else:
            nh.self = False
            nh.address = route[2]

        if route[3] == "external":
            originattr = attrs.OriginAttribute()
            originattr.origin = 1
            any_attrs = Any()
            any_attrs.Pack(originattr)
            msg.pattrs.append(any_attrs)
        elif route[3] == "internal":
            originattr = attrs.OriginAttribute()
            originattr.origin = 0
            any_attrs = Any()
            any_attrs.Pack(originattr)
            msg.pattrs.append(any_attrs)
        else:
            originattr = attrs.OriginAttribute()
            originattr.origin = 2
            any_attrs = Any()
            any_attrs.Pack(originattr)
            msg.pattrs.append(any_attrs)

        msg.nlri.MergeFrom(nlri)
        msg.nexthop.MergeFrom(nh)
    else:
        msg = exabgp.ControllerToBGP()
    send = exaStub.SendCtlrMsg.future(msg, metadata=metadata)
    result = send.result()


if __name__ == '__main__':
    serve()
