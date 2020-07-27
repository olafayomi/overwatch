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

import sys
import json
import routecontrol_types_pb2 as rc_messages
import routecontrol_pb2_grpc as routecontrol_service
from StubWrapper import StubWrapper as Stub
from google.protobuf.timestamp_pb2 import Timestamp
from datetime import datetime
import ipaddress
import grpc


def OriginCode(origin):
    if origin == "incomplete":
        return 2
    if origin == "igp":
        return 0
    if origin == "egp":
        return 1

def parse_update(jsonline):
    update = {}
    update["exa_version"] = jsonline["exabgp"]
    tstamp = datetime.fromtimestamp(jsonline["time"])
    PBTimestamp = Timestamp()
    update["timestamp"] = PBTimestamp.FromDatetime(tstamp)
    update["host"] = jsonline["host"]
    update["type"] = jsonline["type"]
    update["asn"] = jsonline["neighbor"]["asn"]
    update["ipaddr"] = jsonline["neighbor"]["address"]
    msg = jsonline["neighbor"]["message"]
    sys.stderr.write("msg: " + str(msg) + "\n")
    sys.stderr.flush()
    if "announce" in msg["update"]:
        update["attributes"] = jsonline["neighbor"]["message"]["update"]["attribute"]
        for next_hop_address, nlri in msg["update"]["announce"]["ipv4 unicast"].items():
            nh = {}
            nh.update({"address": next_hop_address})
            if next_hop_address == jsonline["neighbor"]["address"]["peer"]:
                nh.update({"self": True})
            else:
                nh.update({"self": False})
            update["nexthop"] = nh
            destinations = []
            for prefix in nlri:
                destination = {}
                addr = ipaddress.ip_network(prefix['nlri'])
                if addr.version == 4:
                    family = rc_messages.Family(afi=rc_messages.Family.AFI_IP,
                                                safi=rc_messages.Family.SAFI_UNICAST)

                destination.update({"nlri": addr.with_prefixlen,
                                    "prefix": addr.network_address,
                                    "netmask_len": addr.prefixlen,
                                    "family": family, "is_withdraw": False})
                destinations.append(destination)
            update["addresses"] = destinations
            update["withdraw"] = False
    else:
        #update["attributes"] = None
        destinations = []
        update["withdraw"] = True
        for nlri in jsonline['neighbor']['message']['update']['withdraw']['ipv4 unicast']:
            destination = {}
            addr = ipaddress.ip_network(nlri['nlri'])
            if addr.version == 4:
                family = rc_messages.Family(afi=rc_messages.Family.AFI_IP,
                                            safi=rc_messages.Family.SAFI_UNICAST)
                destination.update({"nlri": addr.with_prefixlen,
                                    "prefix": addr.network_address,
                                    "netmask_len": addr.prefixlen,
                                    "family": family, "is_withdraw": True})
            destinations.append(destination)
        update["addresses"] = destinations
    return update


def SendUpdate(update):
    #RouteUpdate = Stub(routecontrol_service, 'RouteControlStub', 'localhost', 50051)
    channel = grpc.insecure_channel('localhost:50051')
    try:
        grpc.channel_ready_future(channel).result(timeout=10)
    except grpc.FutureTimeoutError:
        sys.stderr.write('Error connecting to server')
        sys.stderr.flush()
    else:
        stub = routecontrol_service.RouteControlStub(channel)
        metadata = [('ip', '127.0.0.1')]
        paths = []
        for i in range(len(update["addresses"])):
            addr = rc_messages.Destination(nlri=str(update["addresses"][i]["nlri"]),
                                           prefix=rc_messages.Prefix(ip_prefix=str(update["addresses"][i]["prefix"]), netmask_len=int(update["addresses"][i]["netmask_len"])),
                                           family=rc_messages.Family(afi=rc_messages.Family.AFI_IP,
                                                                     safi=rc_messages.Family.SAFI_UNICAST),
                                           is_withdraw=update["addresses"][i]["is_withdraw"])
            paths.append(addr)

        if not update["withdraw"]:
            ack = stub.Sendupdate(rc_messages.Update(exabgp=update["exa_version"],
                                                     timestamp=update["timestamp"],
                                                     host=update["host"],
                                                     type=update["type"],
                                                     asn=rc_messages.Asn(local=update['asn']['local'],
                                                                         peer=update['asn']['peer']),
                                                     ipaddr_peers=rc_messages.IpAddress(local=update['ipaddr']['local'],
                                                                                        peer=update['ipaddr']['peer']),
                                                     attributes=rc_messages.AllAtrributes(originattr=rc_messages.OriginAttribute(origin=OriginCode(update["attributes"]["origin"])),
                                                                                          locprefattr=rc_messages.LocalPrefAttribute(local_pref=update["attributes"]["local-preference"])),
                                                     nexthop=rc_messages.Nexthop(address=update["nexthop"]["address"], self=update["nexthop"]["self"]),
                                                     addresses=paths),
                                  metadata=metadata)
        else:
            ack = stub.Sendupdate(rc_messages.Update(exabgp=update["exa_version"],
                                                     timestamp=update["timestamp"],
                                                     host=update["host"],
                                                     type=update["type"],
                                                     asn=rc_messages.Asn(local=update['asn']['local'],
                                                                         peer=update['asn']['peer']),
                                                     ipaddr_peers=rc_messages.IpAddress(local=update['ipaddr']['local'],
                                                                                        peer=update['ipaddr']['peer']),

                                                     addresses=paths),
                                  metadata=metadata)
        sys.stderr.write("Controller acknowledges update with " + ack.ack_message + " at " +str(ack.acktimestamp.ToDatetime()) + "\n")
        sys.stderr.flush()


def run():
    while True:
        line = sys.stdin.readline().strip()
        jsonline = json.loads(line)
        if (jsonline["type"] == "update") and ("update" in jsonline["neighbor"]["message"]):
            msg_dict = parse_update(jsonline)
            SendUpdate(msg_dict)
        else:
            sys.stderr.write(line + '\n')
            sys.stderr.flush()


if __name__ == '__main__':
    run()

#while True:
#    line = sys.stdin.readline().strip()
#    jsonline = json.loads(line)
#    if jsonline["type"] == "update":
#        neighbor_ip = jsonline['neighbor']['address']['peer']
#        update_message = jsonline['neighbor']['message']
#        if "update" in update_message:
#            if "announce" in update_message["update"]:
#                for next_hop_address, nlri in jsonline['neighbor']['message']['update']['announce']['ipv4 unicast'].items():
#                    for prefix in nlri:
#                        sys.stderr.write("Received a BGP update from " + neighbor_ip + '\n')
#                        sys.stderr.write("For prefix " + prefix['nlri'] + '\n')
#                        sys.stderr.write("With a next hop address of " + next_hop_address + '\n')
#                        sys.stderr.write(line)
#                        sys.stderr.flush()
#
#            if "withdraw" in update_message["update"]:
#                for nlri in jsonline['neighbor']['message']['update']['withdraw']['ipv4 unicast']:
#                    for prefix in nlri:
#                        #sys.stderr.write("Received a BGP withdrawal update from " + neighbor_ip + '\n')
#                        #sys.stderr.write("For prefix " + prefix['nlri'] + '\n')
#                        sys.stderr.write(line)
#                        sys.stderr.flush()
#    else:
#        sys.stderr.write(line + '\n')
#        sys.stderr.flush()
    
