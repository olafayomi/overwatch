// Copyright (c) 2020, WAND Network Research Group
//                     Department of Computer Science
//                     University of Waikato
//                     Hamilton
//                     New Zealand
//
// This program is free software; you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program; if not, write to the Free Software
// Foundation, Inc., 59 Temple Place, Suite 330,
// Boston,  MA 02111-1307  USA
//
// @Author : Brendon Jones (Original Disaggregated Router)
// @Author : Dimeji Fayomi

#include <stdlib.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netdb.h>
#include <arpa/inet.h>
#include <stdio.h>
#include "Prefix.h"


// ==================== HELPER METHODS ======================


/*
 * Wrap strtol() to more easily check for errors parsing. Any characters
 * that aren't valid in the given base will result in an error. Returns -1
 * on failure.
 */
static int process_number(char *token) {
    int value;
    char *endptr = NULL;
    errno = 0;
    value = strtol(token, &endptr, 10);

    /* any error, empty string or remaining characters is an error */
    if ( errno != 0 || token == endptr || *endptr != '\0' ) {
        return -1;
    }

    return value;
}


// ========================= IPV4 ===========================


/* ---- (PYTHON) Initialisation and cleaning functions ---- */


/*
 * Create a new IPv4 object and set fields to default values
 */
static PyObject *IPv4_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
    IPv4 *self;
    self = (IPv4 *)type->tp_alloc(type, 0);
    if ( self != NULL ) {
        self->ip = 0;
        self->prefixlen = IPV4_PREFIX_LEN_MAX;
    }

    return (PyObject *)self;
}


/*
 * Wrap getaddrinfo() to convert a string containing an IP address into a
 * struct addrinfo we can later extract the address from.
 */
static struct addrinfo* parse_address(char *address) {
    struct addrinfo hint;
    struct addrinfo *addrinfo;

    memset(&hint, 0, sizeof(struct addrinfo));
    hint.ai_flags = AI_NUMERICHOST;
    hint.ai_family = PF_UNSPEC;
    hint.ai_socktype = SOCK_STREAM; /* limit it to a single socket type */
    hint.ai_protocol = 0;
    hint.ai_addrlen = 0;
    hint.ai_addr = NULL;
    hint.ai_canonname = NULL;
    hint.ai_next = NULL;
    addrinfo = NULL;

    if ( getaddrinfo(address, NULL, &hint, &addrinfo) != 0 ) {
        return NULL;
    }

    return addrinfo;
}


/*
 * Initialise a new IPv4 prefix object.
 *
 * Expects an IPv4 address string in dotted quad notation (with or without
 * a prefix length) and an optional separate prefix length argument. If no
 * prefix length is given (through either argument), it defaults to 32.
 *
 * The optional prefixlength argument will take precedence over any length
 * given as part of the IP address string.
 */
static int IPv4_init(IPv4 *self, PyObject *args, PyObject *kwds) {
    static char *kwlist[] = {"ip", "prefixlen", NULL};
    char *ip_arg = NULL;
    int prefixlen_arg = -1;
    char *addrstr;
    char *prefixstr;
    char *fullstr;
    char *dotptr;
    struct addrinfo *addrinfo;
    int dots;

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "s|i", kwlist, &ip_arg,
                &prefixlen_arg)) {
        return -1;
    }

    /* make a copy so that we don't destroy the original python string */
    fullstr = strdup(ip_arg);

    /* split the address string on the '/' to separate address and prefixlen */
    addrstr = strtok(fullstr, "/");
    prefixstr = strtok(NULL, "/");

    /*
     * getaddrinfo()/inet_aton() will accept integers or outdated formats
     * based around classful addressing, but we don't want to accept anything
     * that isn't a proper dotted quad. Guess we count the number of dots.
     */
    dots = 0;
    dotptr = addrstr;
    while ( (dotptr = strchr(dotptr, '.')) != NULL ) {
        dots++;
        dotptr++;
    }

    if ( dots != 3 ) {
        PyErr_SetString(PyExc_ValueError, "Invalid IP address format.");
        free(fullstr);
        return -1;
    }

    /* try to convert the address string into a struct addrinfo */
    addrinfo = parse_address(addrstr);

    if ( addrinfo == NULL ) {
        PyErr_SetString(PyExc_ValueError, "Invalid IP address format.");
        free(fullstr);
        return -1;
    }

    self->ip = ntohl(((struct sockaddr_in*)addrinfo->ai_addr)->sin_addr.s_addr);
    freeaddrinfo(addrinfo);

    /* prefer to use the prefixlen_arg, though it might not be set */
    if ( prefixlen_arg == -1 ) {
        if ( prefixstr != NULL ) {
            /* otherwise try to extract prefix length from the address string */
            prefixlen_arg = process_number(prefixstr);
        } else {
            /* failing that, set the prefix length to 32 */
            prefixlen_arg = IPV4_PREFIX_LEN_MAX;
        }
    }

    free(fullstr);

    /* check that the prefix length falls within the expected range */
    if ( prefixlen_arg < 0 || prefixlen_arg > IPV4_PREFIX_LEN_MAX ) {
        PyErr_SetString(PyExc_ValueError, "Invalid prefix length");
        return -1;
    }

    self->prefixlen = (uint8_t)prefixlen_arg;

    return 0;
}


