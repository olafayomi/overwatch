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
#from google.protobuf.empty_pb2 import Empty
from concurrent import futures

_ONE_DAY_IN_SECONDS = 60 * 60 * 24


class Controller(exaBGPChannel.exabgpapiServicer):

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
        print("Keepalive messages: %s\n" %state)
        return empty_pb2.Empty()

    def SendUpdateEoR(self, request, context):
        metadata = dict(context.invocation_metadata())
        print("EOR message received")
        print(metadata)
        state = MessageToDict(request)
        print("EOR message: %s\n" % state)
        return empty_pb2.Empty()


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    exaBGPChannel.add_exabgpapiServicer_to_server(Controller(), server)
    server.add_insecure_port('127.0.0.1:50051')
    server.start()
    try:
        while True:
            time.sleep(_ONE_DAY_IN_SECONDS)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    serve()
