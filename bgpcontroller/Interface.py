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

class Interface(object):
    """
        An object that defines each interface in the dataplane of the peers
        managed by overwatch. 
    """

    def __init__(self, ifname, ifindex, state, neighbours, addresses):
        self.ifname = ifname 
        self.ifindex = ifindex 
        self.state = state 
        self.neighbours = neighbours 
        self.internal = None
        self.addresses = addresses


    def __str__(self):
        return "Interface(%s, index=%s, addresses=%s, state=%s, internal=%s)" % (
                self.ifname, self.ifindex, self.addresses, self.state, self.internal)


    def set_internal(self, boolval): 
        self.internal = boolval