/*
 * Clean-up method called to deallocate used resources
 */
static void IPv4_dealloc(IPv4 *self) {
    Py_TYPE(self)->tp_free((PyObject*)self);
}


/* ---- (PYTHON) Builtin functions ---- */


/*
 * Rich comparator method that compares two objects and returns a result
 */
static PyObject *IPv4_richcmp(PyObject *obj1, PyObject *obj2, int operator) {
    int compare_result;
    int compare_raw;

    /* Validate the type of the objects we are comparing */
    if ( !PyObject_IsInstance(obj1, (PyObject*)&IPv4Type) ) {
        PyErr_SetString(PyExc_AttributeError,
                "Can only compare prefix objects");
        return NULL;
    }

    if ( !PyObject_IsInstance(obj2, (PyObject*)&IPv4Type) &&
            !PyObject_IsInstance(obj2, (PyObject*)&IPv6Type) ) {
        PyErr_SetString(PyExc_AttributeError,
                "Can only compare prefix objects");
        return NULL;
    }

    /* Determine the ordering of the two objects */
    compare_raw = IPv4_compare(obj1, obj2);

    /* Check if the ordering matches what the comparison operator wanted */
    switch ( operator ) {
        case Py_LT: compare_result = compare_raw < 0; break;
        case Py_LE: compare_result = compare_raw <= 0; break;
        case Py_EQ: compare_result = compare_raw == 0; break;
        case Py_NE: compare_result = compare_raw != 0; break;
        case Py_GT: compare_result = compare_raw > 0; break;
        case Py_GE: compare_result = compare_raw >= 0; break;
        default: compare_result = 0; break;
    }

    /* return the result of the actual comparison operator */
    if ( compare_result ) {
        Py_RETURN_TRUE;
    }

    Py_RETURN_FALSE;
}


/*
 * Return the dotted quad string representation of an IPv4 prefix including
 * both address and prefix length.
 */
static PyObject *IPv4_str(IPv4 *obj) {
    PyObject *ip = IPv4_ip_str(obj);
    PyObject *res = PyUnicode_FromFormat("%U/%d", ip, obj->prefixlen);
    Py_XDECREF(ip);
    return res;
}


/*
 * Hash function, based on the version, address and prefix length.
 */
static Py_hash_t IPv4_hash(IPv4 *obj){
    Py_hash_t res;
    PyObject *tup = Py_BuildValue("(iOi)", 4, IPv4_ip(obj), obj->prefixlen);
    res = PyObject_Hash(tup);
    Py_XDECREF(tup);
    return res;
}


/*
 * Return the state of the object (for pickling)
 */
static PyObject *IPv4_getstate(IPv4 *self) {
    return Py_BuildValue(
            "{sBsI}",
            "prefixlen", self->prefixlen,
            "ip", self->ip
            );
}


/*
 * Restore the state of an object based on a state dictionary (for pickling)
 */
