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

from abc import abstractmethod, ABCMeta
from Network import Network

class Routing(object):
    __metaclass__ = ABCMeta

    def __init__(self, address):
        self.topology = None
        self.address = address

    def set_topology(self, topology):
        self.topology = Network(topology)

    @abstractmethod
    def apply(self, all_routes):
        pass


class BGPDefaultRouting(Routing):
    def __init__(self, address):
        super(BGPDefaultRouting, self).__init__(address)
        self.log = logging.getLogger("BGPRouting")

    def apply(self, all_routes):
        loc_rib = {}

        # sort all routes to each prefix by preference
        for prefix in all_routes:
            all_routes[prefix].sort()

        for prefix, routes in all_routes.items():
            # routes are sorted by preference, so pick the first valid one
            for route in routes:
                # make sure there is a path to the nexthop
                if route.nexthop is None:
                    continue
                #if not route.nexthop:
                #    continue
                #if self.asn in route.as_path:
                #    self.log.debug("self in aspath")
                #    continue
                loc_rib[prefix] = [route]
                break
        return loc_rib


class BrendonRouting(Routing):
    def __init__(self, address):
        super(BrendonRouting, self).__init__(address)
        self.log = logging.getLogger("BrendonRouting")

    def apply(self, all_routes):
        loc_rib = {}
        for prefix, routes in all_routes.items():
            loc_rib[prefix] = self._get_best_routes(routes)
        return loc_rib

    def _get_best_routes(self, routes):
        # no topology information, return all the routes
        if self.topology is None:
            return routes

        # find the costs to reach each peer offering this route
        costs = [self.topology.get_path_cost(self.address, route.nexthop)
                 for route in routes]
        #self.log.debug("==========================")
        #self.log.debug(costs)
        #self.log.debug([routes[i] for i, x in enumerate(costs) if x == min(costs)])
        #self.log.debug("==========================")

        # return all the routes that are available for that minimum cost
        return [routes[i] for i, x in enumerate(costs) if x == min(costs)]

#class PARouting(Routing):
#    def __init(self, address):
#        super(PARouting, self).__init__(address)
#        self.log = logging.getLogger("PARouting")
#
#    def apply(self, all_routes):
#        loc_rib  = {}
#        for prefix, routes in all_routes.items():
#
#    def _get_perfaware_routes(self, routes):
#        for route in routes:

