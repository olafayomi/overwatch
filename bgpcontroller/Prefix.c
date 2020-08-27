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
    Convert a string number to a integer. If a error occurs the method will
    return -1. Method will process up to a null terminator and makes sure
    that all chars are numeric (between '0' and '9').
*/
static int process_number(char *token) {
    int val = -1;
    int offset = 0;
    while (*(token+offset)) {
        char c = *(token+offset);
        if (c >= '0' && c <= '9') {
            if (val == -1)
                val = 0;

            val = (val * 10) + c - '0';
        } else {
            return -1;
        }
        offset++;
    }

    return val;
}

/*
    Process a hex string to a integer. Similar to process_number however
    we will also accept chars 'a' to 'f' (lower or uppercase).
*/
static int process_hexnumber(char *token) {
    int val = -1;
    int offset = 0;
    while (*(token+offset)) {
        char c = *(token+offset);
        if (c >= '0' && c <= '9') {
            // Convert numeric chars
            if (val == -1)
                val = 0;
            val = (val * 16) + c - '0';
        } else if (c >= 'a' && c <= 'f') {
            // Convert letter hex (lowercase)
            if (val == -1)
                val = 0;

            val = (val * 16) + (c - 'a' + 10);
        } else if (c >= 'A' && c <= 'F') {
            // Convert letter hex (uppercase)
            if (val == -1)
                val = 0;

            val = (val * 16) + (c - 'A' + 10);
        } else {
            return -1;
        }
        offset++;
    }

    return val;
}


// ========================= IPV4 ===========================


/* ---- (PYTHON) Initiation and cleaning functions ---- */


/* Method called when the a new object is created */
static PyObject *IPv4_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
    IPv4 *self;
    self = (IPv4 *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->ip = 0;
        self->prefixlen = IPV4_PREFIX_LEN_MAX;
    }

    return (PyObject *)self;
}

/*
    Initiation method of a IPv4 prefix address.
    We will expect to receive as arguments an IPv4 address string in
    doted quad notation with or without a prefixlength. If no prefix
    length is specified for both arguments the prefix default is a /32.

    The prefixlength attribute is optional and specifies a number representing
    the prefixlength of the prefix address. Please note that specifying
    this object takes precendence over a / in the IP address string.
*/
static int IPv4_init(IPv4 *self, PyObject *args, PyObject *kwds) {
    static char *kwlist[] = {"ip", "prefixlen", NULL};
    char *ip_arg = NULL;
    short preflen_arg = -1;

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "s|b", kwlist,
                                      &ip_arg, &preflen_arg))
        return -1;

    // Make a copy of the string argument so we don't destroy it
    // Preserve the argument varaible for the caller in python
    char *ip_str = strdup(ip_arg);

    // Process the string into the IP address and prefixlength
    char *token = ip_str;
    int octets = 0;
    int length = strlen(ip_str);

    for (int i = 0; i <= length; i++) {
        char c = *(ip_str+i);

        /*
            Process the first 3 octets. The octet seperator is a . charecter.
            A null terminator or any other non numeric char will raise an
            error.
        */
        if (octets < 3) {
            if (c == '.') {
                // Replace the token with a terminator
                *(ip_str+i) = '\0';

                int val = process_number(token);
                if (!(val >= 0 && val <= IPV4_QUAD_MAX)){
                    free(ip_str);
                    PyErr_SetString(PyExc_ValueError, "Invalid IP address format.");
                    return -1;
                }

                // Pack the IP address and go to the next token in our string
                self->ip |= ((unsigned int)(val & 0xff) << ((3-octets)*8));
                octets++;
                token = (ip_str+i+1);
            } else if (c == '\0') {
                free(ip_str);
                PyErr_SetString(PyExc_ValueError, "Invalid IP address format");
                return -1;
            }

        /*
            Process the last octet of the IP address. This octet needs to be terminated
            by a null terminator or a mask length symbol. Any other non numeric
            symbol will raise a error.
        */
        } else if (octets == 3) {
            if (c == '/' || c == '\0') {
                // Replace the split char with a null terminator
                *(ip_str+i) = '\0';

                int val = process_number(token);
                if (!(val >= 0 && val <= IPV4_QUAD_MAX)){
                    free(ip_str);
                    PyErr_SetString(PyExc_ValueError, "Invalid IP address format.");
                    return -1;
                }

                // Pack the octet in the IP number
                self->ip |= ((unsigned int)(val & 0xff) << ((3-octets)*8));

                // Indicate that we have a mask in our string
                if (c == '/')
                    octets++;

                token = (ip_str+i+1);
                break;
            }
        }
    }

    // If no prefixlen argument was specified try to process a length from the IP string
    if (preflen_arg == -1) {
        if (octets == 4) {
            int val = process_number(token);

            // If the prefix length is invalid free up resources and raise a error
            if (!(val >= 0 && val <= IPV4_PREFIX_LEN_MAX)) {
                free(ip_str);
                PyErr_SetString(PyExc_ValueError, "Prefix length is invalid");
                return -1;
            }

            self->prefixlen = ((unsigned char)val);
        }
    } else {
        self->prefixlen = ((unsigned char)preflen_arg);
    }

    // Initiation complete
    free(ip_str);

    // Validate the prefix length
    if (!(self->prefixlen >= 0 && self->prefixlen <= IPV4_PREFIX_LEN_MAX)) {
        PyErr_SetString(PyExc_ValueError, "Prefix length is invalid");
        return -1;
    }

    return 0;
}

