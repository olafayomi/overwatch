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

from copy import deepcopy
import json
import logging
from radix import Radix
from abc import abstractmethod, ABCMeta
from Prefix import Prefix

from CommunityParser import communities_to_tuple_array

# XXX maybe a filter object should require all rules to be True? Still not
# sure I've got this working the right way. Really depends if we want to
# behave the same way as bird, or do our own better thing.

class Filter(object):
    """
    Filter objects combine rules and actions for filtering routes.

    Routes are tested against the rules in the order they were added, until
    a rule returns a successful match, at which point matching terminates.
    If the route matched a rule then any actions associated with this Filter
    are then run, possibly modifying the route.

    Code creating a filter used when exporting routes to a peer that will
    accept only routes in 10.1.2.0/24 or its subnets and will prepend the
    ASN to the AS path might look something like:

        # create an example peer
        peer = BGPPeer(..., default_import=False, default_export=False)

        # create the filter that will accept anything that matches
        filter = Filter("filter 1", onmatch=Filter.ACCEPT)

        # add the rule to match anything in 10.1.2.0/24 or its subnets
        filter.add_rule(PrefixFilterRule("10.1.2.0/24+"))

        # prepend ASN 64496 to any routes that match the rule
        filter.add_action(Filter.PREPEND_ASPATH, 64496)

        # apply the filter to all routes being exported to the peer
        peer.add_export_filter(filter)

    """
    ACCEPT = True
    REJECT = False

    ACCEPT_SYNONYMS = [
        True, "true", "True", "TRUE", ACCEPT, "accept", "Accept", "ACCEPT"
    ]
    REJECT_SYNONYMS = [
        False, "false", "False", "FALSE", REJECT, "reject", "Reject", "REJECT"
    ]

    ADD_COMMUNITY = 0
    REMOVE_COMMUNITY = 1
    PREPEND_ASPATH = 2

    def __init__(self, name="Generic Filter", onmatch=ACCEPT):
        self.name = name
        self.rules = []
        self.actions = []
        self.log = logging.getLogger("Filter")
        if onmatch in Filter.REJECT_SYNONYMS:
            self.onmatch = Filter.REJECT
        else:
            if onmatch not in Filter.ACCEPT_SYNONYMS:
                self.log.warning("Invalid onmatch value, assuming ACCEPT")
            self.onmatch = Filter.ACCEPT

    def __str__(self):
        return "Filter(%s, onmatch=%s, %d rules, %d actions)" % (
                self.name, self.onmatch, len(self.rules), len(self.actions))

    def toJSON(self):
        return json.dumps({
                "name": self.name,
                "onmatch": self.onmatch,
                "rules": len(self.rules),
                "actions": len(self.actions)
        })

    def match(self, route):
        """ Attempt to match the route against all rules in this Filter. """
        for rule in self.rules:
            result = rule.match(route)
            if result is True:
                return self.onmatch
        return None

    def apply(self, route, copy=False):
        """
        Update route with all actions in this Filter, copying if required.
        """
        if len(self.actions) == 0:
            return route

        if copy:
            route_copy = deepcopy(route)
        else:
            route_copy = route

        for action, args in self.actions:
            action(route_copy, args)
        return route_copy

    def add_action(self, action, args):
        """ Add a new action to take should a route match this Filter. """
        if action == self.ADD_COMMUNITY:
            self.actions.append((self._add_communities,
                        communities_to_tuple_array(args)))
        elif action == self.REMOVE_COMMUNITY:
            self.actions.append((self._remove_communities,
                        communities_to_tuple_array(args)))
        elif action == self.PREPEND_ASPATH:
            self.actions.append((self._prepend_aspath, args))
        else:
            self.actions.append(action, args)

    def _add_communities(self, route, communities):
        route.add_communities(communities)

    def _remove_communities(self, route, communities):
        route.remove_communities(communities)

    def _prepend_aspath(self, route, as_path):
        if not isinstance(as_path, list):
            as_path = [as_path]
        route.set_as_path(as_path + route.as_path())

    def add_rule(self, rule):
        """ Add a new rule to this Filter for matching routes """
        self.rules.append(rule)


class FilterRule(object):
    """
    Abstract base class from which all filter rules inherit.
    """
    __metaclass__ = ABCMeta

    def __init__(self, onmatch=True):
        self.log = logging.getLogger("FilterRule")
        if onmatch in Filter.REJECT_SYNONYMS:
            self.onmatch = False
        else:
            if onmatch not in Filter.ACCEPT_SYNONYMS:
                self.log.warning("Invalid onmatch value, assuming TRUE")
            self.onmatch = True

    @abstractmethod
    def match(self, route):
        pass

    @abstractmethod
    def __str__(self):
        pass


class AlwaysMatchRule(FilterRule):
    """
    Always match the route regardless of what the route is.
    """
    def __init__(self, onmatch=True):
        super(AlwaysMatchRule, self).__init__(onmatch)

    def match(self, route):
        return self.onmatch

    def __str__(self):
        return "AlwaysMatchRule(onmatch=%s)" % self.onmatch


