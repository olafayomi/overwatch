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

#ifndef PREFIX_H
#define PREFIX_H

#include <Python.h>
#include <stdint.h>
#include "structmember.h"
#include "prefixtypes.h"

#define     IPV4_ALL_ONES           0xffffffffU
#define     IPV4_PREFIX_LEN_MAX     32
#define     IPV4_QUAD_MAX           255

#define     IPV6_ALL_ONES           0xffffffffffffffffULL
#define     IPV6_PREFIX_LEN_MAX     128
#define     IPV6_QUAD_MAX           0xFFFFu


/* Convert a string number to an integer */
static int process_number(char *token);


// NOTE: Sections and functions which contain the (PYTHON) in
// their comments are exposed externally (can be accessed from
// python).


// ========================= IPV4 ===========================


/* ---- (PYTHON) Initialisation and cleaning functions ---- */


// Allocate new object
static PyObject *IPv4_new(PyTypeObject *type, PyObject *args, PyObject *kwds);

// Initialisation method
static int IPv4_init(IPv4 *self, PyObject *args, PyObject *kwds);

// Cleanup method (free memory)
static void IPv4_dealloc(IPv4 *self);


/* ---- (PYTHON) Builtin functions ---- */


// Rich comparator (compare two objects)
static PyObject *IPv4_richcmp(PyObject *obj1, PyObject *obj2, int op);

// To string
static PyObject *IPv4_str(IPv4 *obj);

// Hash method
static Py_hash_t IPv4_hash(IPv4 *obj);

// Retrieve state (serialize)
static PyObject *IPv4_getstate(IPv4 *self);

// Restore object from state (de-serialize)
static PyObject *IPv4_setstate(IPv4 *self, PyObject *d);


/* ---- Helper methods ---- */


// Compare two objects and return their ordering as an int
static int IPv4_compare(PyObject *obj1, PyObject *obj2);

// Create an IPv4 netmask as an integer from a prefixlength
static uint32_t IPv4_calculate_netmask(uint8_t prefixlen);

// (PYTHON) Return a dotted quad str of an IPv4 prefix ip
static PyObject *IPv4_ip_str(IPv4 *obj);


/* ---- (PYTHON) Object attributes and functions ---- */


// Get the netmask of the prefix
static PyObject *IPv4_netmask(IPv4 *self);

// Get a netmask from a prefix length
static PyObject *IPv4_netmask_from_prefixlen(IPv4 *self, PyObject *preflenOBJ);

// Get the maximum prefix length for the AFI
static PyObject *IPv4_max_prefixlen(IPv4 *self);

// Get the IP of the prefix
static PyObject *IPv4_ip(IPv4 *self);

// Get the prefix AFI number
static PyObject *IPv4_afi(IPv4 *self);

// Get the prefix SAFi number
static PyObject *IPv4_safi(IPv4 *self);

// Check if two prefixes are contained within one another
static PyObject *IPv4_contains(IPv4 *self, PyObject *other);


/* ---- Type Configuration ---- */


// Member variable definition of type
static PyMemberDef IPv4_members[] = {
    {"prefixlen", T_UBYTE, offsetof(IPv4, prefixlen), READONLY,
        "ipv4 prefix length"},
    {NULL}  /* Sentinel */
};

// Method definition of type
static PyMethodDef IPv4_methods[] = {
    {"ip", (PyCFunction)IPv4_ip, METH_NOARGS,
     "Return the ip address of the prefix as a number"},

    {"netmask", (PyCFunction)IPv4_netmask, METH_NOARGS,
     "Return the a netmask number of the prefix"},
    {"netmask_from_prefixlen", (PyCFunction)IPv4_netmask_from_prefixlen, METH_O,
     "Return a netmask number from a prefix length for the prefix family"},
    {"max_prefixlen", (PyCFunction)IPv4_max_prefixlen, METH_NOARGS,
     "Return the max prefix length"},
    {"without_netmask", (PyCFunction)IPv4_ip_str, METH_NOARGS,
     "Return the doted quad representation of the IP address"},

    {"afi", (PyCFunction)IPv4_afi, METH_NOARGS,
     "Returns the prefix afi version"},
    {"safi", (PyCFunction)IPv4_safi, METH_NOARGS,
     "Returns the prefix safi version"},

    {"contains", (PyCFunction)IPv4_contains, METH_O,
     "Checks if a prefix is contained within another prefix"},

    {"__getstate__", (PyCFunction)IPv4_getstate, METH_NOARGS,
     "Retrieve the state dictionary for pickling"},
    {"__setstate__", (PyCFunction)IPv4_setstate, METH_O,
     "Restore an object from a state dictionary for unpickling"},

    {NULL}  /* Sentinel */
};