/* Clean-up method called to deallocate used resources */
static void IPv4_dealloc(IPv4 *self) {
    Py_TYPE(self)->tp_free((PyObject*)self);
}


/* ---- (PYTHON) Builtin functions ---- */


/* Rich comparator method that compares two objects and returns a result */
static PyObject *IPv4_richcmp(PyObject *obj1, PyObject *obj2, int op)
{
    int c = 0, cmp_res;

    // Validate the type of the objects we are comparing
    if (!PyObject_IsInstance(obj1, (PyObject*)&IPv4Type)) {
        PyErr_SetString(PyExc_AttributeError, "Can only compare prefix objects");
        return NULL;
    }

    if (
            (!PyObject_IsInstance(obj2, (PyObject*)&IPv4Type)) &&
            (!PyObject_IsInstance(obj2, (PyObject*)&IPv6Type))
    ) {
        PyErr_SetString(PyExc_AttributeError, "Can only compare prefix objects");
        return NULL;
    }

    // Compare the two objects
    cmp_res = IPv4_compare(obj1, obj2);

    // Return the result for the operation
    switch (op) {
    case Py_LT: c = cmp_res <  0; break;
    case Py_LE: c = cmp_res <= 0; break;
    case Py_EQ: c = cmp_res == 0; break;
    case Py_NE: c = cmp_res != 0; break;
    case Py_GT: c = cmp_res >  0; break;
    case Py_GE: c = cmp_res >= 0; break;
    }

    // If the comparison is true return true
    if (c) {
        Py_RETURN_TRUE;
    }

    // Otherwise return false
    Py_RETURN_FALSE;
}

/* Return the string represntation of an IPv4 prefix (doted quad IP/prefixlen) */
static PyObject *IPv4_str(IPv4 *obj) {
    PyObject *ip = IPv4_ip_str(obj);
    PyObject *res = PyUnicode_FromFormat("%U/%d", ip, obj->prefixlen);
    Py_XDECREF(ip);
    return res;
}

/* Hash function */
static Py_hash_t IPv4_hash(IPv4 *obj){
    /*
        Hash function based on the initial Prefix.py module implementation.
        Hash a tuple made up of the prefix version, IP address and prefix
        length.
    */

    Py_hash_t res;
    PyObject *tup = Py_BuildValue("(iOi)", 4, IPv4_ip(obj), obj->prefixlen);
    res = PyObject_Hash(tup);
    Py_XDECREF(tup);
    return res;
}

/* Return the state of the object (for pickling) */
static PyObject *IPv4_getstate(IPv4 *self) {
    return Py_BuildValue("{sBsI}", "prefixlen", self->prefixlen, "ip", self->ip);
}

