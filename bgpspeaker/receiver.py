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

import sys
import json
import grpc
import attribute_pb2 as attrs
import capability_pb2 as caps
import gobgp_pb2 as gobgp
import exabgp_pb2 as exabgp
import exabgpapi_pb2_grpc as exaBGPChannel
from google.protobuf.any_pb2 import Any
from google.protobuf.timestamp_pb2 import Timestamp

metadata = [('ip', '127.0.0.1')]


def OriginCode(origin):
    if origin == "igp":
        return 0
    if origin == "egp":
        return 1
    if origin == "incomplete":
        return 2


def SessionState(state):
    if state == "unknown":
        return 0
    if state == "idle":
        return 1
    if state == "connect":
        return 2
    if state == "connected":
        return 2
    if state == "active":
        return 3
    if state == "opensent":
        return 4
    if state == "openconfirm":
        return 5
    if state == "established":
        return 6
    if state == "down":
        return 7


def AdminState(state):
    if state == "unknown":
        return 1
    else:
        return 0


def MessageCode(msgtype):
    if msgtype == "open":
        return 1
    if msgtype == "update":
        return 2
    if msgtype == "notification":
        return 3
    if msgtype == "keepalive":
        return 4
    if msgtype == "refresh":
        return 5
    if msgtype == "state":
        return 6
    if msgtype == "withdraw":
        return 7


def exaBGPParser(jsonline, ctlrStub):
    try:
        neigh = jsonline["neighbor"]
    except KeyError:
        if "asn" in jsonline:
            local_as = int(jsonline["asn"]["local"])
            peer_as = int(jsonline["asn"]["peer"])
        else:
            sys.stderr.write('Malformed message received '+str(jsonline)+' \n')
            sys.stderr.flush()
            return

        if "address" in jsonline:
            speaker_id = jsonline["address"]["local"]
            peer_addr = jsonline["address"]["peer"]
        else:
            sys.stderr.write('Malformed message received '+str(jsonline)+' \n')
            sys.stderr.flush()
            return

    local_as = int(neigh["asn"]["local"])
    peer_as = int(neigh["asn"]["peer"])
    speaker_id = neigh["address"]["local"]
    peer_addr = neigh["address"]["peer"]

    if jsonline["type"] == "state":
        state = jsonline["neighbor"]["state"]
        if state == "down":
            msg = exabgp.ExaPeerState(local_as=local_as, peer_as=peer_as,
                                      neighbor_address=peer_addr,
                                      speaker_id=speaker_id,
                                      session_state=1,
                                      admin_state=AdminState(state))
        else:
            msg = exabgp.ExaPeerState(local_as=local_as, peer_as=peer_as,
                                      neighbor_address=peer_addr,
                                      speaker_id=speaker_id,
                                      session_state=SessionState(state),
                                      admin_state=AdminState(state))
        ctlrStub.SendPeerState(msg, metadata=metadata)
    elif "state" in jsonline:
        state = jsonline["state"]
        if state == "down":
            msg = exabgp.ExaPeerState(local_as=local_as, peer_as=peer_as,
                                      neighbor_address=peer_addr,
                                      speaker_id=speaker_id,
                                      session_state=1,
                                      admin_state=AdminState(state))
        else:
            msg = exabgp.ExaPeerState(local_as=local_as, peer_as=peer_as,
                                      neighbor_address=peer_addr,
                                      speaker_id=speaker_id,
                                      session_state=SessionState(state),
                                      admin_state=AdminState(state))
        ctlrStub.SendPeerState(msg, metadata=metadata)
    else:
        # Should raise an unknown message here...
        pass

    if jsonline["type"] == "open":
        msgcode = MessageCode(jsonline["type"])
        if jsonline["neighbor"]["direction"]:
            if jsonline["neighbor"]["direction"] == "receive":
                encode_msgs = gobgp.Messages(
                            received=gobgp.Message(
                                    open=msgcode))
            else:
                encode_msgs = gobgp.Messages(sent=gobgp.Message(open=msgcode))
        # Grab multiprotocol capability first
        if "1" not in jsonline["neighbor"]["open"]["capabilities"]:
            sys.stderr.write("Received BGP Open message from peer: "
                             + peer_addr
                             + " with no multiprotocol capability")
            sys.stderr.flush()
            return
        else:
            cap = jsonline["neighbor"]["open"]["capabilities"]["1"]
            familylist = []
            for fam in cap["families"]:
                if fam == "ipv4/unicast":
                    familylist.append(gobgp.Family(
                                            afi=gobgp.Family.AFI_IP,
                                            safi=gobgp.Family.SAFI_UNICAST))

                if fam == "ipv4/multicast":
                    familylist.append(gobgp.Family(
                                            afi=gobgp.Family.AFI_IP,
                                            safi=gobgp.Family.SAFI_MULTICAST))

                if fam == "ipv4/flow":
                    familylist.append(
                            gobgp.Family(
                                afi=gobgp.Family.AFI_IP,
                                safi=gobgp.Family.SAFI_FLOW_SPEC_UNICAST))

                if fam == "ipv6/unicast":
                    familylist.append(gobgp.Family(
                                            afi=gobgp.Family.AFI_IP6,
                                            safi=gobgp.Family.SAFI_UNICAST))

                if fam == "ipv6/multicast":
                    familylist.append(gobgp.Family(
                                            afi=gobgp.Family.AFI_IP6,
                                            safi=gobgp.Family.SAFI_MULTICAST))

                if fam == "ipv6/flow":
                    familylist.append(
                            gobgp.Family(
                                afi=gobgp.Family.AFI_IP6,
                                safi=gobgp.Family.SAFI_FLOW_SPEC_UNICAST))
                # TO-DO: Set default multiprotocol family
            multiprotlist = []
            for fam in familylist:
                multiprotlist.append(caps.MultiProtocolCapability(family=fam))
            capabilities = exabgp.ExaPeerCapabilities()
            capabilities.multiprotocolcap.extend(multiprotlist)

        # Grab the  capabilities
        for no, cap in jsonline["neighbor"]["open"]["capabilities"].items():
            if no == "2":
                routerefresh = caps.RouteRefreshCapability()
                capabilities.routerefreshcap.MergeFrom(routerefresh)

            if no == "71":
                longlivegrcap = caps.LongLivedGracefulRestartCapability()
                grcaptuples = []
                for fam in familylist:
                    grcaptuples.append(
                            caps.LongLivedGracefulRestartCapabilityTuple(
                                family=fam,
                                flags=0))
                longlivegrcap.tuples.extend(grcaptuples)
                capabilities.longlivedgracefulrestartcap.MergeFrom(
                        longlivegrcap)

            if no == "69":
                addpathcap = caps.AddPathCapability()
                addpathtuples = []
                for key, value in cap.items():
                    if key == "ipv4/unicast":
                        family = gobgp.Family(afi=gobgp.Family.AFI_IP,
                                              safi=gobgp.Family.SAFI_UNICAST)
                        if value == "send/receive":
                            mode = caps.AddPathMode.MODE_BOTH
                        if value == "send":
                            mode = caps.AddPathMode.MODE_SEND
                        if value == "receive":
                            mode = caps.AddPathMode.MODE_RECEIVE
                        if value == "none":
                            mode = caps.AddPathMode.MODE_NONE
                        addpathtuple = caps.AddPathCapabilityTuple(
                                family=family, mode=mode)
                        addpathtuples.append(addpathtuple)

                addpathcap.tuples.extend(addpathtuples)
                capabilities.addpathcap.MergeFrom(addpathcap)

            if no == "64":
                grcap = caps.GracefulRestartCapability(flags=1,
                                                       time=cap["time"])
                grcaptuples = []
                for fam in familylist:
                    grcaptuple = caps.GracefulRestartCapabilityTuple(
                            family=fam, flags=1)
                    grcaptuples.append(grcaptuple)
                grcap.tuples.extend(grcaptuples)
                capabilities.gracefulrestartcap.MergeFrom(grcap)

            if no == "65":
                fouroctetas = caps.FourOctetASNumberCapability()
                # fouroctetas.as = peer_as
                setattr(fouroctetas, "as", peer_as)
                capabilities.fouroctetascap.MergeFrom(fouroctetas)
        msg = exabgp.ExaPeerOpen(local_as=local_as, peer_as=peer_as,
                                 neighbor_address=peer_addr,
                                 speaker_id=speaker_id,
                                 messages=encode_msgs,
                                 capabilities=capabilities,
                                 hold_time=int(jsonline["neighbor"]
                                                       ["open"]["hold_time"]),
                                 bgp_version=int(jsonline["neighbor"]
                                                         ["open"]["version"]))
        ctlrStub.SendPeerOpen(msg, metadata=metadata)

    if jsonline["type"] == "keepalive":
        msgcode = MessageCode(jsonline["type"])
        if jsonline["neighbor"]["direction"]:
            if jsonline["neighbor"]["direction"] == "receive":
                encode_msgs = gobgp.Messages(received=gobgp.Message(
                                                        keepalive=msgcode))
            else:
                encode_msgs = gobgp.Messages(sent=gobgp.Message(
                                                    keepalive=msgcode))
        msg = exabgp.ExaKeepalive(local_as=local_as, peer_as=peer_as,
                                  neighbor_address=peer_addr,
                                  speaker_id=speaker_id,
                                  messages=encode_msgs)
        ctlrStub.SendPeerKeepalive(msg, metadata=metadata)

    if jsonline["type"] == "update":
        if "eor" in jsonline["neighbor"]["message"]:
            msgcode = MessageCode(jsonline["type"])
            if jsonline["neighbor"]["direction"]:
                if jsonline["neighbor"]["direction"] == "receive":
                    encode_msgs = gobgp.Messages(received=gobgp.Message(
                                                            update=msgcode))
                else:
                    encode_msgs = gobgp.Messages(sent=gobgp.Message(
                                                        update=msgcode))
            if jsonline["neighbor"]["message"]["eor"]["afi"] == "ipv4":
                afi = gobgp.Family.AFI_IP
            elif jsonline["neighbor"]["message"]["eor"]["afi"] == "ipv6":
                afi = gobgp.Family.AFI_IP6
            else:
                afi = gobgp.Family.UNKNOWN

            if jsonline["neighbor"]["message"]["eor"]["safi"] == "unicast":
                safi = gobgp.Family.SAFI_UNICAST
            elif jsonline["neighbor"]["message"]["eor"]["safi"] == "multicast":
                safi = gobgp.Family.SAFI_MULTICAST
            else:
                safi = gobgp.Family.SAFI_UNKNOWN

            msg = exabgp.ExaUpdateEoR(local_as=local_as, peer_as=peer_as,
                                      neighbor_address=peer_addr,
                                      speaker_id=speaker_id,
                                      messages=encode_msgs,
                                      family=gobgp.Family(afi=afi, safi=safi))
            ctlrStub.SendUpdateEoR(msg, metadata=metadata)
            return

        if "announce" in jsonline["neighbor"]["message"]["update"]:
            msgcode = MessageCode(jsonline["type"])
            if jsonline["neighbor"]["direction"]:
                if jsonline["neighbor"]["direction"] == "receive":
                    encode_msgs = gobgp.Messages(received=gobgp.Message(
                                                            update=msgcode))
                else:
                    encode_msgs = gobgp.Messages(sent=gobgp.Message(
                                                        update=msgcode))
            announce = jsonline["neighbor"]["message"]["update"]["announce"]
            attributes = jsonline["neighbor"]["message"]["update"]["attribute"]
            nexthop = gobgp.NexthopAction()
            nlri = exabgp.ExaNLRI()
            pattrs = []

            for fam, nexthopandnlri in announce.items():
                if fam == "ipv4 unicast":
                    family = gobgp.Family(afi=gobgp.Family.AFI_IP,
                                          safi=gobgp.Family.SAFI_UNICAST)
                if fam == "ipv6 unicast":
                    family = gobgp.Family(afi=gobgp.Family.AFI_IP6,
                                          safi=gobgp.Family.SAFI_UNICAST)

                for nh, NLRI in nexthopandnlri.items():
                    if nh == peer_addr:
                        nexthop.self = True
                    else:
                        nexthop.self = False
                    nexthop.address = nh

                    for dest in NLRI:
                        nlri.prefix.append(dest['nlri'])

            for rattr, value in attributes.items():
                if rattr == "origin":
                    originattr = attrs.OriginAttribute()
                    originattr.origin = OriginCode(value)
                    any_attrs = Any()
                    any_attrs.Pack(originattr)
                    pattrs.append(any_attrs)

                if rattr == "local-preference":
                    localprefattr = attrs.LocalPrefAttribute()
                    localprefattr.local_pref = int(value)
                    any_attrs = Any()
                    any_attrs.Pack(localprefattr)
                    pattrs.append(any_attrs)

                if rattr == "as-path":
                    aspath = attrs.AsPathAttribute()
                    as_set = attrs.AsSegment()
                    as_set.type = int(1)
                    for num in value:
                        as_set.numbers.append(int(num))
                    aspath.segments.append(as_set)
                    any_attrs = Any()
                    any_attrs.Pack(aspath)
                    pattrs.append(any_attrs)

                if rattr == "community":
                    community = attrs.CommunitiesAttribute()
                    for clist in value:
                        for num in clist:
                            community.communities.append(int(num))
                    any_attrs = Any()
                    any_attrs.Pack(community)
                    pattrs.append(any_attrs)

                if rattr == "med":
                    multi_exit = attrs.MultiExitDiscAttribute()
                    multi_exit.med = int(value)
                    any_attrs = Any()
                    any_attrs.Pack(multi_exit)
                    pattrs.append(any_attrs)

            time = Timestamp()
            ts = time.GetCurrentTime()
            msg = exabgp.ExaUpdate(local_as=local_as, peer_as=peer_as,
                                   neighbor_address=peer_addr,
                                   speaker_id=speaker_id,
                                   time=ts,
                                   pattrs=pattrs,
                                   messages=encode_msgs,
                                   nexthop=nexthop,
                                   family=family,
                                   nlri=nlri)
            ctlrStub.SendUpdate(msg, metadata=metadata)
            return
        else:
            msgcode = MessageCode("withdraw")
            if jsonline["neighbor"]["direction"]:
                if jsonline["neighbor"]["direction"] == "receive":
                    encode_msgs = gobgp.Messages(
                            received=gobgp.Message(withdraw_update=msgcode))
                else:
                    encode_msgs = gobgp.Messages(
                            sent=gobgp.Message(withdraw_update=msgcode))
            withdraw = jsonline["neighbor"]["message"]["update"]["withdraw"]
            nlri = exabgp.ExaNLRI()
            for fam, nlri_info in withdraw.items():
                if fam == "ipv4 unicast":
                    family = gobgp.Family(afi=gobgp.Family.AFI_IP,
                                          safi=gobgp.Family.SAFI_UNICAST)
                if fam == "ipv6 unicast":
                    family = gobgp.Family(afi=gobgp.Family.AFI_IP6,
                                          safi=gobgp.Family.SAFI_UNICAST)
                for info in nlri_info:
                    nlri.prefix.append(info["nlri"])
            time = Timestamp()
            ts = time.GetCurrentTime()
            msg = exabgp.ExaUpdate(local_as=local_as, peer_as=peer_as,
                                   neighbor_address=peer_addr,
                                   speaker_id=speaker_id,
                                   time=ts,
                                   messages=encode_msgs,
                                   family=family,
                                   nlri=nlri)
            ctlrStub.SendUpdate(msg, metadata=metadata)
            return


def CreateStub():
    channel = grpc.insecure_channel(target='127.0.0.1:50051',
                                    options=[
                                        ('grpc.keepalive_time_ms',60000),
                                        ('grpc.keepalive_timeout_ms',30000),
                                        ('grpc.keepalive_permit_without_calls',True),
                                        ('grpc.http2.max_pings_without_data',0),
                                        ('grpc.http2.min_time_between_pings_ms',60000),
                                        ('grpc.http2.min_ping_interval_without_data_ms',30000)]
                                   )
    try:
        grpc.channel_ready_future(channel).result(timeout=10)
    except grpc.FutureTimeoutError:
        sys.stderr.write('Error connecting to overwatch controller')
        sys.stderr.flush()
    else:
        stub = exaBGPChannel.ControllerInterfaceStub(channel)
        return stub


def run():
    ctlrStub = CreateStub()
    while True:
        line = sys.stdin.readline().strip()
        jsonline = json.loads(line)
        exaBGPParser(jsonline, ctlrStub)
        sys.stderr.write(str(jsonline) + '\n')
        sys.stderr.flush()


if __name__ == '__main__':
    # print(sys.path)
    run()
