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

#ifndef ROUTEENTRY_H
#define ROUTEENTRY_H

#include <Python.h>
#include <stdint.h>
#include "structmember.h"

#define DEFAULT_LOCAL_PREF      100

#define ORIGIN_IGP              0
#define ORIGIN_EGP              1
#define ORIGIN_INCOMPLETE       2


static PyTypeObject RouteEntryType;


typedef struct {
    PyObject_HEAD;

    /* Prefix that this route entry refers to */
    PyObject *prefix;

    /* ASN of the peer that we received this route entry from */
    uint32_t peer;

    /* BGP preference for this route entry */
    uint32_t preference;

    /* AS Path, AS Set and Communities for this route entry, all optional */
    uint32_t *as_path;
    uint32_t *as_set;
    uint32_t *communities;

    /* Size of the AS Path, AS Set and Communities */
    uint16_t as_path_size;
    uint16_t as_set_size;
    uint16_t communities_size;

    /* BGP Origin for this route entry (IGP/EGP/INCOMPLETE) */
    uint8_t origin;

    /* Next hop to reach the given prefix */
    char *nexthop;
} RouteEntry;


// NOTE: Sections which contain the keyword Python are
// exposed externally (i.e. we can access them in python)


/* ---- Python initialisation and cleaning functions ---- */


// Allocate new object
static PyObject *re_new(PyTypeObject *type, PyObject *args, PyObject *kwds);

// Initialisation method
static int re_init(RouteEntry *self, PyObject *args, PyObject *kwds);

// Cleanup method
static void re_dealloc(RouteEntry *self);


/* ---- Cleaning methods and attribute initiation methods ---- */

// Free memory allocations of a route entry object
static void free_memory(RouteEntry *self);

// Initialise and associate a new prefix object with a route entry
static int init_prefix(RouteEntry *self, PyObject *prefix);


/* ---- Python builtin functions ---- */


// Rich comparator
static PyObject *re_richcmp(PyObject *obj1, PyObject *obj2, int op);

// To string
static PyObject *re_str(RouteEntry *obj);

// Hash method
static Py_hash_t re_hash(RouteEntry *obj);

// Deep copy
static PyObject *re_deepcopy(RouteEntry *self, PyObject *memo);

// Retrieve state (serialize)
static PyObject *re_getstate(RouteEntry *self);

// Restore object from state (de-serialize)
static PyObject *re_setstate(RouteEntry *self, PyObject *d);


/* ---- Helper methods ---- */


// Compare to route entry entry objects
static int re_compare(RouteEntry *obj1, RouteEntry *obj2);

// Check if two route entry tables are equal
static int compare_lists(uint32_t *list1, uint32_t *list2,
        uint16_t size1, uint16_t size2);


/* ---- Table helper methods (internal use only) ---- */


// Get the as set as a list
static PyObject *get_as_set_list(RouteEntry *obj);

// Get the communities as a list
static PyObject *get_communities_list(RouteEntry *obj);


/* ---- Python attributes getter and setters functions ---- */


// Get the as path
static PyObject *re_as_path(RouteEntry *obj);

// Set the as path of a route entry
static PyObject *re_set_as_path(RouteEntry *obj, PyObject *as_path);

// Get the as set
static PyObject *re_as_set(RouteEntry *obj);

// Add elements to the as set
static PyObject *re_add_as_set(RouteEntry *self, PyObject *as_set);

// Get the communities
static PyObject *re_communities(RouteEntry *obj);

// Add communities
static PyObject *re_add_communities(RouteEntry *self, PyObject *com);

// Remove communities
static PyObject *re_remove_communities(RouteEntry *self, PyObject *com);

// Set the nexthop of a route entry
static PyObject *re_set_nexthop(RouteEntry *obj, PyObject *nexthop);

// Save/load route entry into/from a buffer
static PyObject *save_to_buffer(RouteEntry *self, PyObject *arg);
static PyObject *save_to_buffer_impl(RouteEntry *self, Py_buffer *buffer);
static PyObject *load_from_buffer(RouteEntry *self, PyObject *arg);
static PyObject *load_from_buffer_impl(RouteEntry *self, Py_buffer *buffer);
static PyObject *create_from_buffer(PyObject *cls, PyObject *arg);

/* ---- Python module functions ---- */


// Get an as path announce string component (ExaBGP format)
static PyObject *re_announce_as_path_str(RouteEntry *obj);

// Get a community announce string component (ExaBGP format)
static PyObject *re_announce_communities_str(RouteEntry *obj);


/* ---- Type configuration ---- */