static PyObject *IPv4_setstate(IPv4 *self, PyObject *d) {
    PyObject *ip;
    PyObject *prefixlen;

    ip = PyDict_GetItemString(d, "ip");
    if ( ip == NULL ) {
        PyErr_SetString(PyExc_AttributeError,
                "Invalid set state dictionary received (no IP)!");
        return NULL;
    }

    prefixlen = PyDict_GetItemString(d, "prefixlen");
    if ( prefixlen == NULL ) {
        PyErr_SetString(PyExc_AttributeError,
                "Invalid set state dictionary received (no prefixlen)!");
        return NULL;
    }

    self->ip = (uint32_t)PyLong_AsLong(ip);
    self->prefixlen = (uint8_t)PyLong_AsLong(prefixlen);
    Py_RETURN_NONE;
}


/* ---- Helper methods ---- */


/*
 * Compare two prefix objects and return an integer less than, equal to, or
 * greater than zero if obj1 is found, respectively, to be less than, equal
 * to, or greater than obj2.
 */
static int IPv4_compare(PyObject *obj1, PyObject *obj2) {
    uint8_t prefixlen1, prefixlen2;
    uint32_t ip1, ip2;

    if ( !PyObject_IsInstance(obj2, (PyObject*)&IPv4Type) ) {
        /* IPv4 will always sort before IPv6 */
        return -1;
    }

    ip1 = ((IPv4*)obj1)->ip;
    ip2 = ((IPv4*)obj2)->ip;

    /* compare IP addresses */
    if ( ip1 < ip2 ) {
        return -1;
    } else if ( ip1 > ip2 ) {
        return 1;
    }

    prefixlen1 = ((IPv4*)obj1)->prefixlen;
    prefixlen2 = ((IPv4*)obj2)->prefixlen;

    /* compare prefix length */
    if ( prefixlen1 < prefixlen2 ) {
        return -1;
    } else if ( prefixlen1 > prefixlen2 ) {
        return 1;
    }

    /* prefixes are the same */
    return 0;
}


/*
 * Create and return an IPv4 prefix netmask.
 */
static uint32_t IPv4_calculate_netmask(uint8_t prefixlen) {
    if ( prefixlen >= IPV4_PREFIX_LEN_MAX ) {
        return IPV4_ALL_ONES;
    }

    return IPV4_ALL_ONES ^ (IPV4_ALL_ONES >> prefixlen);
}


/*
 * Return a dotted quad representation of an IPv4 prefix.
 */
static PyObject *IPv4_ip_str(IPv4 *obj) {
    struct in_addr addr;
    char ipstr[INET_ADDRSTRLEN];

    addr.s_addr = htonl(obj->ip);

    if ( inet_ntop(AF_INET, &addr, ipstr, INET_ADDRSTRLEN) == NULL ) {
        Py_RETURN_NONE;
    }

    return PyUnicode_FromString(ipstr);
}


/* ---- (PYTHON) Object attributes and functions ---- */


/*
 * Return the integer netmask of an IPv4 prefix.
 */
static PyObject *IPv4_netmask(IPv4 *self) {
    return Py_BuildValue("I", IPv4_calculate_netmask(self->prefixlen));
}


/*
 * Return the integer netmask for a given prefix length.
 */
static PyObject *IPv4_netmask_from_prefixlen(IPv4 *self, PyObject *preflenOBJ) {
    int prefixlen;

    if ( !PyLong_Check(preflenOBJ) ) {
        PyErr_SetString(PyExc_AttributeError,
                "Prefix length has to be a number");
        return NULL;
    }

    prefixlen = PyLong_AsLong(preflenOBJ);
    if ( prefixlen < 0 || prefixlen > IPV4_PREFIX_LEN_MAX ) {
        PyErr_SetString(PyExc_AttributeError, "Invalid prefix length");
        return NULL;
    }

    return Py_BuildValue("I", IPv4_calculate_netmask((uint8_t)prefixlen));
}


/*
 * Return the max prefix length for the IP family.
 */
static PyObject *IPv4_max_prefixlen(IPv4 *self) {
    return Py_BuildValue("i", IPV4_PREFIX_LEN_MAX);
}


/*
 * Return the IP address of an IPv4 prefix.
 */
static PyObject *IPv4_ip(IPv4 *self) {
    return Py_BuildValue("I", self->ip);
}