/* Restore the state of a object based on a state dictionary (for pickling) */
static PyObject *IPv4_setstate(IPv4 *self, PyObject *d) {
    PyObject *ip = PyDict_GetItemString(d, "ip");
    if (ip == NULL) {
        PyErr_SetString(PyExc_AttributeError,
                "Invalid set state dictionary received (no IP)!");
        return NULL;
    }

    PyObject *prefixlen = PyDict_GetItemString(d, "prefixlen");
    if (prefixlen == NULL) {
        PyErr_SetString(PyExc_AttributeError,
                "Invalid set state dictionary received (no prefixlen)!");
        return NULL;
    }

    self->ip = (unsigned int)PyLong_AsLong(ip);
    self->prefixlen = (unsigned char)PyLong_AsLong(prefixlen);
    Py_RETURN_NONE;
}


/* ---- Helper methods ---- */


/*
    Compare two Prefix objects and return a int describing their ordering
    -1 = obj1 is lower than obj2
     1 = obj1 is higher than obj2
     0 = obj1 is equal to obj2
*/
static int IPv4_compare(PyObject *obj1, PyObject *obj2) {
    unsigned char v1 = 0,v2 = 0,p1 = 0,p2 = 0;
    unsigned int i1 = 0, i2 = 0;

    i1 = ((IPv4*)obj1)->ip;
    p1 = ((IPv4*)obj1)->prefixlen;
    v1 = 4;

    if (PyObject_IsInstance(obj2, (PyObject*)&IPv4Type)) {
        i2 = ((IPv4*)obj2)->ip;
        p2 = ((IPv4*)obj2)->prefixlen;
        v2 = 4;
    } else if (PyObject_IsInstance(obj2, (PyObject*)&IPv6Type)) {
        // Comparing a IPv4 to a IPv6
        v2 = 6;
    }

    // Order by the prefix version
    if (v1 < v2) {
        return -1;
    } else if (v1 > v2) {
        // Always return 1 if IPv4 compare to IPv6
        return 1;
    }

    // Order by the IP number of the prefixes
    if (i1 < i2) {
        return -1;
    } else if (i1 > i2) {
        return 1;
    }

    // Order by the prefix length
    if (p1 < p2) {
        return -1;
    } else if (p1 > p2) {
        return 1;
    }

    // If all are the same prefixes are the same
    return 0;
}

/* Create and return a IPv4 prefix netmask */
static unsigned int IPv4_netmaskC(unsigned char prefixlen) {
    // XXX: LEFT SHIFT BY ENTIRE BIT WIDTH IS UNDEFINED
    if (prefixlen == 32)
        return IPV4_ALL_ONES;

    return IPV4_ALL_ONES ^ (IPV4_ALL_ONES >> prefixlen);
}

/* Return a dotted quad representation of a IPv4 prefix */
static PyObject *IPv4_ip_str(IPv4 *obj) {
    unsigned char bytes[4];
    bytes[0] = obj->ip & 0xFF;
    bytes[1] = (obj->ip >> 8) & 0xFF;
    bytes[2] = (obj->ip >> 16) & 0xFF;
    bytes[3] = (obj->ip >> 24) & 0xFF;
    return PyUnicode_FromFormat("%d.%d.%d.%d", bytes[3], bytes[2],
            bytes[1], bytes[0]);
}


/* ---- (PYTHON) Object attributes and functions ---- */


/* Return the netmask of a IPv4 prefix */
static PyObject *IPv4_netmask(IPv4 *self) {
    return Py_BuildValue("I", IPv4_netmaskC(self->prefixlen));
}

/* return a netmask for a prefix length */
static PyObject *IPv4_netmask_from_prefixlen(IPv4 *self, PyObject *preflenOBJ) {
    if (!PyLong_Check(preflenOBJ)) {
        PyErr_SetString(PyExc_AttributeError, "Prefix length has to be a number");
        return NULL;
    }

    long prefixlen = PyLong_AsLong(preflenOBJ);
    if (!(prefixlen >= 0 && prefixlen <= 32)) {
        PyErr_SetString(PyExc_AttributeError, "Prefix length has to be between 0 and 32");
        return NULL;
    }

    return Py_BuildValue("I", IPv4_netmaskC((unsigned short)prefixlen));
}

/* Return the max prefix lengh for the IP family */
static PyObject *IPv4_max_prefixlen(IPv4 *self) {
    return Py_BuildValue("i", IPV4_PREFIX_LEN_MAX);
}

/* Return the IP address of a IPv4 prefix */
static PyObject *IPv4_ip(IPv4 *self) {
    return Py_BuildValue("I", self->ip);
}