// Configure the IPv4 prefix type
static PyTypeObject IPv4Type = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "Prefix.IPv4",             /* tp_name */
    sizeof(IPv4),              /* tp_basicsize */
    0,                         /* tp_itemsize */
    (destructor)IPv4_dealloc,  /* tp_dealloc */
    0,                         /* tp_print */
    0,                         /* tp_getattr */
    0,                         /* tp_setattr */
    0,                         /* tp_reserved */
    (reprfunc)IPv4_str,        /* tp_repr */
    0,                         /* tp_as_number */
    0,                         /* tp_as_sequence */
    0,                         /* tp_as_mapping */
    (hashfunc)IPv4_hash,       /* tp_hash  */
    0,                         /* tp_call */
    (reprfunc)IPv4_str,        /* tp_str */
    0,                         /* tp_getattro */
    0,                         /* tp_setattro */
    0,                         /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT,        /* tp_flags */
    "IPv4 Prefix objects",     /* tp_doc */
    0,                         /* tp_traverse */
    0,                         /* tp_clear */
    (richcmpfunc)IPv4_richcmp, /* tp_richcompare */
    0,                         /* tp_weaklistoffset */
    0,                         /* tp_iter */
    0,                         /* tp_iternext */
    IPv4_methods,              /* tp_methods */
    IPv4_members,              /* tp_members */
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    (initproc)IPv4_init,       /* tp_init */
    0,                         /* tp_alloc */
    IPv4_new,                  /* tp_new */
};


// ========================= IPV6 ===========================


/* ---- (PYTHON) Initialisation and cleaning functions ---- */


// Allocate new object
static PyObject *IPv6_new(PyTypeObject *type, PyObject *args, PyObject *kwds);

// Initialisation method
static int IPv6_init(IPv6 *self, PyObject *args, PyObject *kwds);

// Cleanup method (free memory allocations)
static void IPv6_dealloc(IPv6 *self);


/* ---- (PYTHON) Builtin functions ---- */


// Rich comparator (compare two objects)
static PyObject *IPv6_richcmp(PyObject *obj1, PyObject *obj2, int op);

// To string
static PyObject *IPv6_str(IPv6 *obj);

// Hash Method
static Py_hash_t IPv6_hash(IPv6 *obj);

// Retrieve state (serialize)
static PyObject *IPv6_getstate(IPv6 *self);

// Restore object from state (de-serialize)
static PyObject *IPv6_setstate(IPv6 *self, PyObject *d);


/* ---- Helper methods ---- */


// Compare two objects and return their ordering as an int
static int IPv6_compare(PyObject *obj1, PyObject *obj2);

// Create an IPv6 upper netmask section from a prefix length
static uint64_t IPv6_netmask_upper(uint8_t prefixlen);

// Create an IPv6 lower netmask section from a prefix length
static uint64_t IPv6_netmask_lower(uint8_t prefixlen);

// Combine two IPv6 address sections into a python number
static PyObject *combine_to_address(uint64_t upper, uint64_t lower);

// (PYTHON) Return an IPv6 ip string from a prefix
static PyObject *IPv6_ip_str(IPv6 *obj);


/* ---- (PYTHON) Object attributes and functions ---- */


// Get the netmask of the prefix
static PyObject *IPv6_netmask(IPv6 *self);

// Get a netmask from a prefix length
static PyObject *IPv6_netmask_from_prefixlen(IPv6 *self, PyObject *preflenOBJ);

// Get the maximum prefix length for the AFI
static PyObject *IPv6_max_prefixlen(IPv6 *self);

// Get the IP of the prefix
static PyObject *IPv6_ip(IPv6 *self);

// Get the prefix AFI number
static PyObject *IPv6_afi(IPv6 *self);

// Get the prefix SAFI number
static PyObject *IPv6_safi(IPv6 *self);