/*
 * Return the IP address AFI number.
 */
static PyObject *IPv4_afi(IPv4 *self) {
    return Py_BuildValue("i", 1);
}


/*
 * Return the IP address SAFI number.
 */
static PyObject *IPv4_safi(IPv4 *self) {
    // TODO: Implement correct SAFI computation
    return Py_BuildValue("i", 1);
}


/*
 * Check if one IPv4 prefix contains another IPv4 prefix.
 */
static PyObject *IPv4_contains(IPv4 *self, PyObject *other) {
    /* if the other object isn't an IPv4 object then it isn't contained */
    if ( !PyObject_IsInstance(other, (PyObject*)&IPv4Type) ) {
        Py_RETURN_FALSE;
    }

    /* check if all the bits in our prefix length match in both prefixes */
    if ( (((IPv4*)other)->ip & IPv4_calculate_netmask(self->prefixlen)) ==
            self->ip ) {
        Py_RETURN_TRUE;
    }

    Py_RETURN_FALSE;
}


// ========================= IPV6 ===========================


/* ---- (PYTHON) Initialisation and cleaning functions ---- */


/*
 * Create a new IPv6 object and set fields to default values.
 */
static PyObject *IPv6_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
    IPv6 *self;
    self = (IPv6 *)type->tp_alloc(type, 0);
    if ( self != NULL ) {
        self->upper = 0;
        self->lower = 0;
        self->prefixlen = IPV6_PREFIX_LEN_MAX;
    }

    return (PyObject *)self;
}


/*
 * Initialise a new IPv6 prefix object.
 *
 * Expects an IPv4 address string in dotted quad notation (with or without
 * a prefix length) and an optional separate prefix length argument. If no
 * prefix length is given (through either argument), it defaults to 128.
 *
 * The optional prefixlength argument will take precedence over any length
 * given as part of the IP address string.
 */
static int IPv6_init(IPv6 *self, PyObject *args, PyObject *kwds) {
    static char *kwlist[] = {"ip", "prefixlen", NULL};
    char *ip_arg = NULL;
    int prefixlen_arg = -1;
    char *addrstr;
    char *prefixstr;
    char *fullstr;
    struct addrinfo *addrinfo;
    struct in6_addr in6;

    if ( !PyArg_ParseTupleAndKeywords(args, kwds, "s|i", kwlist, &ip_arg,
                &prefixlen_arg) ) {
        return -1;
    }

    /* make a copy so that we don't destroy the original python string */
    fullstr = strdup(ip_arg);

    /* split the address string on the '/' to separate address and prefixlen */
    addrstr = strtok(fullstr, "/");
    prefixstr = strtok(NULL, "/");

    /* try to convert the address string into a struct addrinfo */
    addrinfo = parse_address(addrstr);

    if ( addrinfo == NULL ) {
        PyErr_SetString(PyExc_ValueError, "Invalid IP address format.");
        free(fullstr);
        return -1;
    }

    /* extract the upper and lower parts from the in6_addr */
    in6 = ((struct sockaddr_in6*)addrinfo->ai_addr)->sin6_addr;
    self->upper = (((uint64_t)ntohl(in6.s6_addr32[0])) << 32) +
        ntohl(in6.s6_addr32[1]);
    self->lower = (((uint64_t)ntohl(in6.s6_addr32[2])) << 32) +
        ntohl(in6.s6_addr32[3]);
    freeaddrinfo(addrinfo);

    /* prefer to use the prefixlen_arg, though it might not be set */
    if ( prefixlen_arg == -1 ) {
        if ( prefixstr != NULL ) {
            /* otherwise try to extract prefix length from the address string */
            prefixlen_arg = process_number(prefixstr);
        } else {
            /* failing that, set the prefix length to 32 */
            prefixlen_arg = IPV6_PREFIX_LEN_MAX;
        }
    }

    free(fullstr);

    /* check that the prefix length falls within the expected range */
    if ( prefixlen_arg < 0 || prefixlen_arg > IPV6_PREFIX_LEN_MAX ) {
        PyErr_SetString(PyExc_ValueError, "Invalid prefix length");
        return -1;
    }

    self->prefixlen = (uint8_t)prefixlen_arg;

    return 0;
}