/* Return the IP address AFI number */
static PyObject *IPv4_afi(IPv4 *self) {
    return Py_BuildValue("i", 1);
}

/* Return the IP address SAFI number */
static PyObject *IPv4_safi(IPv4 *self) {
    // TODO: Implement correct SAFI computation
    return Py_BuildValue("i", 1);
}

/* Check if two prefixes are contained within each other */
static PyObject *IPv4_contains(IPv4 *self, PyObject *other)
{
    // If the other py object is not IPv4 return false
    if (!PyObject_IsInstance(other, (PyObject*)&IPv4Type))
        Py_RETURN_FALSE;

    if ((
        ((IPv4*)other)->ip & IPv4_netmaskC(self->prefixlen)) == self->ip
    )
        Py_RETURN_TRUE;

    Py_RETURN_FALSE;
}


// ========================= IPV6 ===========================


/* ---- (PYTHON) Initiation and cleaning functions ---- */


/* Method called when the a new object is created */
static PyObject *IPv6_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
    IPv6 *self;
    self = (IPv6 *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->upper = 0;
        self->lower = 0;
        self->prefixlen = IPV6_PREFIX_LEN_MAX;
    }

    return (PyObject *)self;
}

/*
    Initiation method of a IPv6 prefix address.
    We will expect to receive as arguments an IPv6 address string with or without a
    prefixlength. If no prefix length is specified for both arguments the prefix
    default is a /128.

    The prefixlength attribute is optional and specifies a number representing
    the prefixlength of the prefix address. Please note that specifying
    this object takes precendence over a / in the IP address string.
*/
static int IPv6_init(IPv6 *self, PyObject *args, PyObject *kwds) {
    static char *kwlist[] = {"ip", "prefixlen", NULL};
    char *ip_arg = NULL;
    short preflen_arg = -1;

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "s|b", kwlist,
                                      &ip_arg, &preflen_arg))
        return -1;

    // Make a copy of the string
    char *ip_str = strdup(ip_arg);

    // Process the string into the IP address and prefixlength
    char *token = ip_str;
    int length = strlen(ip_str);

    int parts[8] = {0,0,0,0,0,0,0,0};

    // The location of the pad hextet char (::)
    int padHextet = -1;

    // The number of hextets processed
    int hextet = 0;
    // Do we have a mask to process from the str
    unsigned char proc_mask = 0;

    for (int i = 0; i <= length; i++) {
        char c = *(ip_str+i);

        if (c == ':') {
            // Check if we are over the number of allowed groups in the IP
            if (hextet >= 7) {
                free(ip_str);
                PyErr_SetString(PyExc_ValueError, "Invalid IP address format. Too many groups!");
                return -1;
            }

            // Replace the token with a terminator
            *(ip_str+i) = '\0';

            // If this this is the first group do not parse for numbers
            // XXX: We assume that : should be followed by :: for offset 0.
            // if not the next iteration we will get an error raised
            if (i != 0) {
                int val = process_hexnumber(token);
                if (!(val >= 0 && val <= IPV6_QUAD_MAX)){
                    free(ip_str);
                    PyErr_SetString(PyExc_ValueError, "Invalid IP address format");
                    return -1;
                }

                parts[hextet] = val;
                hextet ++;
                token = (ip_str+i+1);
            }

            // Check for a pad char
            if (*(ip_str+i+1) == ':') {
                if (padHextet != -1) {
                    // We can only have one pad char
                    free(ip_str);
                    PyErr_SetString(PyExc_ValueError, "IPv6 can only contain one ::");
                    return -1;
                }

                i += 1;
                token = (ip_str+i+1);
                padHextet = hextet;

                // Replace the end pad char with a terminator
                *(ip_str+i) = '\0';
            }
        } else if ((c == '/') || (c == '\0')) {
            *(ip_str+i) = '\0';

            // If the end char is a : but not part of a :: we have a invalid address
            if (*(ip_str+i-1) == '\0' && *(ip_str+i-2) != '\0') {
                free(ip_str);
                PyErr_SetString(PyExc_ValueError,
                    "Invalid IP address format. IP must end on a pad zero or have e number");
                return -1;
            }

            // Check if we have digits in the final group
            if (*(ip_str+i-1) != '\0') {
                int val = process_hexnumber(token);
                if (!(val >= 0 && val <= IPV6_QUAD_MAX)){
                    free(ip_str);
                    PyErr_SetString(PyExc_ValueError, "Invalid IP address format");
                    return -1;
                }

                parts[hextet] = val;
                hextet ++;
                token = (ip_str+i+1);
            }

            // If we are in the mask move to the mask token for processing
            if (c == '/') {
                proc_mask = 1;
                token = (ip_str+i+1);
            }

            // If we do not have a pad char skip the shifting
            if (padHextet != -1) {
                int padShift = (hextet - padHextet);
                if (padShift != 0) {
                    if (padHextet + padShift >= 8) {
                        free(ip_str);
                        PyErr_SetString(PyExc_ValueError,
                            "Invalid IP address. Too many groups!");
                        return -1;
                    }

                    for (int q = padShift-1; q >= 0; q--) {
                        int index1 = padHextet+q;
                        int index2 = (8-padShift)+q;
                        parts[index2] = parts[index1];
                        parts[index1] = 0;
                    }
                }
            } else if (padHextet == -1 && hextet != 8) {
                free(ip_str);
                PyErr_SetString(PyExc_ValueError,
                    "Invalid IP address. IPv6 prefix dosen't have enough groups");
                return -1;
            }

            // Pack the numbers to the sections
            self->upper = parts[0];
            self->upper = (self->upper << 16) | parts[1];
            self->upper = (self->upper << 16) | parts[2];
            self->upper = (self->upper << 16) | parts[3];

            self->lower = parts[4];
            self->lower = (self->lower << 16) | parts[5];
            self->lower = (self->lower << 16) | parts[6];
            self->lower = (self->lower << 16) | parts[7];

            break;
        }
    }

    // If no prefixlen argument was specified try to process a length from the IP string
    if (preflen_arg == -1) {
        if (proc_mask != 0) {
            // Get the netmask
            int val = process_number(token);

            if (!(val >= 0 && val <= IPV6_PREFIX_LEN_MAX)) {
                free(ip_str);
                PyErr_SetString(PyExc_ValueError, "Prefix length is invalid");
                return -1;
            }

            self->prefixlen = ((unsigned char)val);
        }
    } else {
        self->prefixlen = ((unsigned char)preflen_arg);
    }

    free(ip_str);

    // Validate the prefix length
    if (!(self->prefixlen >= 0 && self->prefixlen <= IPV6_PREFIX_LEN_MAX)) {
        PyErr_SetString(PyExc_ValueError, "Prefix length is invalid");
        return -1;
    }

    return 0;
}