// Member variable definition
static PyMemberDef re_members[] = {
    {"origin", T_UBYTE, offsetof(RouteEntry, origin), READONLY, "Route entry origin"},
    {"peer", T_UINT, offsetof(RouteEntry, peer), READONLY, "Route entry peer asn"},
    {"prefix", T_OBJECT, offsetof(RouteEntry, prefix), READONLY, "Route entry prefix object"},
    {"nexthop", T_STRING, offsetof(RouteEntry, nexthop), READONLY, "Route entry nexthop"},
    {"preference", T_UINT, offsetof(RouteEntry, preference), READONLY, "Route entry preference"},
    {NULL}  /* Sentinel */
};

// Method definitions
static PyMethodDef re_methods[] = {
    {"get_announce_as_path_string", (PyCFunction)re_announce_as_path_str, METH_NOARGS,
     "Return the route entry as path announcement string"},
    {"get_announce_communities_string", (PyCFunction)re_announce_communities_str, METH_NOARGS,
     "Return the route entry communities announcement string"},
    {"add_communities", (PyCFunction)re_add_communities, METH_O,
     "Add communities to the route entry"},
    {"remove_communities", (PyCFunction)re_remove_communities, METH_O,
     "Remove communities from the route entry"},
    {"communities", (PyCFunction)re_communities, METH_NOARGS,
     "Return a set of community tuples of the prefix"},
    {"as_path", (PyCFunction)re_as_path, METH_NOARGS,
     "Return the as path of the route entry"},
    {"set_as_path", (PyCFunction)re_set_as_path, METH_O,
     "Update the AS path to a new list"},
    {"as_set", (PyCFunction)re_as_set, METH_NOARGS,
     "Return the AS set of the route entry"},
    {"add_as_set", (PyCFunction)re_add_as_set, METH_O,
     "Add elements to the as set of the route entry"},
    {"set_nexthop", (PyCFunction)re_set_nexthop, METH_O,
     "Update the nexthop attribute of a route entry"},
    {"save_to_buffer", (PyCFunction)save_to_buffer, METH_O,
     "Pack the route entry into a given buffer"},
    {"load_from_buffer", (PyCFunction)load_from_buffer, METH_O,
     "Unpack the route entry from a given buffer into an existing one"},
    {"create_from_buffer", (PyCFunction)create_from_buffer, METH_O|METH_CLASS,
     "Unpack the route entry from a given buffer and create a new one"},

    {"__deepcopy__", (PyCFunction)re_deepcopy, METH_O,
     "Perform a deep copy of a route entry object"},
    {"__getstate__", (PyCFunction)re_getstate, METH_NOARGS,
     "Retrieve the state dictionary for pickling"},
    {"__setstate__", (PyCFunction)re_setstate, METH_O,
     "Restore an object from a state dictionary for unpickling"},
    {NULL}  /* Sentinel */
};

// Configure the type
static PyTypeObject RouteEntryType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "RouteEntry.RouteEntry",   /* tp_name */
    sizeof(RouteEntry),        /* tp_basicsize */
    0,                         /* tp_itemsize */
    (destructor)re_dealloc,    /* tp_dealloc */
    0,                         /* tp_print */
    0,                         /* tp_getattr */
    0,                         /* tp_setattr */
    0,                         /* tp_reserved */
    (reprfunc)re_str,          /* tp_repr */
    0,                         /* tp_as_number */
    0,                         /* tp_as_sequence */
    0,                         /* tp_as_mapping */
    (hashfunc)re_hash,         /* tp_hash  */
    0,                         /* tp_call */
    (reprfunc)re_str,          /* tp_str */
    0,                         /* tp_getattro */
    0,                         /* tp_setattro */
    0,                         /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT,        /* tp_flags */
    "Route Entry objects",     /* tp_doc */
    0,                         /* tp_traverse */
    0,                         /* tp_clear */
    (richcmpfunc)re_richcmp,   /* tp_richcompare */
    0,                         /* tp_weaklistoffset */
    0,                         /* tp_iter */
    0,                         /* tp_iternext */
    re_methods,                /* tp_methods */
    re_members,                /* tp_members */
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    (initproc)re_init,         /* tp_init */
    0,                         /* tp_alloc */
    re_new,                    /* tp_new */
};

// Define the module
static PyModuleDef remodule = {
    PyModuleDef_HEAD_INIT,
    "RouteEntry",
    "Route Entry module",
    -1,
    NULL, NULL, NULL, NULL, NULL
};

#endif /* ROUTEENTRY_H */