/*
 * Clean-up method
 */
static void IPv6_dealloc(IPv6 *self) {
    Py_TYPE(self)->tp_free((PyObject*)self);
}


/* ---- (PYTHON) Builtin functions ---- */


/*
 * Rich comparator method that compares two objects and returns a result
 */
static PyObject *IPv6_richcmp(PyObject *obj1, PyObject *obj2, int operator) {
    int compare_result;
    int compare_raw;

    /* Validate the type of the objects we are comparing */
    if ( !PyObject_IsInstance(obj1, (PyObject*)&IPv6Type) ) {
        PyErr_SetString(PyExc_AttributeError,
                "Can only compare prefix objects");
        return NULL;
    }

    if ( !PyObject_IsInstance(obj2, (PyObject*)&IPv4Type) &&
            !PyObject_IsInstance(obj2, (PyObject*)&IPv6Type) ) {
        PyErr_SetString(PyExc_AttributeError,
                "Can only compare prefix objects");
        return NULL;
    }

    /* Determine the ordering of the two objects */
    compare_raw = IPv6_compare(obj1, obj2);

    /* Check if the ordering matches what the comparison operator wanted */
    switch ( operator ) {
        case Py_LT: compare_result = compare_raw < 0; break;
        case Py_LE: compare_result = compare_raw <= 0; break;
        case Py_EQ: compare_result = compare_raw == 0; break;
        case Py_NE: compare_result = compare_raw != 0; break;
        case Py_GT: compare_result = compare_raw > 0; break;
        case Py_GE: compare_result = compare_raw >= 0; break;
        default: compare_result = 0; break;
    }

    /* return the result of the actual comparison operator */
    if ( compare_result ) {
        Py_RETURN_TRUE;
    }

    Py_RETURN_FALSE;
}


/*
 * Return the hexadecimal string representation of an IPv6 prefix including
 * both address and prefix length.
 */
static PyObject *IPv6_str(IPv6 *obj) {
    PyObject *ip = IPv6_ip_str(obj);
    PyObject *res = PyUnicode_FromFormat("%U/%d", ip, obj->prefixlen);
    Py_XDECREF(ip);
    return res;
}


/*
 * Hash function, based on the version, address and prefix length.
 */
static Py_hash_t IPv6_hash(IPv6 *obj){
    Py_hash_t res;
    PyObject *tup = Py_BuildValue("(iOc)", 6, IPv6_ip(obj), obj->prefixlen);
    res = PyObject_Hash(tup);
    Py_XDECREF(tup);
    return res;
}


/*
 * Return the state of the object (for pickling)
 */
static PyObject *IPv6_getstate(IPv6 *self) {
    return Py_BuildValue(
            "{sBsKsK}",
            "prefixlen", self->prefixlen,
            "lower", self->lower,
            "upper", self->upper);
}


/*
 * Restore the state of an object based on a state dictionary (for pickling)
 */
static PyObject *IPv6_setstate(IPv6 *self, PyObject *d) {
    PyObject *lower;
    PyObject *upper;
    PyObject *prefixlen;

    lower = PyDict_GetItemString(d, "lower");
    if ( lower == NULL ) {
        PyErr_SetString(PyExc_AttributeError,
                "Invalid set state dictionary received (no IP lower)!");
        return NULL;
    }

    upper = PyDict_GetItemString(d, "upper");
    if ( upper == NULL ) {
        PyErr_SetString(PyExc_AttributeError,
                "Invalid set state dictionary received (no IP upper)!");
        return NULL;
    }

    prefixlen = PyDict_GetItemString(d, "prefixlen");
    if ( prefixlen == NULL ) {
        PyErr_SetString(PyExc_AttributeError,
                "Invalid set state dictionary received (no prefixlen)!");
        return NULL;
    }

    self->upper = (uint64_t)PyLong_AsUnsignedLongLong(upper);
    self->lower = (uint64_t)PyLong_AsUnsignedLongLong(lower);
    self->prefixlen = (uint8_t)PyLong_AsLong(prefixlen);
    Py_RETURN_NONE;
}


/* ---- Helper methods ---- */


