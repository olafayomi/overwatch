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

from Peer import Peer
from PolicyObject import ACCEPT
from Prefix import Prefix
from RouteEntry import RouteEntry, DEFAULT_LOCAL_PREF, ORIGIN_EGP
import messages_pb2 as pb


class BGPPeer(Peer):
    def __init__(self, name, asn, address, outgoing_queue, control_queue,
            internal_command_queue,
            preference=DEFAULT_LOCAL_PREF,
            default_import=ACCEPT,
            default_export=ACCEPT):

        super(BGPPeer, self).__init__(name, asn, address, control_queue,
                internal_command_queue, preference, default_import,
                default_export)

        self.log = logging.getLogger("BGPPeer")
        self.out_queue = outgoing_queue

        self.seen_eor = False
        self.actions.update({
            pb.Message.BGP: self._process_bgp_message,
        })

        # Do not export or process anything until we know the peers
        # capabilities. We should not receive an exaBGP route update before
        # the negotiated message. The negotiated message will cause us to
        # send a request to our tables to reload their routes to us.
        self.afi_safi = []

    def __cmp__(self, other):
        if self.asn > other.asn:
            return 1
        if self.asn < other.asn:
            return -1
        if self.address > other.address:
            return 1
        if self.address < other.address:
            return -1
        return 0

    def _afi_safi_to_str(self, afi, safi):
        """
            Convert a pair of AFI SAFI numeric values to their exaBGP
            name representation
        """
        name = ""
        if afi == 1:
            name = "ipv4"
        elif afi == 2:
            name = "ipv6"

        if safi == 1:
            name += " unicast"
        elif safi == 2:
            name += " multicast"
        elif safi == 4:
            name += " nlri-mpls"
        elif safi == 128:
            name += " mpls-vpn"
        return name

    def _str_to_afi_safi(self, name):
        """
            Convert an exabgp afi safi string to numeric values
        """
        parts = name.split(" ")
        afi = 0
        safi = 0

        if parts[0] == "ipv4":
            afi = 1
        elif parts[0] == "ipv6":
            afi = 2

        if parts[1] == "unicast":
            safi = 1
        elif parts[1] == "multicast":
            safi = 2
        return (afi, safi)

    def _do_announce(self, prefix, route):
        # TODO origin, aggregator/atomic-aggregate attributes
        # TODO use attributes/nlri announce many routes with same attributes
        #    "announce attribute next-hop self community [] nlri 1.2.3.4/32"
        #self.log.debug("announce %s", prefix)
        announce = "neighbor %s announce route %s next-hop %s %s %s" % (
                    self.address,
                    prefix, route.nexthop, route.get_announce_as_path_string(),
                    route.get_announce_communities_string())
        # this queue is just raw bytes, not packed inside a protobuf message
        self.out_queue.put(bytes(announce, "utf-8"))

    def _do_withdraw(self, prefix, route):
        #self.log.debug("withdraw %s", prefix)
        withdraw = "neighbor %s withdraw route %s next-hop %s" % (
                    self.address, prefix, route.nexthop)
        self.out_queue.put(bytes(withdraw, "utf-8"))

    def _process_bgp_message(self, message):
        try:
            message = json.loads(message.bgp.json)
        except json.JSONDecodeError as e:
            self.log.error("Invalid json in ExaBGP message, ignoring")
            return None

        assert(message["neighbor"]["address"]["peer"] == self.address)
        assert(message["neighbor"]["asn"]["peer"] == self.asn)

        if message["type"] == "state":
            callback = self._process_state_message(message)
        elif message["type"] == "notification":
            callback = self._process_notification_message(message)
        elif message["type"] == "update":
            callback = self._process_update_message(message)
        elif message["type"] == "open":
            callback = self._process_open_message(message)
        elif message["type"] == "refresh":
            callback = self._process_refresh_message(message)
        elif message["type"] == "negotiated":
            callback = self._process_negotiated_message(message)
        else:
            self.log.warning("Unknown BGP message type: %s", message["type"])
            callback = None
        return callback

    def _process_state_message(self, message):
        """
            Process and handle bgp state messages.
        """
        self.log.debug("Peer %s state change: %s", self.name,
                message["neighbor"]["state"])
        # TODO deal with graceful restart
        # tell the controller that we have changed state so that it can alert
        # other peers about it
        if message["neighbor"]["state"] == "up":
            self._state_change(True)
        elif message["neighbor"]["state"] == "down":
            self._state_change(False)
        return None

    def _process_notification_message(self, message):
        """
            Process and handle bgp notification messages
        """
        self.log.debug("Peer %s notification: %s", self.name, message)
        return None

    def _process_withdraw_prefixes(self, family, update):
        """
            Process the withdraw BGP prefixes for a specified family. Please
            note that this method doesn't validate if the family exists
            as the caller should have already done this. Return true if
            prefix changes occurred.
        """
        prefixes = update["withdraw"][family]

        empty = []
        for withdrawn in prefixes:
            withdrawn = withdrawn["nlri"]
            withdrawn_prefix = Prefix(withdrawn)
            # a peer can remove supernets that don't explicitly exist, so we
            # need to check if a prefix is contained within the withdrawn one
            for route in self.received:
                if withdrawn_prefix.contains(route.prefix):
                    # remove any routes that fall within the prefix
                    empty.append(route)

        # remove prefixes that no longer have routes
        for route in empty:
            self.received.remove(route)

        return len(prefixes) > 0

    def _process_announce_prefixes(self, family, update):
        """
            Process the announced BGP prefixes for a specified family. Please
            note that this method doesn't validate if the family exists
            as the caller should have already done this. Return true if
            prefix changes occurred.
        """
        announce = update["announce"][family]

        if "null" in announce and \
            "eor" in announce["null"]:
            # TODO see also restart flags that say not to wait for EOR
            self.seen_eor = True
            return True

        if "attribute" not in update:
            return False

        as_path = update["attribute"].get("as-path", [])
        as_set = update["attribute"].get("as-set", [])
        communities = update["attribute"].get("community", [])

        for nexthop, prefixes in announce.items():
            # XXX nexthop is currently just a string
            for prefix in prefixes:
                prefix = prefix["nlri"]
                route = RouteEntry(ORIGIN_EGP, self.asn,
                        str(prefix), str(nexthop), as_path, as_set,
                        communities, self.preference)
                # check if the route passes filters before we store it
                if self.filter_import_route(route):
                    self.received.append(route)
        return len(announce) > 0

    def _process_bgp_update_section(self, update, section_name, func):
        """
            Process a BGP update specific for specific AFI SAFI prefix
            families as defined by the peer. This method returns True if
            an update occurred, false otherwise. If the update section
            doesn't exist in the update message false is returned.

            For every family that exists in the update section the function
            func will be executed and the status for all families returned.
        """
        status = False

        if section_name not in update:
            return False

        # Process the message for negotiated AFI/SAFI values
        section = update[section_name]
        for family in self.afi_safi:
            # Convert the tuple to a exaBGP afi safi string value
            family = self._afi_safi_to_str(family[0], family[1])
            if family in section:
                if func(family, update):
                    status = True
        return status

    def _can_import_prefix(self, prefix):
        """
            Check if a prefixes AFI/SAFI is in our AFI/SAFI list. If not
            return False (can't import prefix from table) otherwise return
            true (import prefix from table)
        """

        # XXX: If the peer has just started up (no negotiated message) we will
        # not import any prefixes. When the negotiated message is received we
        # will re-ask the tables for routes sending a reload command.
        for afi, safi in self.afi_safi:
            if afi == prefix.afi() and safi == prefix.safi():
                return True
        return False

    def _process_update_message(self, message):
        # update timing metrics to track when messages were received
        if len(self.received) == 0:
            self.metrics["peer_first_import_timestamp"].set_to_current_time()
        self.metrics["peer_last_import_timestamp"].set_to_current_time()

        # update metrics to track how long we took to process the message
        with self.metrics["peer_process_bgp_update_duration"].time():
            update = message["neighbor"]["message"].get("update", None)
            withdrawn = False
            announced = False

            # Process EoR messages if there is no update
            # XXX: assumes that we will not get an update and eor in message
            if update is None:
                eor_section = message["neighbor"]["message"].get("eor", None)
                if eor_section is not None:
                    self.seen_eor = True
                    announced = True
                    self.log.debug("%s seen eor for AFI %s and SAFI %s",
                            self.name, eor_section["safi"], eor_section["afi"])
            else:
                withdrawn = self._process_bgp_update_section(update, "withdraw",
                        self._process_withdraw_prefixes)
                announced = self._process_bgp_update_section(update, "announce",
                        self._process_announce_prefixes)

            # record the number of routes that we have received
            self.metrics["peer_prefix_accepted_current"].set(len(self.received))

            # if anything changed then just send all the routes we have
            if self.seen_eor and (withdrawn or announced):
                self.metrics["peer_prefix_received_current"].set(
                        len(self.received))
                # send filtered routes to the route tables
                self.log.debug("Updating %s peer tables", self.name)
                return self._update_tables_with_routes
        return None

    def _process_open_message(self, message):
        # if the EoR is not one form our peer ignore it
        if message["neighbor"]["direction"] != "receive":
            return None

        self.log.debug("Received peer %s open message", self.name)

        # Check if the GR capability is advertised
        if "64" in message["neighbor"]["open"]["capabilities"]:
            self.seen_eor = False
            self.log.debug("Peer %s advertised GR capability, waiting for EoR",
                    self.name)
        else:
            self.seen_eor = True
            self.log.debug("Peer %s lacks GR capability, disabling EoR wait",
                    self.name)

        # TODO: Do capability processing once GR support is implemented
        # If capability 64 is advertised but no AFI or SAFI is present then
        # peer will send us EoR but is not GR capable.
        return None

    def _process_negotiated_message(self, message):
        # Parse the peers negotiated AFI SAFI from the message
        negotiated = message["neighbor"].get("negotiated", None)
        if negotiated:
            if "families" in negotiated:
                self.afi_safi = []
                for family in negotiated["families"]:
                    self.afi_safi.append(self._str_to_afi_safi(family))
                self.log.debug("%s negotiated msg received, AFI SAFI %s",
                        self.name, self.afi_safi)

                # Ask the tables that are exporting to us to resend their routes
                # XXX can we remove the need for this if they haven't sent us
                # anything useful yet?
                self._reload_from_tables()
        return None

    def _process_refresh_message(self, message):
        # TODO check that AFI/SAFI are valid?
        # TODO do enhanced route refresh (RFC 7313) if peer is capable
        self._do_export_routes(refresh=True)
        # TODO does this need to be delayed? if so make a new function to do it
        # cause we can't pass arguments around
        return None