/* Clean-up method */
static void IPv6_dealloc(IPv6 *self) {
    Py_TYPE(self)->tp_free((PyObject*)self);
}

/* ---- (PYTHON) Builtin functions ---- */


/* Rich comparator method that compares two objects and returns a result */
static PyObject *IPv6_richcmp(PyObject *obj1, PyObject *obj2, int op)
{
    int c = 0, cmp_res;

    // Validate the type of the objects we are comparing
    if (!PyObject_IsInstance(obj1, (PyObject*)&IPv6Type)) {
        PyErr_SetString(PyExc_AttributeError, "Can only compare prefix objects");
        return NULL;
    }

    if (
            (!PyObject_IsInstance(obj2, (PyObject*)&IPv4Type)) &&
            (!PyObject_IsInstance(obj2, (PyObject*)&IPv6Type))
    ) {
        PyErr_SetString(PyExc_AttributeError, "Can only compare prefix objects");
        return NULL;
    }

    // Compare the two objects
    cmp_res = IPv6_compare(obj1, obj2);

    // Return the result for the operation
    switch (op) {
    case Py_LT: c = cmp_res <  0; break;
    case Py_LE: c = cmp_res <= 0; break;
    case Py_EQ: c = cmp_res == 0; break;
    case Py_NE: c = cmp_res != 0; break;
    case Py_GT: c = cmp_res >  0; break;
    case Py_GE: c = cmp_res >= 0; break;
    }

    // If the comparison is true return true
    if (c) {
        Py_RETURN_TRUE;
    }

    // Otherwise return false
    Py_RETURN_FALSE;
}