/*
 * Compare two prefix objects and return an integer less than, equal to, or
 * greater than zero if obj1 is found, respectively, to be less than, equal
 * to, or greater than obj2.
 */
static int IPv6_compare(PyObject *obj1, PyObject *obj2) {
    uint8_t prefixlen1, prefixlen2;
    uint64_t ip1upper, ip1lower, ip2upper, ip2lower;

    if ( !PyObject_IsInstance(obj2, (PyObject*)&IPv6Type) ) {
        /* IPv6 will always sort after IPv4 */
        return 1;
    }

    ip1upper = ((IPv6*)obj1)->upper;
    ip1lower = ((IPv6*)obj1)->lower;
    ip2upper = ((IPv6*)obj2)->upper;
    ip2lower = ((IPv6*)obj2)->lower;

    /* compare IP addresses */
    if ( (ip1upper < ip2upper) ||
            (ip1upper == ip2upper && ip1lower < ip2lower) ) {
        return -1;
    } else if ( (ip1upper > ip2upper) ||
            (ip1upper == ip2upper && ip1lower > ip2lower) ) {
        return 1;
    }

    prefixlen1 = ((IPv6*)obj1)->prefixlen;
    prefixlen2 = ((IPv6*)obj2)->prefixlen;

    /* compare prefix length */
    if ( prefixlen1 < prefixlen2 ) {
        return -1;
    } else if ( prefixlen1 > prefixlen2 ) {
        return 1;
    }

    /* prefixes are the same */
    return 0;
}


/*
 * Create and return the upper portion of an IPv6 netmask.
 */
static uint64_t IPv6_netmask_upper(uint8_t prefixlen) {
    if ( prefixlen >= 64 ) {
        return IPV6_ALL_ONES;
    }

    return IPV6_ALL_ONES ^ (IPV6_ALL_ONES >> prefixlen);
}


/*
 * Create and return the lower portion of an IPv6 netmask
 */
static uint64_t IPv6_netmask_lower(uint8_t prefixlen) {
    int lowerlen;

    if ( prefixlen <= 64 ) {
        return 0ULL;
    }

    lowerlen = prefixlen - 64;

    if ( lowerlen >= 64 ) {
        return IPV6_ALL_ONES;
    }

    return IPV6_ALL_ONES ^ (IPV6_ALL_ONES >> lowerlen);
}


/*
 * Generate a full IPv6 address or netmask as a string from the upper 64 bits
 * and the lower 64 bits of the value.
 */
static PyObject *combine_to_address(uint64_t upper, uint64_t lower) {
    char *ptr;
    PyObject *obj;

    if ( asprintf(&ptr, "%.16" PRIx64 "%.16" PRIx64, upper, lower) < 0 ) {
        Py_RETURN_NONE;
    }

    obj = PyLong_FromString(ptr, NULL, 16);

    free(ptr);
    return obj;
}


/*
 *  Return a python string representation of an IPv6 IP address.
 */
static PyObject *IPv6_ip_str(IPv6 *obj) {
    struct in6_addr addr;
    char ipstr[INET6_ADDRSTRLEN];

    addr.s6_addr32[0] = htonl((obj->upper >> 32) & 0xffffffff);
    addr.s6_addr32[1] = htonl(obj->upper & 0xffffffff);
    addr.s6_addr32[2] = htonl((obj->lower >> 32) & 0xffffffff);
    addr.s6_addr32[3] = htonl(obj->lower & 0xffffffff);

    if ( inet_ntop(AF_INET6, &addr, ipstr, INET6_ADDRSTRLEN) == NULL ) {
        Py_RETURN_NONE;
    }

    return PyUnicode_FromString(ipstr);
}


/* ---- (PYTHON) Object attributes and functions ---- */


/*
 * Return the netmask of an IPv6 prefix.
 */
static PyObject *IPv6_netmask(IPv6 *self) {
    return combine_to_address(
            IPv6_netmask_upper(self->prefixlen),
            IPv6_netmask_lower(self->prefixlen));
}


/*
 * Return a netmask for an IPv6 prefix length.
 */
