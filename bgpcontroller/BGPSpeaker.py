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

import logging
import json
from copy import deepcopy
from abc import abstractmethod, ABCMeta
from queue import Empty
from ctypes import cdll, byref, create_string_buffer
from collections import defaultdict, OrderedDict
from PolicyObject import PolicyObject, ACCEPT
import time
from multiprocessing import Process, Queue
import attribute_pb2 as attrs
import gobgp_pb2 as gobgp
import exabgp_pb2 as exabgp
from google.protobuf.any_pb2 import Any


class BGPSpeaker(Process):
    __metaclass__ = ABCMeta

    def __init__(self, name, address, speaker_type, peers,
                 command_queue, outgoing_queue, default_import=ACCEPT,
                 default_export=ACCEPT):
        Process.__init__(self, name=name)

        self.log = logging.getLogger("BGPSpeaker")
        self.address = address
        self.speaker_type = speaker_type
        self.command_queue = command_queue
        self.outgoing_queue = outgoing_queue
        self.peers = peers
        self.active = False
        self.degraded = 0
        self.daemon = True
        self.keepalived_time = 0
        self.asn = None
        # self.init_time = 0
        # self.live = False
        self.mailbox = Queue()
        self.actions = {
            "announce": self._process_send_announcement,
            "withdraw": self._process_send_withdrawal,
            "healthcheck": self._process_speaker_healthcheck,
            "peerstate": self._process_peer_state,
            "peercap": self._process_peer_capabilities,
            "update": self._process_receive_update,
            "debug": self._process_debug_message,
        }

    def __str__(self):
        return "BGPSpeaker(%s, address: %s type: %s)"\
            % (self.name, self.address, self.speaker_type)

    def run(self):
        libc = cdll.LoadLibrary("libc.so.6")
        buff = create_string_buffer(len(self.name)+5)
        buff.value = ("foo " + self.name).encode()
        libc.prctl(15, byref(buff), 0, 0, 0)

        callbacks = []

        while True:
            curr_time = time.time()
            if self.keepalived_time != 0:
                time_diff = curr_time - self.keepalived_time
                if time_diff > 120:
                    self._destruct()
         
            try:
                msgtype, message = self.mailbox.get(block=True, timeout=1)
            except Empty:
                for callback, timeout in callbacks:
                    self.log.debug("No recent messages, callback %s triggered" %
                           callback)
                    callback()
                callbacks.clear()
                continue

            while len(callbacks) > 0 and callbacks[0][1] < time.time():
                self.log.debug("Triggering overdue callback %s" % callback)
                callback, timeout = callbacks.pop(0)
                callback()

            if msgtype in self.actions:
                callback = self.actions[msgtype](message)
                if callback and not any(callback == x for x, y in callbacks):
                    callbacks.append((callback, time.time() + 10))
            else:
                self.log.warning("Ignoring unknown message type %s" % msgtype)
            del message

    def _process_receive_update(self, message):
        self.keepalived_time - time.time()
        self.active = True
        peer_addr = message["neighborAddress"]
        peer_asn = message["peerAs"]
        speaker_addr = message["speakerId"]
        speaker_as = message["localAs"]
        update_type = message["messages"]["received"]
        afi, safi = "ipv4", "unicast"
        family = []
        nlri = []
        self.command_queue.put(("healthcheck", {
            "speaker": {
                "address": speaker_addr,
                "asn": speaker_as,
            },
            "status": True,
        }))
        if ('update' in update_type) and ('nlri' in message):
            nexthop = message["nexthop"]["address"]
            pfxs = message["nlri"]["prefix"]
            attribute = {}
            pattrs = message["pattrs"]
            fam = message["family"]
            for attr in pattrs:
                #self.log.info("DIMEJI_DEBUG_BGPSPEAKER _process_receive_update all attributes: %s" % attr)
                if 'localPref' in attr:
                    #self.log.info("DIMEJI_DEBUG_BGPSPEAKER _process_receive_update Local-preference is %s" % attr['localPref'])
                    attribute["local-preference"] = attr['localPref']

                if 'origin' in attr:
                    #self.log.info("DIMEJI_DEBUG_BGPSPEAKER _process_receive_update Origin is %s" % attr['origin'])
                    attribute["origin"] = attr['origin']

                if 'communities' in attr:
                    #self.log.info("DIMEJI_DEBUG_BGPSPEAKER _process_receive_update Communities is %s" % attr['communities'])
                    attribute["community"] = attr['communities']

                if 'segments' in attr:
                    #self.log.info("DIMEJI_DEBUG_BGPSPEAKER _process_recieve_update AS_PATH is %s" % attr['segments'])
                    as_set = []
                    for as_seg in attr['segments']:
                        as_set = as_set + as_seg['numbers']
                    attribute["as-path"] = as_set
        
            for pfx in pfxs:
                nlri.append(pfx)
                #self.log.info("DIMEJI_DEBUG_BGPSPEAKER _process_receive_update prefix is %s" %pfx)
            # XXX: Remove 2001:df8::/48 for now
            #if len(nlri) == 1:
            #    if nlri[0] == '2001:df8::/48':
            #        return
            #else:
            #    index =  nlri.index("2001:df8::/48")
            #    nlri.pop(index)

            if fam['afi'] == 'AFI_IP':
                afi = "ipv4"
            elif fam['afi'] == 'AFI_IP6':
                afi = "ipv6"
            elif fam['afi'] == 'AFI_L2VPN':
                afi = "l2vpn"
            elif fam['afi'] == 'AFI_LS':
                afi = "link-state"
            elif fam['afi'] == 'AFI_OPAQUE':
                afi = "mpls"
            else:
                afi = "unknown"

            if fam['safi'] == 'SAFI_UNICAST':
                safi = "unicast"
            elif fam['safi'] == 'SAFI_MULTICAST':
                safi = "multicast"
            elif fam['safi'] == 'SAFI_MPLS_LABEL':
                safi = "mpls"
            elif fam['safi'] == 'SAFI_VPLS':
                safi = "vpls"
            else:
                safi = "unknown"
            family.append((afi, safi))
            self.command_queue.put(("bgp", {
                "peer": {
                    "address": peer_addr,
                    "asn": peer_asn,
                },
                "update": {
                    "announce": {
                        "nlri": nlri,
                        "family": family,
                        "attribute": attribute,
                        "nexthop": nexthop,
                    },
                },
                "type": "update",
            }))
            return
        # else:
        if ('update' in update_type) and ('nlri' not in message):
            fam = message["family"]
            if fam['afi'] == 'AFI_IP':
                afi = "ipv4"
            elif fam['afi'] == 'AFI_IP6':
                afi = "ipv6"
            elif fam['afi'] == 'AFI_L2VPN':
                afi = "l2vpn"
            elif fam['afi'] == 'AFI_LS':
                afi = "link-state"
            elif fam['afi'] == 'AFI_OPAQUE':
                afi = "mpls"
            else:
                afi = "unknown"

            if fam['safi'] == 'SAFI_UNICAST':
                safi = "unicast"
            elif fam['safi'] == 'SAFI_MULTICAST':
                safi = "multicast"
            elif fam['safi'] == 'SAFI_MPLS_LABEL':
                safi = "mpls"
            elif fam['safi'] == 'SAFI_VPLS':
                safi = "vpls"
            else:
                safi = "unknown"
            family.append((afi, safi))
            self.command_queue.put(("bgp", {
                "peer": {
                    "address": peer_addr,
                    "asn": peer_asn,
                },
                "eor": {
                    "family": family,
                },
                "type": "update",
            }))
            return

        if 'withdrawUpdate' in update_type:
            pfxs = message["nlri"]["prefix"]
            fam = message["family"]
            for pfx in pfxs:
                nlri.append(pfx)

            # XXX: Remove 2001:df8::/48 for now
            #if len(nlri) == 1:
            #    if nlri[0] == '2001:df8::/48':
            #        return
            #else:
            #    index =  nlri.index("2001:df8::/48")
            #    nlri.pop(index)

            if fam['afi'] == 'AFI_IP':
                afi = "ipv4"
            elif fam['afi'] == 'AFI_IP6':
                afi = "ipv6"
            elif fam['afi'] == 'AFI_L2VPN':
                afi = "l2vpn"
            elif fam['afi'] == 'AFI_LS':
                afi = "link-state"
            elif fam['afi'] == 'AFI_OPAQUE':
                afi = "mpls"
            else:
                afi = "unknown"

            if fam['safi'] == 'SAFI_UNICAST':
                safi = "unicast"
            elif fam['safi'] == 'SAFI_MULTICAST':
                safi = "multicast"
            elif fam['safi'] == 'SAFI_MPLS_LABEL':
                safi = "mpls"
            elif fam['safi'] == 'SAFI_VPLS':
                safi = "vpls"
            else:
                safi = "unknown"
            family.append((afi, safi))
            self.command_queue.put(("bgp", {
                "peer": {
                    "address": peer_addr,
                    "asn": peer_asn,
                },
                "update": {
                    "withdraw": {
                        "nlri": nlri,
                        "family": family,
                    },
                },
                "type": "update",
            }))
            return

    def _process_peer_state(self, message):
        self.keepalived_time = time.time()
        self.active = True
        peer_addr = message["neighborAddress"]
        peer_asn = message["peerAs"]
        speaker_addr = message["speakerId"]
        speaker_as = message["localAs"]
        if ("sessionState" in message):
            if peer_addr in self.peers:
                state = message["sessionState"]
                if state != "ESTABLISHED":
                    self.command_queue.put(("bgp", {
                        "peer": {
                            "address": peer_addr,
                            "asn": peer_asn,
                        },
                        "type": "state",
                        "state": "down",
                    }))
        else:
            # state is established
            if peer_addr in self.peers:
                state = "ESTABLISHED"
                self.command_queue.put(("bgp", {
                    "peer": {
                        "address": peer_addr,
                        "asn": peer_asn,
                    },
                    "type": "state",
                    "state": "up",
                }))

        self.command_queue.put(("healthcheck", {
            "speaker": {
                "address": speaker_addr,
                "asn": speaker_as,
            },
            "status": True,
        }))
        return

    def _process_peer_capabilities(self, message):
        self.keepalived_time = time.time()
        self.active = True
        peer_addr = message["neighborAddress"]
        peer_asn = message["peerAs"]
        speaker_addr = message["speakerId"]
        speaker_as = message["localAs"]
        if "received" not in message["messages"]:
            return

        direction = "receive"
        caps = message["capabilities"]

        if peer_addr not in self.peers:
            self.log.info("Open message received from unknown peer %s" % peer_addr)
            return

        afi, safi, addpathmode = "ipv4", "unicast", "None"
        routerefreshcap, gracefulrestart, multiproto = False, False, []
        longlivedgracefulrestart, fouroctet = False, False
        for capName, capValue in caps.items():
            if capName == 'routerefreshcap':
                routerefreshcap = True

            if capName == 'gracefulrestartcap':
                gracefulrestart = True

            if capName == 'fouroctetascap':
                fouroctet = True

            if capName == 'longlivedgracefulrestartcap':
                longlivedgracefulrestart = True

            if capName == 'addpathcap':
                if "tuples" in capValue:
                    mode = capValue["tuples"][0]["mode"]
                    if mode == 'MODE_BOTH':
                        addpathmode = "BOTH"
                    elif mode == 'MODE_RECEIVE':
                        addpathmode = "RECEIVE"
                    elif mode == 'MODE_SEND':
                        addpathmode = "SEND"
                    else:
                        addpathmode = "NONE"
                else:
                    addpathmode = "NONE"

            if capName == 'multiprotocolcap':
                for family in capValue:
                    addrfam = family["family"]["afi"]
                    safifam = family["family"]["safi"]
                    if addrfam == 'AFI_IP':
                        afi = "ipv4"
                    elif addrfam == 'AFI_IP6':
                        afi = "ipv6"
                    elif addrfam == 'AFI_L2VPN':
                        afi = "l2vpn"
                    elif addrfam == 'AFI_LS':
                        afi = "link-state"
                    elif addrfam == 'AFI_OPAQUE':
                        afi = "mpls"
                    else:
                        afi = "unknown"

                    if safifam == 'SAFI_UNICAST':
                        safi = "unicast"
                    elif safifam == 'SAFI_MULTICAST':
                        safi = "multicast"
                    elif safifam == 'SAFI_MPLS_LABEL':
                        safi = "mpls"
                    elif safifam == 'SAFI_VPLS':
                        safi = "vpls"
                    else:
                        safi = "unknown"
                    multiproto.append((afi, safi))
        self.command_queue.put(("bgp", {
            "peer": {
                "address": peer_addr,
                "asn": peer_asn,
            },
            "type": "open",
            "direction":  direction,
            "capabilities": {
                "routerefreshcap": routerefreshcap,
                "gracefulrestart": gracefulrestart,
                "multiprotocol": multiproto,
                "longlivedgracefulrestart": longlivedgracefulrestart,
                "fouroctet": fouroctet,
                "addpath": addpathmode,
            }}))
        self.command_queue.put(("healthcheck", {
            "speaker": {
                "address": speaker_addr,
                "asn": speaker_as,
            },
            "status": True,
        }))
        return

    def _process_send_announcement(self, message):
        if message["peer"] not in self.peers:
            return

        bgpmsg = exabgp.ControllerToBGP()
        bgpmsg.peer_as = message["asn"]
        bgpmsg.neighbor_address = message["peer"]
        bgpmsg.msgtype = 0
        nh = gobgp.NexthopAction()
        nlri = exabgp.ExaNLRI()
        nlri.prefix.append(str(message["route"]["nlri"]))
        bgpmsg.nlri.MergeFrom(nlri)
        if message["route"]["nexthop"] == self.address:
            nh.self = True
            nh.address = self.address
        else:
            nh.self = False
            nh.address = message["route"]["nexthop"]
        bgpmsg.nexthop.MergeFrom(nh)

        if "origin" in message["route"]:
            any_attrs = Any()
            originattr = attrs.OriginAttribute()
            # zero value are not sent over the wire and origin value for igp is 0
            # set igp to something else
            if message["route"]["origin"] == 0:
                originattr.origin =  int(3)
            else:
                originattr.origin = int(message["route"]["origin"])
            any_attrs.Pack(originattr)
            bgpmsg.pattrs.append(any_attrs)

        if "aspath" in message["route"]:
            anypack = Any()
            aspath = attrs.AsPathAttribute()
            as_seg = attrs.AsSegment()
            as_seg.type = int(1)
            paths = message["route"]["aspath"]
            
            self.log.info("DIMEJI_DEBUG_BGPSPEAKER _process_send_announcement paths is %s" % paths)
            self.log.info("DIMEJI_DEBUG_BGPSPEAKER _process_send_announcemnt paths is type %s" % type(paths))
          
            for asn in paths:
                as_seg.numbers.append(int(asn))
            aspath.segments.append(as_seg)
            anypack.Pack(aspath)
            bgpmsg.pattrs.append(anypack)

        if "communities" in message["route"]:
            anycomm = Any()
            commattr = attrs.CommunitiesAttribute()
            communities = message["route"]["communities"]
            self.log.info("DIMEJI_DEBUG_BGPSPEAKER _process_send_announcement communities is %s" % communities)
            self.log.info("DIMEJI_DEBUG_BGPSPEAKER _process_send_announcement communities is type %s" % type(communities))
            if communities is not None:
                for community in communities:
                    for num in community:
                        commattr.communities.append(int(num))
                anycomm.Pack(commattr)
                bgpmsg.pattrs.append(anycomm)
        self.outgoing_queue.put(bgpmsg)
        return

    def _process_send_withdrawal(self, message):
        if message["peer"] not in self.peers:
            return
        bgpmsg = exabgp.ControllerToBGP()
        bgpmsg.peer_as = message["asn"]
        bgpmsg.neighbor_address = message["peer"]
        bgpmsg.msgtype = 1
        nh = gobgp.NexthopAction()
        nlri = exabgp.ExaNLRI()
        nlri.prefix.append(str(message["route"]["nlri"]))
        bgpmsg.nlri.MergeFrom(nlri)
        if message["route"]["nexthop"] == self.address:
            nh.self = True
            nh.address = self.address 
        else:
            nh.self = False
            nh.address = message["route"]["nexthop"]
        bgpmsg.nexthop.MergeFrom(nh)
        #self.outgoing_queue.put(msg.SerializeToString())
        self.outgoing_queue.put(bgpmsg)
        return

    def _process_speaker_healthcheck(self, message):
        # Received a keepalive message, set process to live
        self.keepalived_time = time.time()
        self.active = True
        peer_addr = message["neighborAddress"]
        peer_asn = message["peerAs"]
        speaker_addr = message["speakerId"]
        speaker_as = message["localAs"]
        self.asn = message["localAs"]
        if peer_addr in self.peers:
            self.command_queue.put(("bgp", {
                "peer": {
                    "address": peer_addr,
                    "asn": peer_asn,
                },
                "type": "state",
                "state": "up",
            }))
            self.command_queue.put(("healthcheck", {
                "speaker": {
                    "address": speaker_addr,
                    "asn": speaker_as,
                },
                "status": True,
            }))
            return
        else:
            self.log.info("Keepalive message received from unknown peer %s" % peer_addr)
            return

    def _process_debug_message(self, message):
        self.log.debug(self)
        return None

    def _destruct(self):
        # Tell the controller and peers that speaker is down
        self.command_queue.put(("healthcheck", {
            "speaker": {
                "address": self.address,
                "asn": self.asn,
                "peers": self.peers,
            },
            "status": False,
        }))
        self.active = False
        return

