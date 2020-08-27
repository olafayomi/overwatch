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

#include <stdint.h>
#include <arpa/inet.h>

#include "RouteEntry.h"
#include "prefixtypes.h"

// ========================== HELPER INTERNAL METHODS ==========================


/* Free the memeory used by a route entry object */
static void free_memeory(RouteEntry *self) {
    if (self->nexthop != NULL)
        free(self->nexthop);
    if (self->as_path != NULL)
        free(self->as_path);
    if (self->as_set != NULL)
        free(self->as_set);
    if (self->communities != NULL)
        free(self->communities);
    if (self->prefix != NULL)
        Py_DECREF(self->prefix);
}

/*
    Validate, initiate and associate a prefix to a route entry.
    Returns -1 if an error occurs, 0 otherwise.
*/
static int init_prefix(RouteEntry *self, PyObject *prefix) {
    // Import the prefix module method to initiate it
    PyObject *prefIMP = PyImport_ImportModule("Prefix");
    PyObject *moduleDict = PyModule_GetDict(prefIMP);
    PyObject *IPv4Type = PyDict_GetItemString(moduleDict, "IPv4");
    PyObject *IPv6Type = PyDict_GetItemString(moduleDict, "IPv6");
    PyObject *PrefixFactory = PyDict_GetItemString(moduleDict, "Prefix");

    // Check if prefix is a prefix object
    if (
        (PyObject_IsInstance(prefix, IPv4Type)) ||
        (PyObject_IsInstance(prefix, IPv6Type))
    ) {
        // Free the imports and save a reference to the passed prefix
        Py_XDECREF(prefIMP);
        self->prefix = prefix;
        Py_XINCREF(self->prefix);
    } else if (PyUnicode_Check(prefix)) {
        // Call the factory to build the object
        PyObject *args = Py_BuildValue("(O)", prefix);
        PyObject *obj = PyObject_CallObject(PrefixFactory, args);
        Py_XDECREF(args);
        Py_XDECREF(prefIMP);
        if (obj == NULL)
            return -1;

        self->prefix = obj;
    } else {
        // Raise an error as we received an unkown type
        Py_XDECREF(prefIMP);
        PyErr_SetString(PyExc_AttributeError, "Prefix has to be a Prefix object or a string");
        return -1;
    }

    return 0;
}

/*
    Compare two unsigned int route entry tables. If the tables are the same
    we will return 1. If they are different 1 is retruned. For two tables
    to be the same they must have the same elements and number of elements.
*/
static int table_equal(
    unsigned int *tbl1, unsigned int *tbl2,
    unsigned short tbl1_size, unsigned short tbl2_size) {
    if (tbl1_size == 0 && tbl1_size == tbl2_size)
        return 1;

    if (tbl1_size != tbl2_size)
        return 0;

    // Iterate through the tables and see if we can find
    // a different value
    for (int i = 0; i < tbl1_size; i++) {
        if (*(tbl1+i) != *(tbl2+i))
            return 0;
    }

    // Tables are the same
    return 1;
}

/*
    Check if there is a difference between two set items.
    The difference of set A is defined as elements in A that
    are not in B. Returns 1 if there is a difference, 0 otherwise.
    If an error occurs -1 is returned.
*/
static int set_difference(PyObject *a, PyObject *b) {
    PyObject *aSet = PySet_New(a);
    if (aSet == NULL)
        return -1;

    int size = PySet_Size(aSet);
    for (int i = 0; i < size; i++) {
        PyObject *obj = PySet_Pop(aSet);
        if (obj == NULL) {
            Py_DECREF(aSet);
            return -1;
        }

        // Check if set b contains the key
        int check = PySet_Contains(b, obj);

        Py_DECREF(obj);
        if (check == 0) {
            Py_DECREF(aSet);
            return 1;
        } else if (check == -1) {
            Py_DECREF(aSet);
            return -1;
        }
    }

    Py_DECREF(aSet);
    return 0;
}

/*
    Return the as set as a Python list object. If an error occurs null is returned
    and the error string message is set.
*/
static PyObject *get_as_set_list(RouteEntry *obj) {
    PyObject *as_set = PyList_New(obj->as_set_size);
    for (int i = 0; i < obj->as_set_size; i++) {
        if (PyList_SetItem(as_set, i, PyLong_FromLong((long) *(obj->as_set+i))) == -1) {
            Py_XDECREF(as_set);
            return NULL;
        }
    }
    return as_set;
}

/*
    Return the communities as a python list object. The typels are flatened
    one after each other. If an error is encountered null is returned and
    the error message is set.
*/
static PyObject *get_communities_list(RouteEntry *obj) {
    PyObject *com = PyList_New(obj->communities_size);
    for (int i = 0; i < obj->communities_size; i++) {
        if (PyList_SetItem(com, i, PyLong_FromLong((long) *(obj->communities+i))) == -1) {
            Py_XDECREF(com);
            return NULL;
        }
    }
    return com;
}