class InvertFilterRule(FilterRule):
    """
    Apply the given filter and then invert the match.

    If the given filter matched, it no longer matches. If it failed to get
    a match it is now considered to have succeeded.
    """
    def __init__(self, filter_):
        self.filter = filter_

    def match(self, route):
        result = self.filter.match(route)
        if result is None:
            return self.filter.onmatch
        return None

    def __str__(self):
        return "InvertFilterRule(%s)" % self.filter


class MatchPrefixLengthRule(FilterRule):
    """
    Matches on route prefix length.

    A "+" or "-" suffix will also match longer or shorter prefix lengths
    respectively.
    """
    MATCH = 0
    SHORTER = 1
    LONGER = 2

    def __init__(self, length, onmatch=True):
        if isinstance(length, str) and length.endswith("+"):
            self.length = int(length[:-1])
            self.modifier = self.LONGER
        elif isinstance(length, str) and length.endswith("-"):
            self.length = int(length[:-1])
            self.modifier = self.SHORTER
        else:
            self.length = int(length)
            self.modifier = self.MATCH
        super(MatchPrefixLengthRule, self).__init__(onmatch)

    def match(self, route):
        if self.modifier == self.MATCH:
            if route.prefix.prefixlen == self.length:
                return self.onmatch
        elif self.modifier == self.SHORTER:
            if route.prefix.prefixlen <= self.length:
                return self.onmatch
        elif self.modifier == self.LONGER:
            if route.prefix.prefixlen >= self.length:
                return self.onmatch
        return None

    def __str__(self):
        return "MatchPrefixLengthRule(onmatch=%s, len=%s, modifier=%s)" % (
             self.onmatch, self.length, self.modifier)


class PrefixFilterRule(FilterRule):
    """
    Matches if the route prefix fits any of the given prefix patterns.

    The prefix filter takes patterns similar to the BIRD configuration:

        ipaddress/prefixlen                (exact match)
        ipaddress/prefixlen+               (all subnets)
        ipaddress/prefixlen-               (all supernets)
        ipaddress/prefixlen{low,high}      (all prefixes low <= len <= high)

    See http://bird.network.cz/?get_doc&f=bird-5.html#ss5.2 for more info.

    The approach used is also similar to that used by bird using accept masks
    for prefix length ranges that a prefix will accept, but modified to work
    with py-radix (we don't get to traverse the path ourselves, we just get
    the best matching node).

    See https://gitlab.labs.nic.cz/labs/bird/blob/master/filter/trie.c for info.
    """

    def __init__(self, prefixes, onmatch=True):
        # radix trie holding all the prefixes that this filter will match
        self._rtree = Radix()
        # flag to determine if a zero length prefix should match this filter
        self._zero = False

        if not isinstance(prefixes, list):
            prefixes = [prefixes]

        for item in prefixes:
            # turn the prefix string into a prefix object
            prefix, low, high = self._parse_prefix(item)
            network = prefix.without_netmask() # remove?
            prefixlen = prefix.prefixlen

            if low == 0:
                # flag the trie as accepting zero length prefixes
                self._zero = True
                masklow = low
            else:
                # subtract one so that when xor'd with high the correct bits
                # are set, otherwise we lose one at the bottom end
                masklow = low - 1

            # if the range is below the prefix length we can ignore the
            # remaining bits, they won't ever be checked
            if high < prefixlen:
                prefixlen = high

            # set just the bits that fall in the range we accept
            accept = (prefix.netmask_from_prefixlen(masklow) ^
                    prefix.netmask_from_prefixlen(high))

            # add nodes to match the supernets of the prefix we are adding
            while low < prefixlen and low < high:
                # TODO we can be tighter on what we accept here too?
                self._add_prefix(network, low,
                        accept & prefix.netmask_from_prefixlen(low))
                low += 1

            # add the actual prefix as well
            self._add_prefix(network, prefixlen, accept)

            # roll the new accept mask down to any children of the new node
            children = self._rtree.search_covered(network, prefixlen)
            for child in children:
                if child.prefixlen > prefixlen and child.prefixlen <= high:
                    # TODO we can avoid setting bits shorter than prefixlen?
                    child.data["accept"] |= accept

        super(PrefixFilterRule, self).__init__(onmatch)

    def _add_prefix(self, network, prefixlen, accept):
        # find the best match that exists in the trie already, we might need
        # to merge some accept masks between old and new nodes
        best = self._rtree.search_best(network, prefixlen)
        if best and best.prefixlen == prefixlen:
            # if a node exists, update it with the new accept ranges
            best.data["accept"] |= accept
        else:
            # otherwise create a new node and maybe update it from the parent
            added = self._rtree.add(network, prefixlen)
            added.data["accept"] = accept
            if best:
                # add any accept ranges from the parent to the new node
                # TODO cut off anything shorter than prefixlen?
                added.data["accept"] |= best.data["accept"]

    def __str__(self):
        # TODO tidy up the way prefixes are output
        pstr = self._rtree.prefixes()
        return "PrefixFilterRule(onmatch=%s, prefixes=[%s])" % (
                self.onmatch, pstr)

    def __repr__(self):
        return self.__str__()

    def _parse_prefix(self, prefix):
        if prefix.endswith("+"):
            # strip the '+' and create the prefix with the given netmask
            network = Prefix(prefix[:-1])
            low = network.prefixlen
            high = network.max_prefixlen()
        elif prefix.endswith("-"):
            # strip the '-' and create the prefix with the given netmask
            network = Prefix(prefix[:-1])
            low = 0
            high = network.prefixlen
        elif prefix.endswith("}"):
            # strip the range and create the prefix with the given netmask
            pattern = prefix[prefix.find("{")+1:prefix.find("}")].split(",")
            low = int(pattern[0])
            high = int(pattern[1])
            network = Prefix(prefix[:prefix.find("{")])
        else:
            # create the prefix as given, it needs an exact match
            network = Prefix(prefix)
            low = network.prefixlen
            high = network.prefixlen
        return network, low, high

    def match(self, route):
        # matching prefix length zero is a special case
        if route.prefix.prefixlen == 0:
            return self.onmatch if self._zero else None
        # check the accept ranges in the best (longest) match for this prefix
        rnode = self._rtree.search_best(str(route.prefix))
        bit = 1 << (route.prefix.max_prefixlen() - route.prefix.prefixlen)
        if rnode and rnode.data["accept"] & bit:
            return self.onmatch
        return None