/* Return the string representation of a IPv6 prefix (IP/prefixlen) */
static PyObject *IPv6_str(IPv6 *obj) {
    PyObject *ip = IPv6_ip_str(obj);
    PyObject *res = PyUnicode_FromFormat("%U/%d", ip, obj->prefixlen);
    Py_XDECREF(ip);
    return res;
}

/* IPv6 hash function */
static Py_hash_t IPv6_hash(IPv6 *obj){
    /*
        Hash function based on the initial Prefix.py module implementation.
        Hash a tuple made up of the prefix version, IP address and prefix
        length.
    */

    Py_hash_t res;
    PyObject *tup = Py_BuildValue("(iOc)", 6, IPv6_ip(obj), obj->prefixlen);
    res = PyObject_Hash(tup);
    Py_XDECREF(tup);
    return res;
}

/* Return the state of the object (for pickling) */
static PyObject *IPv6_getstate(IPv6 *self) {
    return Py_BuildValue("{sBsKsK}", "prefixlen", self->prefixlen,
                "lower", self->lower, "upper", self->upper);
}

/* Restore the state of a object based on a state dictionary (for pickling) */
static PyObject *IPv6_setstate(IPv6 *self, PyObject *d) {
    PyObject *lower = PyDict_GetItemString(d, "lower");
    if (lower == NULL) {
        PyErr_SetString(PyExc_AttributeError,
                "Invalid set state dictionary received (no IP lower)!");
        return NULL;
    }

    PyObject *upper = PyDict_GetItemString(d, "upper");
    if (upper == NULL) {
        PyErr_SetString(PyExc_AttributeError,
                "Invalid set state dictionary received (no IP upper)!");
        return NULL;
    }

    PyObject *prefixlen = PyDict_GetItemString(d, "prefixlen");
    if (prefixlen == NULL) {
        PyErr_SetString(PyExc_AttributeError,
                "Invalid set state dictionary received (no prefixlen)!");
        return NULL;
    }

    self->upper = (unsigned long long)PyLong_AsUnsignedLongLong(upper);
    self->lower = (unsigned long long)PyLong_AsUnsignedLongLong(lower);
    self->prefixlen = (unsigned char)PyLong_AsLong(prefixlen);
    Py_RETURN_NONE;
}


/* ---- Helper methods ---- */


/*
    Compare two Prefix objects and return a int describing their ordering
    -1 = obj1 is lower than obj2
     1 = obj1 is higher than obj2
     0 = obj1 is equal to obj2
*/
static int IPv6_compare(PyObject *obj1, PyObject *obj2) {
    unsigned char v1 = 0,v2 = 0,p1 = 0,p2 = 0;
    unsigned long long i1u = 0, i1l = 0, i2u = 0, i2l = 0;

    i1u = ((IPv6*)obj1)->upper;
    i1l = ((IPv6*)obj1)->lower;
    p1 = ((IPv6*)obj1)->prefixlen;
    v1 = 6;

    if (PyObject_IsInstance(obj2, (PyObject*)&IPv6Type)) {
        i2u = ((IPv6*)obj2)->upper;
        i2l = ((IPv6*)obj2)->lower;
        p2 = ((IPv6*)obj2)->prefixlen;
        v2 = 6;
    } else {
        v2 = 4;
    }

    // Order by the prefix version
    if (v1 < v2) {
        return -1;
    } else if (v1 > v2) {
        return 1;
    }

    // Order by the IP number of the prefixes
    if ((i1u < i2u) || (i1u == i2u && i1l < i2l)) {
        return -1;
    } else if ((i1u > i2u) || (i1u == i2u && i1l > i2l)) {
        return 1;
    }

    // Order by the prefix length
    if (p1 < p2) {
        return -1;
    } else if (p1 > p2) {
        return 1;
    }

    // If all are the same prefixes are the same
    return 0;
}

/* Create and return a upper IPv6 netmask section */
static unsigned long long IPv6_netmaskUpperC(unsigned short prefixlen) {
    if (prefixlen >= 64)
        return IPV6_ALL_ONES;

    return IPV6_ALL_ONES ^ (IPV6_ALL_ONES >> prefixlen);
}