/*
    Compare two Route entry objects and return a int describing their ordering
    -1 = obj1 is lower than obj2
     1 = obj1 is higher than obj2
     0 = obj1 is equal to obj2
*/
static int re_compare(RouteEntry *obj1, RouteEntry *obj2) {
    // Highet local preference should sort first
    if (obj1->preference > obj2->preference)
        return -1;
    else if (obj1->preference < obj2->preference)
        return 1;

    // Shortest as path should sort first
    if (obj1->as_path_size < obj2->as_path_size)
        return -1;
    else if (obj1->as_path_size > obj2->as_path_size)
        return 1;

    // Lowest origin should sort first
    if (obj1->origin < obj2->origin)
        return -1;
    else if (obj1->origin > obj2->origin)
        return 1;

    // Lowest peer ASN
    if (obj1->peer < obj2->peer)
        return -1;
    else if (obj1->peer > obj2->peer)
        return 1;

    // Lowest nexthop (python string compare)
    PyObject *nh1 = PyUnicode_FromString(obj1->nexthop);
    PyObject *nh2 = PyUnicode_FromString(obj2->nexthop);

    int nhCompareRes = PyUnicode_Compare(nh1, nh2);
    Py_XDECREF(nh1);
    Py_XDECREF(nh2);

    if (nhCompareRes != 0)
        return nhCompareRes;

    // Compare the as path of the objects
    PyObject *ap1 = re_as_path(obj1);
    PyObject *ap2 = re_as_path(obj2);
    int abCompareLtRes = PyObject_RichCompareBool(ap1, ap2, Py_LT);
    int abCompareGtRes = PyObject_RichCompareBool(ap1, ap2, Py_GT);
    Py_XDECREF(ap1);
    Py_XDECREF(ap2);
    if (abCompareLtRes == 1)
        return -1;
    else if (abCompareGtRes == 1)
        return 1;

    // Compare the as set
    if (table_equal(obj1->as_set, obj2->as_set,
            obj1->as_set_size, obj2->as_set_size) != 1) {
        if (obj1->as_set_size == 0)
            return -1;
        else if (obj2->as_set_size == 0)
            return 1;

        // Get the two sets
        PyObject *asSet1 = re_as_set((RouteEntry *)obj1);
        PyObject *asSet2 = re_as_set((RouteEntry *)obj2);

        if (set_difference(asSet1, asSet2) == 1) {
            Py_XDECREF(asSet1);
            Py_XDECREF(asSet2);
            return -1;
        } else if (set_difference(asSet2, asSet1) == 1) {
            Py_XDECREF(asSet1);
            Py_XDECREF(asSet2);
            return 1;
        }

        Py_XDECREF(asSet1);
        Py_XDECREF(asSet2);
    }

    // Compare the communities
    if (table_equal(obj1->communities, obj2->communities,
            obj1->communities_size, obj2->communities_size) != 1) {

        // Check if any of the unequal sets are empty
        if (obj1->communities_size == 0)
            return -1;
        else if (obj2->communities_size == 0)
            return 1;

        // Get the two sets
        PyObject *comSet1 = re_communities((RouteEntry *)obj1);
        PyObject *comSet2 = re_communities((RouteEntry *)obj2);

        // Check the differences of the two sets
        if (set_difference(comSet1, comSet2) == 1) {
            Py_XDECREF(comSet1);
            Py_XDECREF(comSet2);
            return -1;
        } else if (set_difference(comSet2, comSet1) == 1) {
            Py_XDECREF(comSet1);
            Py_XDECREF(comSet2);
            return 1;
        }

        Py_XDECREF(comSet1);
        Py_XDECREF(comSet2);
    }

    return 0;
}


// ========================== PYTHON METHODS  ==========================


/* Deallocate a route entry object */
static void re_dealloc(RouteEntry *self) {
    free_memeory(self);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

/* Method called when the a new object is created */
static PyObject *re_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
    RouteEntry *self;
    self = (RouteEntry *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->origin = ORIGIN_IGP;
        self->peer = 0;
        self->prefix = NULL;
        self->nexthop = NULL;

        self->as_path_size = 0;
        self->as_path = NULL;

        self->as_set_size = 0;
        self->as_set = NULL;

        self->preference = DEFAULT_LOCAL_PREF;

        self->communities_size = 0;
        self->communities = NULL;
    }

    return (PyObject *)self;
}

