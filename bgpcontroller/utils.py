#!/usr/bin/python

##########################################################################
# Copyright (C) 2020 Carmine Scarpitta
# (Consortium GARR and University of Rome "Tor Vergata")
# www.garr.it - www.uniroma2.it/netgroup
#
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Utils for node manager
#
# @author Carmine Scarpitta <carmine.scarpitta@uniroma2.it>
#


"""This module contains several utility functions for node manager"""

from ipaddress import AddressValueError, IPv4Interface, IPv6Interface, \
        IPv6Network, IPv4Network, IPv6Address, IPv4Address
from socket import AF_INET, AF_INET6


# Utiliy function to check if the IP
# is a valid IPv6 address
def validate_ipv6_address(address):
    """Return True if the provided IP address is a valid IPv6 address"""

    if address is None:
        return False
    try:
        IPv6Interface(address)
        return True
    except AddressValueError:
        return False


# Utiliy function to check if the IP
# is a valid IPv4 address
def validate_ipv4_address(address):
    """Return True if the provided IP address is a valid IPv4 address"""

    if address is None:
        return False
    try:
        IPv4Interface(address)
        return True
    except AddressValueError:
        return False


# Utiliy function to get the IP address family
def get_address_family(address):
    """Return the family of the provided IP address
    or None if the IP is invalid"""

    if validate_ipv6_address(address):
        # IPv6 address
        return AF_INET6
    if validate_ipv4_address(address):
        # IPv4 address
        return AF_INET
    # Invalid address
    return None


# Utiliy function to check if the IP
# is a valid IP address
def validate_ip_address(address):
    """Return True if the provided IP address
    is a valid IPv4 or IPv6 address"""

    return validate_ipv4_address(address) or \
        validate_ipv6_address(address)


# Check if address is a subnet/network
def validate_ipv6_net(address):
    """Return True if the provided IP is a valid IPv6 network"""

    if validate_ipv6_address(address):
        try:
            IPv6Network(address)
            return True
        except ValueError:
            return False

    return False


def validate_ipv4_net(address):
    """Return True if the provided IP is a valid IPv4 network"""

    if validate_ipv4_address(address):
        try:
            IPv4Network(address)
            return True
        except ValueError:
            return False
    return False


# check if address/net is a subset of another  network
def ipv6_addr_is_subset(addr1, addr2):
    """Return True if addr1 can be found in addr2"""

    if validate_ipv6_net(addr2):
        addr1_validate = validate_ipv6_net(addr1)
        addr_net2 = IPv6Network(addr2)
        if addr1_validate:
            addr_net1 = IPv6Network(addr1)
            val = addr_net2.overlaps(addr_net1)
            return val

        addr1_validate = validate_ipv6_address(addr1)
        if addr1_validate:
            address1 = IPv6Interface(addr1)
            if address1 in addr_net2:
                return True
            else:
                return False
    return False


# Check if two addresses belong to the same subnet
def ipv6_addrs_in_subnet(addr1, addr2):
    """ Return True if both addresses belong to the same subnet"""

    if validate_ipv6_address(addr1) and validate_ipv6_address(addr2):
        int_addr2 = IPv6Interface(addr2)
        int_addr1 = IPv6Interface(addr1)

        if int_addr1.ip in int_addr2.network:
            return True
    return False


def ipv4_addrs_in_subnet(addr1, addr2):
    """ Return True if both addresses belong to the same subnet"""

    if validate_ipv4_address(addr1) and validate_ipv4_address(addr2):
        int_addr2 = IPv4Interface(addr2)
        int_addr1 = IPv4Interface(addr1)

        if int_addr1.ip in int_addr2.network:
            return True
    return False


def ipv4_addr_is_subset(addr1, addr2):
    """Return True if addr1 can be found in addr2"""

    if validate_ipv4_address(addr2):
        addr1_validate = validate_ipv4_net(addr1)
        addr_net2 = IPv4Network(addr2)
        if addr1_validate:
            addr_net1 = IPv4Network(addr1)
            val = addr_net2.overlaps(addr_net1)
            return val

        addr1_validate = validate_ipv4_address(addr1)
        if addr1_validate:
            address1 = IPv4Interface(addr1)
            if address1 in addr_net2:
                return True
            else:
                return False
    return False