/* Create and return a lower IPv6 netmask section */
static unsigned long long IPv6_netmaskLowerC(unsigned short prefixlen) {
    if (prefixlen <= 64)
        return 0ULL;

    int len = prefixlen - 64;

    // XXX: PREVENT FULL WIDTH SHIFT ERROR
    if (len == 64)
        return IPV6_ALL_ONES;
    return IPV6_ALL_ONES ^ (IPV6_ALL_ONES >> len);
}

/* Generate a binary string from a upper and lower section of a IPv6 prefix */
static char *combine_to_bin(unsigned long long upper, unsigned long long lower) {
    // Allocate space for our binary string
    char *ptr = malloc(129);

    // Iterate through the upper value and create a binary string from it
    unsigned long long mask = 0x8000000000000000U;
    for (int i = 0; i < 64; i++) {
        if ((upper & mask) == 0)
            *(ptr+i) = '0';
        else
            *(ptr+i) = '1';
        mask >>= 1;
    }

    // Create the binary string from the lower value
    mask = 0x8000000000000000U;
    for (int i = 64; i < 128; i++) {
        if ((lower & mask) == 0)
            *(ptr+i) = '0';
        else
            *(ptr+i) = '1';
        mask >>= 1;
    }

    // Terminate the string and return the pointer to it
    *(ptr+128) = '\0';
    return ptr;
}

/*
    Return a python string of a IPv6 IP address. This method
    will follow IPv6 compression practices (remove leading 0s from
    groups and use the :: to pad longest sequence with 0s).
*/
static PyObject *IPv6_ip_str(IPv6 *obj) {
    char *ptr = malloc(40);

    // Seperate the upper and lower into IP parts
    int parts[8] = {0,0,0,0,0,0,0};
    unsigned long long upper = obj->upper;
    unsigned long long lower = obj->lower;

    for (int i = 3; i >= 0; i--) {
        parts[i] = upper & 0xffff;
        upper >>= 16;
    }

    for (int i = 7; i >= 4; i--) {
        parts[i] = lower & 0xffff;
        lower >>= 16;
    }

    // Find the longest possible pad with zero size
    int longPadSize = -1;
    int longPadIndex = -1;
    int padSize = 0;

    for (int i = 0; i < 8; i++) {
        if (parts[i] == 0) {
            padSize ++;
            if (longPadSize < padSize) {
                longPadSize = padSize;
                longPadIndex = i-(padSize-1);
            }
        } else {
            padSize = 0;
        }
    }

    // Format the IP to a string
    int strIndex = 0;
    for (int i = 0; i < 8; i++) {
        // Check if the current group is a pad with zero group
        // XXX: RFC 5952 specifies that we can pad a single group at first
        // but then states that we should not use :: to pad a single field.
        // Modify our implementation to match the default python implementation!
        if (longPadSize > 1 && longPadIndex == i) {
            if (i == 0) {
                *(ptr+strIndex) = ':';
                *(ptr+strIndex+1) = ':';
                *(ptr+strIndex+2) = '\0';
                strIndex += 2;
            } else {
                *(ptr+strIndex-1) = ':';
                *(ptr+strIndex) = ':';
                *(ptr+strIndex+1) = '\0';
                strIndex += 1;
            }
        // If this is not a pad with zero group (or the size is less than 2)
        // Format the IP address group value and write it to the string
        } else if (
            (longPadSize <= 1) ||
            (!(i >= longPadIndex && i < (longPadIndex+longPadSize)))
        ) {
            strIndex += sprintf((ptr+strIndex), "%x", parts[i]);
            *(ptr+strIndex) = ':';

            if (i != 7)
                strIndex++;
        }
    }

    // Zero pad the string at the end
    *(ptr+strIndex) = '\0';

    // Convert the string to a pythons tring and return the result
    PyObject *res = PyUnicode_FromString(ptr);
    free(ptr);
    return res;
}


/* ---- (PYTHON) Object attributes and functions ---- */


/* Return the netmask of a IPv6 prefix */
static PyObject *IPv6_netmask(IPv6 *self) {
    char *ptr = combine_to_bin(
            IPv6_netmaskUpperC(self->prefixlen),
            IPv6_netmaskLowerC(self->prefixlen));
    PyObject *obj = PyLong_FromString(ptr, NULL, 2);
    free(ptr);
    return obj;
}