/*Initiate a new route entry object */
static int re_init(RouteEntry *self, PyObject *args, PyObject *kwds) {
    static char *kwlist[] = {"origin", "peer", "prefix", "nexthop",
            "as_path", "as_set", "communities", "preference", NULL};

    PyObject *prefix = NULL;
    PyObject *as_path = NULL;
    PyObject *nexthop = NULL;
    PyObject *as_set = NULL;
    PyObject *communities = NULL;

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "bIOO|OOOI", kwlist,
               &self->origin, &self->peer, &prefix, &nexthop,
                &as_path, &as_set, &communities, &self->preference))
        return -1;

    // If we got a string nexthop save it
    if (PyUnicode_Check(nexthop))
        self->nexthop = strdup(PyUnicode_AsUTF8(nexthop));
    // Otherwise set it to a default value
    else
        self->nexthop = strdup("");

    // Initiate the prefix
    if (init_prefix(self, prefix) == -1)
        return -1;

    // Process and save the AS path
    if (as_path != NULL && as_path != Py_None) {
        if (re_set_as_path(self, as_path) == NULL)
            return -1;
    }

    // Process the AS set if provied
    if (as_set != NULL && as_set != Py_None) {
        if ((!PyList_Check(as_set)) && (!PySet_Check(as_set))) {
            PyErr_SetString(PyExc_AttributeError,
                "AS set has to be either a list or a set instance");
            return -1;
        }

        // Turn the list to a set or make a new set (preserve the initial arguments as pop
        // will destroy the list)
        as_set = PySet_New(as_set);

        // If we have items allocate space in our as set table
        self->as_set_size = (unsigned short)PySet_Size(as_set);
        if (self->as_set_size > 0)
            self->as_set = malloc(self->as_set_size * sizeof(unsigned int));

        for (int i = 0; i < self->as_set_size; i++) {
            PyObject *obj = PySet_Pop(as_set);
            if (obj == NULL) {
                Py_DECREF(as_set);
                return -1;
            }

            // If the item is a string convert it to a python number
            if (PyUnicode_Check(obj)) {
                PyObject *tmp = obj;
                obj = PyLong_FromUnicodeObject(obj, 10);
                Py_DECREF(tmp);

                // Check if conversion from string to python int (long) failed
                if (obj == NULL) {
                    Py_DECREF(as_set);
                    return -1;
                }
            }

            // Process a python number
            if (PyLong_Check(obj)) {
                unsigned long v = PyLong_AsUnsignedLong(obj);
                if (v > 0xffffffff) {
                    Py_DECREF(obj);
                    Py_DECREF(as_set);
                    PyErr_SetString(PyExc_AttributeError,
                        "Overflow ASN number error (must be max 32 bits)");
                    return -1;
                }
                *(self->as_set+i) = (unsigned int)v;
            } else {
                // Unkown format was encountered, raise an error
                Py_DECREF(obj);
                Py_DECREF(as_set);
                PyErr_SetString(PyExc_AttributeError,
                    "ASN set can only contain numbers and strings");
                return -1;
            }

            // Free the set item
            Py_DECREF(obj);
        }

        // Free the created set
        Py_DECREF(as_set);
    }

    // Process and save the communities if provided
    if (communities != NULL && communities != Py_None) {
        // Use the python community parser to covert to a list of tuple integers
        PyObject *comParseIMP = PyImport_ImportModule("CommunityParser");
        PyObject *moduleDict = PyModule_GetDict(comParseIMP);
        PyObject *comParser = PyDict_GetItemString(moduleDict,
            "communities_to_tuple_array");

        PyObject *args = Py_BuildValue("(O)", communities);
        communities = PyObject_CallObject(comParser, args);
        Py_XDECREF(args);
        Py_XDECREF(comParseIMP);
        if (communities == NULL)
            return -1;

        // If we have items allocate space in our table
        self->communities_size = (unsigned short)PyList_Size(communities)*2;
        if (self->communities_size > 0)
            self->communities = malloc(self->communities_size * sizeof(unsigned int));

        // Save to our table
        for (int i = 0; i < self->communities_size; i++) {
            PyObject *obj = PyList_GetItem(communities, (i/2));
            PyObject *t1 = PyTuple_GetItem(obj, 0);
            PyObject *t2 = PyTuple_GetItem(obj, 1);

            // TODO: ADD SOME VALIDATION CHECKS???? (technically the
            // parsing method is quite strict)

            // Save the first element of the tuple
            unsigned long v = PyLong_AsUnsignedLong(t1);
            if (v > 0xffffffff) {
                Py_DECREF(communities);
                PyErr_SetString(PyExc_AttributeError,
                    "Overflown first community tuple number (must be max 32 bits)");
                return -1;
            }
            *(self->communities+i) = (unsigned int)v;

            // Save the second element to the tuple
            i++;
            v = PyLong_AsUnsignedLong(t2);
            if (v > 0xffffffff) {
                Py_DECREF(communities);
                PyErr_SetString(PyExc_AttributeError,
                    "Overflown second community tuple number (must be max 32 bits)");
                return -1;
            }
            *(self->communities+i) = (unsigned int)v;
        }

        Py_DECREF(communities);
    }

    return 0;
}

