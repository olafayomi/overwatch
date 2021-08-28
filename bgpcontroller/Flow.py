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


from Prefix import Prefix
from RouteEntry import RouteEntry, DEFAULT_LOCAL_PREF
import utils 


class Flow(object):
    """
        An object that defines all the necessary information
        that the PARTrafficModule needs to share with controller
        and maintain about the flow to a set of destinations that
        are currently being performance-aware routed
    """

    def __init__(self, name, protocol, port, prefixes):
        self.name = name
        self.protocol = protocol
        self.port = port
        self.rtable  = 0 
        self.routes = {}
        for prefix in prefixes:
            p = Prefix(prefix)
            self.routes[p] = None


    def __str__(self):
        return "Flow(%s, protocol=%s, port=%s, table=%s)" % (
                self.name, self.protocol, self.port, self.rtable)


    def update_best_route(self, prefix, route):
        if prefix in self.routes: 
            self.routes[prefix] = route


    def update_routetable(self, table_no):
        self.rtable = table_no


    def get_protocol(self):
        return (self.protocol, self.port)


    def get_route(self, prefix, route):
        if prefix in self.routes:
            return self.routes[prefix]

    def check_prefix(self, prefix):
        if prefix in self.routes:
            return True
        else:
            return False

