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

def communities_to_tuple_array (communities):
    data = []
    if isinstance(communities, list):
        if len(communities) == 0:
            return data

        # If we have a list of strings, tuples or lists process the individual list elements
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

def _community_to_tuple (community):
    # Parse and convert a communtiy string to a tuple
    if isinstance(community, str):
        com_split = community.split(":")
        if not len(com_split) == 2:
            raise Exception("Community Parser: community string can only have one seperator (:), %s" %
                    (community))

        try:
            com_numA = int(com_split[0])
            com_numB = int(com_split[1])
            return (com_numA, com_numB)
        except ValueError:
            raise Exception("Community Parser: community string %s needs to have format NUMBER:NUMBER" %
                    (community))
    # Convert a community array to a tuple
    elif isinstance(community, list):
        if not len(community) == 2:
            raise Exception("Community Parser: community %s can only have 2 items in its array" %
                    (community))

        try:
            com_numA = int(community[0])
            com_numB = int(community[1])
            return (com_numA, com_numB)
        except ValueError:
            raise Exception("Community Parser: community array items %s could not be converted to an integer" %
                    (community))
    elif isinstance(community, tuple):
        try:
            com_numA = int(community[0])
            com_numB = int(community[1])
            return (com_numA, com_numB)
        except ValueError:
            raise Exception("Community Parser: community tuple items (%s, %s) could not be converted to an integers" %
                    (community))
    else:
        raise Exception("Community Parser: unkown type of community %s, found type %s" %
                (community, type(community).__name__))