// Check if two prefixes are contained within one another
static PyObject *IPv6_contains(IPv6* self, PyObject *other);


/* ---- Type Configuration ---- */

// Member variable definition of type
static PyMemberDef IPv6_members[] = {
    {"prefixlen", T_UBYTE, offsetof(IPv6, prefixlen), READONLY, "ipv6 prefixlen"},
    {NULL}  /* Sentinel */
};

// Method definition of type
static PyMethodDef IPv6_methods[] = {
    {"ip", (PyCFunction)IPv6_ip, METH_NOARGS,
     "Return the ip address of the prefix as a number"},

    {"netmask", (PyCFunction)IPv6_netmask, METH_NOARGS,
     "Return the a netmask number of the prefix"},
    {"netmask_from_prefixlen", (PyCFunction)IPv6_netmask_from_prefixlen, METH_O,
     "Return a netmask number from a prefix length for the prefix family"},
    {"max_prefixlen", (PyCFunction)IPv6_max_prefixlen, METH_NOARGS,
     "Return the max prefix length"},
    {"without_netmask", (PyCFunction)IPv6_ip_str, METH_NOARGS,
     "Return the IPv6 IP string representation"},

    {"afi", (PyCFunction)IPv6_afi, METH_NOARGS,
     "Returns the prefix afi version"},
    {"safi", (PyCFunction)IPv6_safi, METH_NOARGS,
     "Returns the prefix safi version"},

    {"contains", (PyCFunction)IPv6_contains, METH_O,
     "Checks if a prefix is contained within another prefix"},

    {"__getstate__", (PyCFunction)IPv6_getstate, METH_NOARGS,
     "Retrieve the state dictionary for pickling"},
    {"__setstate__", (PyCFunction)IPv6_setstate, METH_O,
     "Restore an object from a state dictionary for unpickling"},

    {NULL}  /* Sentinel */
};

// Configure the IPv6 prefix type
static PyTypeObject IPv6Type = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "Prefix.IPv6",             /* tp_name */
    sizeof(IPv6),              /* tp_basicsize */
    0,                         /* tp_itemsize */
    (destructor)IPv6_dealloc,  /* tp_dealloc */
    0,                         /* tp_print */
    0,                         /* tp_getattr */
    0,                         /* tp_setattr */
    0,                         /* tp_reserved */
    (reprfunc)IPv6_str,        /* tp_repr */
    0,                         /* tp_as_number */
    0,                         /* tp_as_sequence */
    0,                         /* tp_as_mapping */
    (hashfunc)IPv6_hash,       /* tp_hash  */
    0,                         /* tp_call */
    (reprfunc)IPv6_str,        /* tp_str */
    0,                         /* tp_getattro */
    0,                         /* tp_setattro */
    0,                         /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT,        /* tp_flags */
    "IPv6 Prefix objects",     /* tp_doc */
    0,                         /* tp_traverse */
    0,                         /* tp_clear */
    (richcmpfunc)IPv6_richcmp, /* tp_richcompare */
    0,                         /* tp_weaklistoffset */
    0,                         /* tp_iter */
    0,                         /* tp_iternext */
    IPv6_methods,              /* tp_methods */
    IPv6_members,              /* tp_members */
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    (initproc)IPv6_init,       /* tp_init */
    0,                         /* tp_alloc */
    IPv6_new,                  /* tp_new */
};


/* ==================== MODULE AND FACTORY SETUP  ========================== */

/* Factory that will create the correct prefix type (IPv4 vs IPv6) */
static PyObject *PrefixFactory(PyObject *self, PyObject *args, PyObject *kwds);

/* Define the module methods (bind the factory to the module) */
static PyMethodDef prefixmethods[] = {
    {
        "Prefix",
        (PyCFunction)PrefixFactory,
        METH_VARARGS | METH_KEYWORDS,
        "Factory entry point (construct a prefix)"
    },
    {NULL, NULL, 0, NULL}   /* Sentinel */
};

/* Define the module */
static PyModuleDef prefixmodule = {
    PyModuleDef_HEAD_INIT,
    "Prefix",
    "IPv4/IPv6 address prefix library",
    -1,
    prefixmethods
    //NULL, NULL, NULL, NULL, NULL
};

#endif /* PREFIX_H */
