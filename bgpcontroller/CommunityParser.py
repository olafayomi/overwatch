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

"""
    Module that defines helper methods to allow converting a community
    to an appropriate type for route processing and filter storage.

    The required type is a list of tuples integers, i.e. [(int, int), (int, int)

    The conversion method accepts an array or single element of communities.
    A community can be in the form in the form:
        [*, *]
        (*, *)
        str             <-- In the format NUMBER:NUMBER

        * = Any type that is accepted by the int() conversion method

    Please note that an array of integers or numerics (i.e not str) will be
    interpreted as a single community element, i.e. (1,2) will result in
    [(1,2)] once processed!

    If the format of the community is unknown, i.e. not in the above format
    an exception will be thrown.
"""

def communities_to_tuple_array(communities):
    data = []
    if isinstance(communities, list):
        if len(communities) == 0:
            return data

        # If we have a list of strings, tuples or lists process the individual
        # list elements
        if (isinstance(communities[0], str) or
                isinstance(communities[0], tuple) or
                isinstance(communities[0], list)):
            for community in communities:
                data.append(_community_to_tuple(community))
        # Otherwise process a single community as a single list object
        else:
            data.append(_community_to_tuple(communities))

    else:
        data.append(_community_to_tuple(communities))

    return data

def _community_to_tuple(community):
    # Parse and convert a community string to a tuple
    if isinstance(community, str):
        parts = community.split(":")
        if len(parts) != 2:
            raise Exception("Community: only one separator (:) allowed (%s)" %
                    (community))

        try:
            return (int(parts[0]), int(parts[1]))
        except ValueError:
            raise Exception("Community: expected format NUMBER:NUMBER (%s)" %
                    (community))
    # Convert a community array to a tuple
    elif isinstance(community, list):
        if len(community) != 2:
            raise Exception("Community: too many elements (%s)" % (community))

        try:
            return (int(community[0]), int(community[1]))
        except ValueError:
            raise Exception("Community: could not convert to integer (%s)" %
                    (community))
    elif isinstance(community, tuple):
        try:
            return (int(community[0]), int(community[1]))
        except ValueError:
            raise Exception("Community: could not convert to integer (%s:%s)" %
                    (community))
    else:
        raise Exception("Community: %s is unknown type %s" %
                (community, type(community).__name__))