class MartiansFilterRule(PrefixFilterRule):
    """
    Matches if the route prefix belongs to the set of martians.
    """

    def __init__(self, onmatch=True):
        prefixes = [
            "0.0.0.0/8+",           # "this" network
            "10.0.0.0/8+",          # private-use network
            "100.64.0.0/10+",       # carrier-grade NAT
            "127.0.0.0/8+",         # loopback
            "169.254.0.0/16+",      # link local
            "172.16.0.0/12+",       # private-use network
            "192.0.0.0/24+",        # IETF protocol assignments
            "192.0.2.0/24+",        # TEST-NET-1
            "192.168.0.0/16+",      # private-use network
            "198.18.0.0/15+",       # network equipment testing
            "198.51.100.0/24+",     # TEST-NET-2
            "203.0.113.0/24+",      # TEST-NET-3
            "224.0.0.0/4+",         # multicast
            "240.0.0.0/4+",         # future use
            "255.255.255.255/32",   # limited broadcast
            "::1/128",              # loopback
            "::/128",               # unspecified
            "::ffff:0:0/96+",       # ipv4 mapped addresses
            "100::/64+",            # black hole
            "2001::/23+",           # IANA protocol assignments
            "2001:10::/28+",        # ORCHID
            "2001:db8::/32+",       # documentation
            "2002::/16+",           # 6to4 addresses
            "fc00::/7+",            # unique local addresses
            "fe80::/10+",           # link local unicast
            "ff00::/8+",            # multicast (what about ffoe::/16?)
        ]
        super(MartiansFilterRule, self).__init__(prefixes, onmatch)

    def __str__(self):
        return "MartiansFilterRule(onmatch=%s)" % self.onmatch


class CommunityFilterRule(FilterRule):
    """
    Matches if any of the given communities are present for the route.
    """

    def __init__(self, communities, onmatch=True):
        self.communities = communities_to_tuple_array(communities)
        super(CommunityFilterRule, self).__init__(onmatch)

    def match(self, route):
        if route.communities() is None:
            return None
        for community in route.communities():
            if community in self.communities:
                return self.onmatch
        return None

    def __str__(self):
        pstr = ",".join(["(%d,%d)" % x for x in self.communities])
        return "CommunityFilterRule(onmatch=%s, communities=[%s])" % (
            self.onmatch, pstr)


class NoExportFilterRule(CommunityFilterRule):
    """
    Matches on communities that should not be exported.
    """

    def __init__(self, onmatch=True):
        # NO_EXPORT, NO_ADVERTISE, NO_EXPORT_SUBCONFED
        communities = [(65535, 65281), (65535, 65281), (65535, 65283)]
        super(NoExportFilterRule, self).__init__(communities, onmatch)

    def __str__(self):
        return "NoExportFilterRule(onmatch=%s)" % self.onmatch


class PeerFilterRule(FilterRule):
    """
    Matches on the route peer ASN.
    """

    def __init__(self, peers, onmatch=True):
        if not isinstance(peers, list):
            peers = [peers]
        self.peers = peers
        super(PeerFilterRule, self).__init__(onmatch)

    def match(self, route):
        if route.peer in self.peers:
            return self.onmatch
        return None

    def __str__(self):
        pstr = ",".join(["%s" % x for x in self.peers])
        return "PeerFilterRule(onmatch=%s, peers=%s)" % (
            self.onmatch, pstr)


class OriginFilterRule(FilterRule):
    """
    Matches on the route origin (i.e. IGP, EGP, INCOMPLETE)
    """

    def __init__(self, origin, onmatch=True):
        self.origin = origin
        super(OriginFilterRule, self).__init__(onmatch)

    def match(self, route):
        if self.origin == route.origin:
            return self.onmatch
        return None

    def __str__(self):
        return "OriginFilterRule(onmatch=%s, origin=%s)" % (
            self.onmatch, self.origin)
