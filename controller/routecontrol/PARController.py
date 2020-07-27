#!/usr/bin/env python


# Copyright (c) 2020, WAND Network Research Group
#                     Department of Computer Science
#                     University of Waikato
#                     Hamilton
#                     New Zealand
#
# Author Dimeji Fayomi (oof1@students.waikato.ac.nz)
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

from concurrent import futures
import time
import grpc
import routecontrol_types_pb2 as rc_messages
import routecontrol_pb2_grpc as routecontrol_service
from datetime import datetime
from google.protobuf.timestamp_pb2 import Timestamp
#import ipaddress

_ONE_DAY_IN_SECONDS = 60 * 60 * 24


class Controller(routecontrol_service.RouteControlServicer):

    def Sendupdate(self, request, context):
        metadata = dict(context.invocation_metadata())
        print(metadata)
        update = rc_messages.Update(exabgp=request.exabgp,
                                    timestamp=request.timestamp,
                                    host=request.host,
                                    type=request.type,
                                    asn=request.asn,
                                    ipaddr_peers=request.ipaddr_peers,
                                    attributes=request.attributes,
                                    nexthop=request.nexthop,
                                    addresses=request.addresses)
        print("Update received: %s\n" % update)
        now = datetime.now()
        PBTimestamp = Timestamp()
        print("Current time is: %s" %PBTimestamp.FromDatetime(now))
        return rc_messages.UpdateAck(ack_message="Acknowledged",
                                     acktimestamp=PBTimestamp.FromDatetime(now))


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    routecontrol_service.add_RouteControlServicer_to_server(Controller(),
                                                            server)
    server.add_insecure_port('127.0.0.1:50051')
    server.start()
    try:
        while True:
            time.sleep(_ONE_DAY_IN_SECONDS)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    serve()
