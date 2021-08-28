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

class DPRouteTable(object):
    """
        An object that defines the route tables created on the dataplane of the peers
        managed by overwatch.
    """ 

    def __init__(self, name, number):
        self.name = name
        self.num = number
        self.route = [] 


    def __str__(self):
        return "DataplaneRouteTable(%s, number=%s)" %(self.name, self.num)


class DPFlowMarking(object): 
    """
        An object for holding ip rules and ip6tables for marking ingress flows
    """

    def __init__(self, fwmark, protocol, port, ifname, table_no):
        self.fwmark = fwmark
        self.protocol = protocol
        self.port = port
        self.ingress = ifname
        self.table = table_no


    def __str__(self):
        return "DPFlowMarking(%s, fwmark=%s, protocol=%s, port=%s, ingress=%s, table=%s)" %(
                self.fwmark, self.protocol, self.port, self.ingress, self.table)

    