static PyObject *IPv6_netmask_from_prefixlen(IPv6 *self, PyObject *preflenOBJ) {
    long prefixlen;

     if ( !PyLong_Check(preflenOBJ) ) {
        PyErr_SetString(PyExc_AttributeError,
                "Prefix length has to be a number");
        return NULL;
    }

    prefixlen = PyLong_AsLong(preflenOBJ);
    if ( prefixlen < 0 || prefixlen > 128 ) {
        PyErr_SetString(PyExc_AttributeError,
                "Prefix length has to be between 0 and 128");
        return NULL;
    }

    /* Generate and return the netmask */
    return combine_to_address(
            IPv6_netmask_upper(prefixlen),
            IPv6_netmask_lower(prefixlen));
}


/*
 * Return the max prefix length for the IP family
 */
static PyObject *IPv6_max_prefixlen(IPv6 *self) {
    return Py_BuildValue("i", IPV6_PREFIX_LEN_MAX);
}


/*
 * Return the IP address of an IPv6 prefix
 */
static PyObject *IPv6_ip(IPv6 *self) {
    return combine_to_address(self->upper, self->lower);
}


/*
 * Return the IP address AFI number.
 */
static PyObject *IPv6_afi(IPv6 *self) {
    return Py_BuildValue("i", 2);
}


/*
 * Return the IP address SAFI number.
 */
static PyObject *IPv6_safi(IPv6 *self) {
    // TODO: Implement correct SAFI computation
    return Py_BuildValue("i", 1);
}


/*
 * Check if one IPv6 prefix contains another IPv6 prefix.
 */
static PyObject *IPv6_contains(IPv6 *self, PyObject *other) {
    uint64_t upper;
    uint64_t lower;

    if ( !PyObject_IsInstance(other, (PyObject*)&IPv6Type) ) {
        Py_RETURN_FALSE;
    }

    upper = ((IPv6*)other)->upper & IPv6_netmask_upper(self->prefixlen);
    lower = ((IPv6*)other)->lower & IPv6_netmask_lower(self->prefixlen);

    if ( upper == self->upper && lower == self->lower ) {
        Py_RETURN_TRUE;
    }

    Py_RETURN_FALSE;
}


// ==================== MODULE AND FACTORY SETUP  ==========================


/*
 *  Prefix factory that initialises either an IPv4 or an IPv6 prefix based
 *  on provided arguments. If the IP string contains a : char then it's
 *  considered an IPv6 prefix. Otherwise we will try to initialise and return
 *  an IPv4 prefix.
 */
static PyObject *PrefixFactory(PyObject *self, PyObject *args, PyObject *kwds) {
    PyObject *obj = NULL;
    static char *kwlist[] = {"ip", "prefixlen", NULL};
    short preflen_arg = -1;
    char *ip_arg = NULL;

    if ( !PyArg_ParseTupleAndKeywords(args, kwds, "s|b", kwlist, &ip_arg,
                &preflen_arg) ) {
        PyErr_SetString(PyExc_ValueError, "Missing IP address argument");
        return NULL;
    }

    /*
     * TODO can we make the getaddrinfo() call here, and then use the family
     * from the resulting struct addrinfo to call the appropriate function?
     * Still need to check for IPv4 address string formatting though to make
     * sure it is a proper dotted quad.
     */

    /* Guess the address family of the prefix */
    if ( index(ip_arg, ':') == NULL ) {
        obj = PyObject_Call((PyObject *) &IPv4Type, args, kwds);
    } else {
        obj = PyObject_Call((PyObject *) &IPv6Type, args, kwds);
    }

    return obj;
}


/*
 * Register the types and the module.
 */
PyMODINIT_FUNC PyInit_Prefix(void) {
    PyObject* module;

    if ( PyType_Ready(&IPv4Type) < 0 ) {
        return NULL;
    }

    if ( PyType_Ready(&IPv6Type) < 0 ) {
        return NULL;
    }

    module = PyModule_Create(&prefixmodule);
    if ( module == NULL ) {
        return NULL;
    }

    Py_INCREF(&IPv4Type);
    PyModule_AddObject(module, "IPv4", (PyObject *)&IPv4Type);

    Py_INCREF(&IPv6Type);
    PyModule_AddObject(module, "IPv6", (PyObject *)&IPv6Type);

    return module;
}