/* Rich comparator method that compares two objects and returns a result */
static PyObject *re_richcmp(PyObject *obj1, PyObject *obj2, int op)
{
    int c = 0, cmp_res;

    // Validate the type of the objects we are comparing
    if (!PyObject_IsInstance(obj1, (PyObject*)&RouteEntryType)) {
        PyErr_SetString(PyExc_AttributeError, "Can only compare route entry objects");
        return NULL;
    }

    if (!PyObject_IsInstance(obj2, (PyObject*)&RouteEntryType)) {
        PyErr_SetString(PyExc_AttributeError, "Can only compare route entry objects");
        return NULL;
    }

    // Compare the two objects
    cmp_res = re_compare((RouteEntry *)obj1, (RouteEntry *)obj2);

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

/* Get a string representation of the route entry */
static PyObject *re_str(RouteEntry *obj) {
    PyObject *as_path = re_as_path(obj);
    if (as_path == NULL)
        return NULL;

    PyObject *res = PyUnicode_FromFormat("%S peer %u (nexthop: %s %S)", obj->prefix,
            obj->peer, obj->nexthop, as_path);
    Py_XDECREF(as_path);
    return res;
}

/* Hash function */
static Py_hash_t re_hash(RouteEntry *obj){
    Py_hash_t res;
    PyObject *tup = Py_BuildValue("(OIsB)", obj->prefix, obj->peer, obj->nexthop, obj->origin);
    res = PyObject_Hash(tup);
    Py_XDECREF(tup);
    return res;
}

/* Return the state of the object (for pickling) */
static PyObject *re_getstate(RouteEntry *self) {
    PyObject *as_path = re_as_path(self);
    PyObject *as_set = get_as_set_list(self);
    PyObject *communities = get_communities_list(self);

    PyObject *res = Py_BuildValue("{sBsIsOsssOsOsOsI}",
            "origin", self->origin, "peer", self->peer, "prefix", self->prefix,
            "nexthop", self->nexthop, "as_path", as_path, "as_set", as_set,
            "communities", communities, "preference", self->preference);

    Py_XDECREF(as_path);
    Py_XDECREF(as_set);
    Py_XDECREF(communities);
    return res;
}

/* Restore the state of a object based on a state dictionary (for pickling) */
static PyObject *re_setstate(RouteEntry *self, PyObject *d) {
    PyObject *origin = PyDict_GetItemString(d, "origin");
    PyObject *peer = PyDict_GetItemString(d, "peer");
    PyObject *prefix = PyDict_GetItemString(d, "prefix");
    PyObject *nexthop = PyDict_GetItemString(d, "nexthop");
    PyObject *as_path = PyDict_GetItemString(d, "as_path");
    PyObject *as_set = PyDict_GetItemString(d, "as_set");
    PyObject *com = PyDict_GetItemString(d, "communities");
    PyObject *preference = PyDict_GetItemString(d, "preference");

    // make sure the dictionary has all fields
    if ((origin == NULL) || (peer == NULL) || (prefix == NULL) ||
        (nexthop == NULL) || (as_path == NULL) || (as_set == NULL) ||
        (com == NULL) || (preference == NULL)) {
        PyErr_SetString(PyExc_AttributeError,
            "Invalid set state dictionary. Not all fields received");
        return NULL;
    }

    // Free up the old resources (if they exist)
    free_memeory(self);

    // ---------- Validate and restore the origin ----------
    if (!PyLong_Check(origin)) {
        PyErr_SetString(PyExc_AttributeError,
            "Invalid dictionary item type (origin). Expected number");
        return NULL;
    }

    long val = PyLong_AsLong(origin);
    if (!(val >= 0 && val <= 2)) {
        PyErr_SetString(PyExc_AttributeError,
            "Invalid dictionary value (origin)");
        return NULL;
    }
    self->origin = (unsigned char)val;

    // ---------- Validate and restore the peer ASN ----------
    if (!PyLong_Check(peer)) {
        PyErr_SetString(PyExc_AttributeError,
            "Invalid dictionary item type (peer). Expected number");
        return NULL;
    }

    val = PyLong_AsLong(peer);
    if (!(val >= 0 && val <= 0xffffffff)) {
        PyErr_SetString(PyExc_AttributeError,
            "Invalid dictionary value (peer)");
        return NULL;
    }
    self->peer = (unsigned int)val;

    // ---------- Validate and restore the prefix ----------
    if (init_prefix(self, prefix) == -1)
        return NULL;

    // ---------- Validate and restore the next hop ----------
    if (!PyUnicode_Check(nexthop)) {
        PyErr_SetString(PyExc_AttributeError,
            "Invalid dictionary item type (nexthop). Expected string");
        return NULL;
    }

    char *strVal = PyUnicode_AsUTF8(nexthop);
    if (strVal == NULL) {
        PyErr_SetString(PyExc_AttributeError,
            "Invalid dictionary value (nexthop)");
        return NULL;
    }
    self->nexthop = strdup(strVal);


    // ---------- Validate and restore the as_path ----------
    if (!PyList_Check(as_path)) {
        PyErr_SetString(PyExc_AttributeError,
            "Invalid dictionary item type (as_path). Expected list");
        return NULL;
    }

    self->as_path_size = (unsigned short)PyList_Size(as_path);
    if (self->as_path_size > 0)
        self->as_path = malloc(self->as_path_size * sizeof(unsigned int));

    for (int i = 0; i < self->as_path_size; i++) {
        PyObject *obj = PyList_GetItem(as_path, i);
        if (!obj)
            return NULL;

        if (PyLong_Check(obj)) {
            unsigned long v = PyLong_AsUnsignedLong(obj);
            if (v > 0xffffffff) {
                PyErr_SetString(PyExc_AttributeError,
                    "Invalid dictionary child value (as_path). Overflow Error");
                return NULL;
            }
            *(self->as_path+i) = (unsigned int)v;
        } else {
            PyErr_SetString(PyExc_AttributeError,
                "Invalid dictionary child type (as_path). Expected number");
            return NULL;
        }
    }

    // ---------- Validate and restore the as_set ----------
    if (!PyList_Check(as_set)) {
        PyErr_SetString(PyExc_AttributeError,
            "Invalid dictionary item type (as_set). Expected list");
        return NULL;
    }

    self->as_set_size = (unsigned short)PyList_Size(as_set);
    if (self->as_set_size > 0)
        self->as_set = malloc(self->as_set_size * sizeof(unsigned int));

    for (int i = 0; i < self->as_set_size; i++) {
        PyObject *obj = PyList_GetItem(as_set, i);
        if (!obj)
            return NULL;

        if (PyLong_Check(obj)) {
            unsigned long v = PyLong_AsUnsignedLong(obj);
            if (v > 0xffffffff) {
                PyErr_SetString(PyExc_AttributeError,
                    "Invalid dictionary child value (as_set). Overflow Error");
                return NULL;
            }
            *(self->as_set+i) = (unsigned int)v;
        } else {
            PyErr_SetString(PyExc_AttributeError,
                "Invalid dictionary child type (as_set). Expected number");
            return NULL;
        }
    }

    // ---------- Validate and restore the communities ----------
    if (!PyList_Check(com)) {
        PyErr_SetString(PyExc_AttributeError,
            "Invalid dictionary item type (communities). Expected list");
        return NULL;
    }

    self->communities_size = (unsigned short)PyList_Size(com);
    if (self->communities_size > 0)
        self->communities = malloc(self->communities_size * sizeof(unsigned int));

    for (int i = 0; i < self->communities_size; i++) {
        PyObject *obj = PyList_GetItem(com, i);
        if (!obj)
            return NULL;

        if (PyLong_Check(obj)) {
            unsigned long v = PyLong_AsUnsignedLong(obj);
            if (v > 0xffffffff) {
                PyErr_SetString(PyExc_AttributeError,
                    "Invalid dictionary child value (communities). Overflow Error");
                return NULL;
            }
            *(self->communities+i) = (unsigned int)v;
        } else {
            PyErr_SetString(PyExc_AttributeError,
                "Invalid dictionary child type (communities). Expected number");
            return NULL;
        }
    }

    Py_RETURN_NONE;
}

/* Make a deep copy of a route entry object */
static PyObject *re_deepcopy(RouteEntry *self, PyObject *memo) {
    // Allocate and initiate a new object
    PyObject *obj = _PyObject_New(&RouteEntryType);
    obj = PyObject_Init(obj, &RouteEntryType);
    RouteEntry *result = (RouteEntry *)obj;

    PyDict_SetItem(memo, PyLong_FromVoidPtr(obj), (PyObject *)result);
    //XXX: Note that the ID is implemented in c python as the memeory address of the
    // object. Its defined by the builtin_id function (which we can't call). We will
    // get the memeory location by executing the functions method call to retrieve
    // the ID.

    // Copy the details of the object
    result->origin = self->origin;
    result->peer = self->peer;

    // XXX: SHOULD WE MAKE A NEW PREFIX???
    result->prefix = self->prefix;
    Py_XINCREF(result->prefix);

    result->nexthop = strdup(self->nexthop);

    // Make a copy of the tables
    result->as_path_size = self->as_path_size;
    if (result->as_path_size != 0)
        result->as_path = malloc(result->as_path_size * sizeof(unsigned int));
    else
        result->as_path = NULL;
    for (int i = 0; i < result->as_path_size; i++) {
        *(result->as_path+i) = *(self->as_path+i);
    }

    result->as_set_size = self->as_set_size;
    if (result->as_set_size != 0)
        result->as_set = malloc(result->as_set_size * sizeof(unsigned int));
    else
        result->as_set = NULL;
    for (int i = 0; i < result->as_set_size; i++) {
        *(result->as_set+i) = *(self->as_set+i);
    }

    result->communities_size = self->communities_size;
    if (result->communities_size != 0)
        result->communities = malloc(result->communities_size * sizeof(unsigned int));
    else
        result->communities = NULL;
    for (int i = 0; i < result->communities_size; i++) {
       *(result->communities+i) = *(self->communities+i);
    }

    // Set the preference and return the result
    result->preference = self->preference;
    return (PyObject *)result;
}


// ========================== PYTHON ATTRIBUTES ==========================


/*
    Return the route entries as path as a Python list object. If an error occurs
    null is returned and the error string message is set.
*/
static PyObject *re_as_path(RouteEntry *obj) {
    PyObject *as_path = PyList_New(obj->as_path_size);
    for (int i = 0; i < obj->as_path_size; i++) {
        if (PyList_SetItem(as_path, i, PyLong_FromLong((long) *(obj->as_path+i))) == -1) {
            Py_XDECREF(as_path);
            return NULL;
        }
    }
    return as_path;
}

/*
    Update the as path table with a list of as paths. Returns NULL on failure
    and Py_None on success.
*/
static PyObject *re_set_as_path(RouteEntry *obj, PyObject *as_path) {
    if (!PyList_Check(as_path)) {
        PyErr_SetString(PyExc_AttributeError, "AS path has to be a list");
        return NULL;
    }

    unsigned short as_path_size = (unsigned short)PyList_Size(as_path);
    unsigned int *data = NULL;
    if (as_path_size > 0)
        data = malloc(as_path_size * sizeof(unsigned int));

    for (int i = 0; i < as_path_size; i++) {
        PyObject *obj = PyList_GetItem(as_path, i);
        if (!obj) {
            free(data);
            return NULL;
        }

        // Object is borrowed reference but if we have a string we have
        // a new reference. Increment the count to allow for easy handeling
        // (we will decrement automatically later)
        Py_INCREF(obj);

        // If the item is a string convert it to a python number
        if (PyUnicode_Check(obj)) {
            PyObject *tmp = obj;
            obj = PyLong_FromUnicodeObject(obj, 10);
            Py_DECREF(tmp);

            // Conversion from string to python int (long) failed
            if (!obj) {
                free(data);
                return NULL;
            }
        }

        // Process a python number
        if (PyLong_Check(obj)) {
            unsigned long v = PyLong_AsUnsignedLong(obj);
            if (v > 0xffffffff) {
                free(data);
                Py_DECREF(obj);
                PyErr_SetString(PyExc_AttributeError,
                    "Overflow ASN number error (must be max 32 bits)");
                return NULL;
            }
            *(data+i) = (unsigned int)v;
        } else {
            // Unkown format was encountered, raise an error
            free(data);
            Py_DECREF(obj);
            PyErr_SetString(PyExc_AttributeError,
                "ASN path list can only contain numbers and strings");
            return NULL;
        }

        Py_DECREF(obj);
    }

    // If we alredy have a allocated table free it
    if (obj->as_path_size != 0)
        free(obj->as_path);

    if (as_path_size == 0) {
        obj->as_path = NULL;
        obj->as_path_size = 0;
    } else {
        obj->as_path = data;
        obj->as_path_size = as_path_size;
    }

    Py_RETURN_NONE;
}

/*
    Return the as set of the route entry as a python set.
    As per the module convetion if the as set is mepty we will
    return py none
*/
static PyObject *re_as_set(RouteEntry *obj) {
    PyObject *as_set = get_as_set_list(obj);
    if (as_set == NULL)
        return NULL;

    // Return Py None (empty as set)
    if (PyList_Size(as_set) == 0) {
        Py_DECREF(as_set);
        Py_RETURN_NONE;
    }

    // Convert the list to a set and return the result
    PyObject *res = PySet_New(as_set);
    Py_DECREF(as_set);
    return res;
}

/* Add elements to the as set table of the route entry */
static PyObject *re_add_as_set(RouteEntry *self, PyObject *as_set) {
    // Make sure the attribute is a list or a set element
    if ((!PyList_Check(as_set)) && (!PySet_Check(as_set))) {
        PyErr_SetString(PyExc_AttributeError,
            "AS set has to be either a set attribute or a list");
        return NULL;
    }

    // Copy an existing set or turn a list to as set
    PyObject *set = PySet_New(as_set);
    if (set == NULL)
        return NULL;

    // Declare an array to allow filtering of as-set items
    // (only add if not in as path)
    unsigned int dataList[PySet_Size(set)];
    int dataIndex = 0;

    // Iterate through the as set
    int set_size = PySet_Size(set);
    for (int i = 0; i < set_size; i++) {
        // Pop a item from the set
        PyObject *obj = PySet_Pop(set);
        if (obj == NULL) {
            Py_DECREF(set);
            return NULL;
        }

        // Parse and validate the asn
        unsigned long v = PyLong_AsUnsignedLong(obj);
        if (v > 0xffffffff) {
            Py_DECREF(set);
            Py_DECREF(obj);
            PyErr_SetString(PyExc_AttributeError,
                "Overflown first community tuple number (must be max 32 bits)");
            return NULL;
        }

        // Free the pop-ed set value
        Py_DECREF(obj);

        // Check if we alredy have the item in our set table
        int found = 0;
        for (int j = 0; j < self->as_set_size; j++) {
            if ((unsigned int)v == *(self->as_set+j)) {
                found = -1;
                break;
            }
        }

        // If the item is alredy in our as set just skip it
        if (found == -1)
            continue;

        // Only add the as set item if its not present in the as path list
        for (int j = 0; j < self->as_path_size; j++) {
            if ((unsigned int)v == *(self->as_path+j)) {
                found = 1;
                break;
            }
        }

        // If the item is in neither the as path and set add it to the data array
        if (found == 0) {
            dataList[dataIndex] = (unsigned int)v;
            dataIndex++;
        }
    }

    // Free the set
    Py_DECREF(set);

    unsigned short new_size = self->as_set_size;

    // Resize our community table if we have more elements to add
    if (dataIndex > 0) {
        new_size += dataIndex;
        void *ptr = realloc(self->as_set, new_size * sizeof(unsigned int));
        if (ptr == NULL) {
            PyErr_SetString(PyExc_MemoryError,
                "Can't resize as-set table. Operation falied");
            return NULL;
        }
        self->as_set = ptr;
    }

    // Add the filtered asn to the table
    for (int i = 0; i < dataIndex; i++) {
        *(self->as_set+self->as_set_size+i) = dataList[i];
    }
    self->as_set_size = new_size;

    Py_RETURN_NONE;
}

/*
    Reconstruct and return a set of communities two element tuples.
    As per the module convetion if the communities set is empty we
    will return None.
*/
static PyObject *re_communities(RouteEntry *obj) {
    int num_tuples = obj->communities_size/2;
    // If the set is empty return Py None
    if (num_tuples == 0)
        Py_RETURN_NONE;

    PyObject *com = PyList_New(num_tuples);
    for (int i = 0; i < obj->communities_size; i++) {
        PyObject *tup = PyTuple_New(2);
        if (PyTuple_SetItem(tup, 0, PyLong_FromLong((long) *(obj->communities+i))) != 0) {
            Py_XDECREF(tup);
            Py_XDECREF(com);
            return NULL;
        }

        i++;
        if (PyTuple_SetItem(tup, 1, PyLong_FromLong((long) *(obj->communities+i))) != 0) {
            Py_XDECREF(tup);
            Py_XDECREF(com);
            return NULL;
        }

        // Add the tuple to the list
        if (PyList_SetItem(com, ((i-1)/2), tup) != 0) {
            Py_XDECREF(tup);
            Py_XDECREF(com);
            return NULL;
        }
    }

    PyObject *res = PySet_New(com);
    Py_XDECREF(com);
    return res;
}


/* Add communities to the communities table of the route entry */
static PyObject *re_add_communities(RouteEntry *self, PyObject *com) {
    // Validate the attribute
    if (PyList_Size(com) == 0)
        Py_RETURN_NONE;

    if (!PyList_Check(com)) {
        PyErr_SetString(PyExc_AttributeError,
            "Invalid community attribute. Expected list");
        return NULL;
    }

    // Declare an array to allow set-like filtering (don't re add
    // already added communities)
    unsigned int dataList[PyList_Size(com)*2];
    int dataIndex = 0;

    // Iterate through the community tuples
    for (int i = 0; i < PyList_Size(com); i++) {
        PyObject *obj = PyList_GetItem(com, i);
        if (obj == NULL)
            return NULL;

        if ((!PyTuple_Check(obj)) || (PyTuple_Size(obj) != 2)) {
            PyErr_SetString(PyExc_AttributeError,
                "Attribute has to be a list of 2 element tuples");
            return NULL;
        }

        PyObject *t1 = PyTuple_GetItem(obj, 0);
        PyObject *t2 = PyTuple_GetItem(obj, 1);

        // Parse and validate the first tuple
        unsigned long v1 = PyLong_AsUnsignedLong(t1);
        if (v1 > 0xffffffff) {
            PyErr_SetString(PyExc_AttributeError,
                "Overflown first community tuple number (must be max 32 bits)");
            return NULL;
        }

        // Parse and validate the second tuple
        unsigned long v2 = PyLong_AsUnsignedLong(t2);
        if (v2 > 0xffffffff) {
            PyErr_SetString(PyExc_AttributeError,
                "Overflown second community tuple number (must be max 32 bits)");
            return NULL;
        }

        // Iterate through the current community table to see if item exists alredy
        int found = 0;
        for (int j = 0; j < self->communities_size; j+=2) {
            if (
                ((unsigned int)v1 == *(self->communities+j)) &&
                ((unsigned int)v2 == *(self->communities+j+1))
            ) {
                found = 1;
                break;
            }
        }

        // If we haven't alredy seen the tuple add it to the data list to extend the
        // table with
        if (found == 0) {
            dataList[dataIndex] = (unsigned int)v1;
            dataList[dataIndex+1] = (unsigned int)v2;
            dataIndex+=2;
        }
    }

    unsigned short new_size = self->communities_size;

    // Resize our community table if we have more elements to add
    if (dataIndex > 0) {
        new_size += dataIndex;
        void *ptr = realloc(self->communities, new_size * sizeof(unsigned int));
        if (ptr == NULL) {
            PyErr_SetString(PyExc_MemoryError,
                "Can't resize community table. Operation falied");
            return NULL;
        }
        self->communities = ptr;
    }

    // Add the filtered communities to the table
    for (int i = 0; i < dataIndex; i++) {
        *(self->communities+self->communities_size+i) = dataList[i];
    }
    self->communities_size = new_size;

    Py_RETURN_NONE;
}

/* Remove communities from the route entry */
static PyObject *re_remove_communities(RouteEntry *self, PyObject *com) {
    // Don't do any work if we don't have any communities
    if (self->communities_size == 0)
        Py_RETURN_NONE;

    // Convert the remove communities list to a set
    PyObject *set = PySet_New(com);
    if (set == NULL) {
        return NULL;
    }

    // iterate through the set of communities and remove them from our table
    int numElements = PySet_Size(set);
    int endIndex = self->communities_size - 1;
    for (int i = 0; i < numElements; i++) {
        PyObject *obj = PySet_Pop(set);
        if (obj == NULL) {
            Py_DECREF(set);
            return NULL;
        }

        if ((!PyTuple_Check(obj)) || (PyTuple_Size(obj) != 2)) {
            Py_DECREF(set);
            Py_DECREF(obj);
            PyErr_SetString(PyExc_AttributeError,
                "Attribute has to be a list of 2 element tuples");
            return NULL;
        }

        // Get the tuple items (borrowed reference)
        PyObject *t1 = PyTuple_GetItem(obj, 0);
        PyObject *t2 = PyTuple_GetItem(obj, 1);

        // Parse and validate the first tuple
        unsigned long v1 = PyLong_AsUnsignedLong(t1);
        if (v1 > 0xffffffff) {
            Py_DECREF(set);
            Py_DECREF(obj);
            PyErr_SetString(PyExc_AttributeError,
                "Overflown first community tuple number (must be max 32 bits)");
            return NULL;
        }

        // Parse and validate the second tuple
        unsigned long v2 = PyLong_AsUnsignedLong(t2);
        if (v2 > 0xffffffff) {
            Py_DECREF(set);
            Py_DECREF(obj);
            PyErr_SetString(PyExc_AttributeError,
                "Overflown second community tuple number (must be max 32 bits)");
            return NULL;
        }

        // Free the pop-ed set value (New refence)
        Py_DECREF(obj);

        // Iterate through the item to see if we can find it
        for (int j = 0; j < self->communities_size; j+=2) {
            if (
                ((unsigned int)v1 == *(self->communities+j)) &&
                ((unsigned int)v2 == *(self->communities+j+1))
            ) {
                if (j < (endIndex - 1)) {
                    // Swap the item to the end of the table (will be cut off in resize)
                    unsigned int tmp1 = *(self->communities+j);
                    unsigned int tmp2 = *(self->communities+j+1);
                    *(self->communities+j) = *(self->communities+endIndex-1);
                    *(self->communities+j+1) = *(self->communities+endIndex);
                    *(self->communities+endIndex-1) = tmp1;
                    *(self->communities+endIndex) = tmp2;
                }
                // Move the end index to the new position
                endIndex -= 2;
                break;
            }
        }
    }

    // Free the coppied set
    Py_DECREF(set);

    // Resize the communities table if we removed elements
    if (endIndex != (self->communities_size - 1)) {
        int newSize = endIndex + 1;
        if (newSize > 0) {
            // Reallocate the memeory section (make smaller)
            void *ptr = realloc(self->communities, newSize * sizeof(unsigned int));
            if (ptr == NULL) {
                PyErr_SetString(PyExc_MemoryError,
                    "Can't resize community table. Operation falied");
                return NULL;
            }

            // Update the new pointer and new size
            self->communities = ptr;
            self->communities_size = newSize;
        } else {
            // If the table is empty free the memory and set the size to 0
            free(self->communities);
            self->communities = NULL;
            self->communities_size = 0;
        }
    }

    Py_RETURN_NONE;
}

/* Update the nexthop attribute of a route entry */
static PyObject *re_set_nexthop(RouteEntry *obj, PyObject *nexthop) {
    // If we got a string nexthop update the old attribute
    if (PyUnicode_Check(nexthop)) {
        free(obj->nexthop);
        obj->nexthop = strdup(PyUnicode_AsUTF8(nexthop));
    } else {
        // Otherwise set a default value
        free(obj->nexthop);
        obj->nexthop = strdup("");
    }
    Py_RETURN_NONE;
}


// ========================== PYTHON MODULE METHODS ==========================


/* Generate and return the asn path announcement string (ExaBGP format) */
static PyObject *re_announce_as_path_str(RouteEntry *obj) {
    // Generate the as path string with a specific ExaBGP format
    PyObject *as_path = PyUnicode_FromString("");
    for (int i = 0; i < obj->as_path_size; i++) {
        PyObject *new_as_path;
        if (i == 0)
            new_as_path = PyUnicode_FromFormat("%U%u", as_path, *(obj->as_path+i));
        else
            new_as_path = PyUnicode_FromFormat("%U %u", as_path, *(obj->as_path+i));

        Py_XDECREF(as_path);
        as_path = new_as_path;
    }

    // Generate the as set string with a specific format
    PyObject *as_set = PyUnicode_FromString("");
    for (int i = 0; i < obj->as_set_size; i++) {
        PyObject *new_as_set = PyUnicode_FromFormat("%U %u", as_set, *(obj->as_set+i));
        Py_XDECREF(as_set);
        as_set = new_as_set;
    }

    if (obj->as_set_size > 0) {
        PyObject *new_as_set = PyUnicode_FromFormat("(%U )", as_set);
        Py_XDECREF(as_set);
        as_set = new_as_set;
    }

    PyObject *res;
    if (obj->as_set_size == 0)
        res = PyUnicode_FromFormat("as-path [%U]", as_path);
    else
        res = PyUnicode_FromFormat("as-path [%U %U]", as_path, as_set);

    Py_XDECREF(as_path);
    Py_XDECREF(as_set);
    return res;
}

/* Generate and return the community announcement string (ExaBGP format) */
static PyObject *re_announce_communities_str(RouteEntry *obj) {
    if (obj->communities_size == 0)
        return PyUnicode_FromFormat("");

    PyObject *com = PyUnicode_FromString("");
    for (int i = 0; i < obj->communities_size; i++) {
        PyObject *new_com;
        if ((i+2) == obj->communities_size) {
            new_com = PyUnicode_FromFormat("%U%u:%u", com,
                *(obj->communities+i), *(obj->communities+i+1));
        } else
            new_com = PyUnicode_FromFormat("%U%u:%u ", com,
                *(obj->communities+i), *(obj->communities+i+1));

        Py_XDECREF(com);
        com = new_com;
        i++;
    }

    PyObject *res = PyUnicode_FromFormat("community [%U]", com);
    Py_XDECREF(com);
    return res;
}

// ========================== INITIATE THE MODULE ==========================

// Register the types and the module
PyMODINIT_FUNC PyInit_RouteEntry(void) {
    PyObject *m;

    if (PyType_Ready(&RouteEntryType) < 0)
        return NULL;

    m = PyModule_Create(&remodule);
    if (m == NULL)
        return NULL;

    Py_INCREF(&RouteEntryType);
    PyModule_AddObject(m, "RouteEntry", (PyObject *)&RouteEntryType);

    // ADD THE STATIC ATTRIBUTES
    PyModule_AddObject(m, "DEFAULT_LOCAL_PREF",
            PyLong_FromLong(DEFAULT_LOCAL_PREF));
    PyModule_AddObject(m, "ORIGIN_IGP",
            PyLong_FromLong(ORIGIN_IGP));
    PyModule_AddObject(m, "ORIGIN_EGP",
            PyLong_FromLong(ORIGIN_EGP));
    PyModule_AddObject(m, "ORIGIN_INCOMPLETE",
            PyLong_FromLong(ORIGIN_INCOMPLETE));
    return m;
}