/* Return a netmask for a prefix length */
static PyObject *IPv6_netmask_from_prefixlen(IPv6 *self, PyObject *preflenOBJ) {
     if (!PyLong_Check(preflenOBJ)) {
        PyErr_SetString(PyExc_AttributeError, "Prefix length has to be a number");
        return NULL;
    }
    long prefixlen = PyLong_AsLong(preflenOBJ);
    if (!(prefixlen >= 0 && prefixlen <= 128)) {
        PyErr_SetString(PyExc_AttributeError, "Prefix length has to be between 0 and 128");
        return NULL;
    }

    // Generate and return the netmask
    char *ptr = combine_to_bin(
            IPv6_netmaskUpperC(prefixlen),
            IPv6_netmaskLowerC(prefixlen));
    PyObject *obj = PyLong_FromString(ptr, NULL, 2);
    free(ptr);
    return obj;
}

/* Return the max prefix lengh for the IP family */
static PyObject *IPv6_max_prefixlen(IPv6 *self) {
    return Py_BuildValue("i", IPV6_PREFIX_LEN_MAX);
}

/* Return the IP address of a IPv6 prefix */
static PyObject *IPv6_ip(IPv6 *self) {
    char *ptr = combine_to_bin(
            self->upper,
            self->lower);
    PyObject *obj = PyLong_FromString(ptr, NULL, 2);
    free(ptr);
    return obj;
}

/* Return the IP address AFI number */
static PyObject *IPv6_afi(IPv6 *self) {
    return Py_BuildValue("i", 2);
}

/* Return the IP address SAFI number */
static PyObject *IPv6_safi(IPv6 *self) {
    // TODO: Implement correct SAFI computation
    return Py_BuildValue("i", 1);
}

/* Check if two prefixes are contained within each other */
static PyObject *IPv6_contains(IPv6 *self, PyObject *other)
{
    if (!PyObject_IsInstance(other, (PyObject*)&IPv6Type))
        Py_RETURN_FALSE;

    unsigned long long resUpper = ((IPv6*)other)->upper & IPv6_netmaskUpperC(self->prefixlen);
    unsigned long long resLower = ((IPv6*)other)->lower & IPv6_netmaskLowerC(self->prefixlen);

    if (resUpper == self->upper && resLower == self->lower)
        Py_RETURN_TRUE;

    Py_RETURN_FALSE;
}


// ==================== MODULE AND FACTORY SETUP  ==========================


/*
    Prefix factory that intiaties either a IPv4 or a IPv6 prefix based
    on provided arguments. If the ip string contains a : char then its considered
    a IPv6 prefix. Otherwise we will try to intiate and return a IPv4 prefix.
*/
static PyObject *PrefixFactory(PyObject *self, PyObject *args, PyObject *kwds) {
    PyObject *obj = NULL;

    static char *kwlist[] = {"ip", "prefixlen", NULL};
    short preflen_arg = -1;

    char *ip_arg = NULL;
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "s|b", kwlist, &ip_arg, &preflen_arg)) {
        PyErr_SetString(PyExc_ValueError, "Please provide the required arguments");
        return NULL;
    }

    // Check if the prefix is a IPv6
    int version = 4;
    for (int i = 0; i < strlen(ip_arg); i++) {
        if (*(ip_arg+i) == ':') {
            version = 6;
            break;
        }
    }

    // Intiate the correct prefix type
    if (version == 4) {
        obj = PyObject_Call((PyObject *) &IPv4Type, args, kwds);
    } else {
        obj = PyObject_Call((PyObject *) &IPv6Type, args, kwds);
    }

    return obj;
}

// Register the types and the module
PyMODINIT_FUNC PyInit_Prefix(void) {
    PyObject* m;

    if (PyType_Ready(&IPv4Type) < 0)
        return NULL;

    if (PyType_Ready(&IPv6Type) < 0)
        return NULL;

    m = PyModule_Create(&prefixmodule);
    if (m == NULL)
        return NULL;

    Py_INCREF(&IPv4Type);
    PyModule_AddObject(m, "IPv4", (PyObject *)&IPv4Type);

    Py_INCREF(&IPv6Type);
    PyModule_AddObject(m, "IPv6", (PyObject *)&IPv6Type);
    return m;
}

