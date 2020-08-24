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
import sys
import grpc
import attribute_pb2 as attrs
import gobgp_pb2 as gobgp
import exabgp_pb2 as exabgp
import exabgpapi_pb2_grpc as exaBGPChannel
from google.protobuf.empty_pb2 import Empty
from google.protobuf.json_format import MessageToDict
from concurrent import futures

metadata = [('ip', '127.0.0.1')]
_ONE_DAY_IN_SECONDS = 60 * 60 * 24


def CreateExaBGPStub():
    channel = grpc.insecure_channel('localhost:50051')
    try:
        grpc.channel_ready_future(channel).result(timeout=10)
    except grpc.FutureTimeoutError:
        print("Error connecting to ExaBGP server")
    else:
        stub = exaBGPChannel.ExabgpInterfaceStub(channel)
        return stub


def FetchMsg(stub):
    message = stub.GetCtlrMsg(Empty(), metadata=metadata)
    output = MessageToDict(message)
    if len(output) != 0:
        neigh = output['neighborAddress']
        nexthop = output['nexthop']['address']
        peer_as = output['peerAs']
        prefix = output['nlri']['prefix'][0]
        attr_dict = dict(output['pattrs'][0])
        ori = attr_dict['origin']
        if ori == 0:
            origin = 'igp'
        elif ori == 1:
            origin = 'egp'
        else:
            origin = 'incomplete'

        if message.msgtype == 0:
            sys.stdout.write('neighbor ' + neigh + ' announce route '
                             + prefix + ' next-hop '
                             + nexthop + ' origin ' + origin + '\n')
            #sys.stdout.write('announce route ' + prefix + ' next-hop '
            #                 + nexthop + ' origin ' + origin + '\n')
            sys.stdout.flush()
        else:
            sys.stdout.write('neighbor ' + neigh + ' withdraw route '
                             + prefix + '\n')
            #sys.stdout.write('withdraw route ' + prefix + '\n')
            sys.stdout.flush()


def run():
    sendStub = CreateExaBGPStub()
    while True:
        FetchMsg(sendStub)
        time.sleep(1)

if __name__ == '__main__':
    time.sleep(45)
    run()
