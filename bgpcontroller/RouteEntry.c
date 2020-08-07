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

PyObject *IPv4Type = NULL;
PyObject *IPv6Type = NULL;
PyObject *PrefixFactory = NULL;
PyObject *comParser = NULL;

// ========================== HELPER INTERNAL METHODS ==========================


/*
 * Free the memory used by a route entry object.
 */
static void free_memory(RouteEntry *self) {
    if ( self->nexthop != NULL ) {
        free(self->nexthop);
        self->nexthop = NULL;
    }
    if ( self->as_path != NULL ) {
        free(self->as_path);
        self->as_path = NULL;
    }
    if ( self->as_set != NULL ) {
        free(self->as_set);
        self->as_set = NULL;
    }
    if ( self->communities != NULL ) {
        free(self->communities);
        self->communities = NULL;
    }
    if ( self->prefix != NULL ) {
        Py_DECREF(self->prefix);
        self->prefix = NULL;
    }
}


/*
 *  Validate, initialise and associate a prefix to a route entry.
 *  Returns -1 if an error occurs, 0 otherwise.
 */
static int init_prefix(RouteEntry *self, PyObject *prefix) {
    /* Check if prefix is a prefix object */
    if ( PyObject_IsInstance(prefix, IPv4Type) ||
            PyObject_IsInstance(prefix, IPv6Type) ) {
        /* It is a prefix object, save a reference to it */
        self->prefix = prefix;
        Py_XINCREF(self->prefix);
        return 0;
    }

    if ( PyUnicode_Check(prefix) ) {
        /* It is a string, create a prefix object from it */
        PyObject *args = Py_BuildValue("(O)", prefix);
        PyObject *obj = PyObject_CallObject(PrefixFactory, args);
        Py_XDECREF(args);
        if ( obj == NULL ) {
            return -1;
        }
        self->prefix = obj;
        return 0;
    }

    /* Not a prefix object or a string, raise an error */
    PyErr_SetString(PyExc_AttributeError,
            "Prefix has to be a Prefix object or a string");
    return -1;
}


static int parse_32bit_value(PyObject *obj, uint32_t *result) {
    uint64_t value;

    /* only operate on python long values */
    if ( !PyLong_Check(obj) ) {
        return -1;
    }

    value = PyLong_AsUnsignedLong(obj);

    /* make sure the number fits in the expected range */
    if ( value > 0xffffffff ) {
        return -1;
    }

    /* trim it down to the 32 bit value */
    *result = (uint32_t)value;
    return 0;
}


/*
 * Compare two lists and return an integer less than, equal to, or greater
 * than zero if list1 is found, respectively, to be less than, equal to, or
 * greater than list2.
 */
static int compare_lists(uint32_t *list1, uint32_t *list2,
        uint16_t size1, uint16_t size2) {
    int i;

    /* a shorter list will sort earlier than a longer one */
    if ( size1 < size2 ) {
        return -1;
    } else if ( size1 > size2 ) {
        return 1;
    }

    /* check every element to make sure they are the same */
    /* TODO any chance they can be the same but in a different order? */
    for ( i = 0; i < size1; i++ ) {
        if ( *(list1 + i) < *(list2 + i) ) {
            return -1;
        } else if ( *(list1 + i) > *(list2 + i) ) {
            return 1;
        }
    }

    return 0;
}


/*
 *  Return the AS set as a Python list object. If an error occurs null is
 *  returned and the error string message is set.
 */
static PyObject *get_as_set_list(RouteEntry *obj) {
    PyObject *as_set;
    int i;

    as_set = PyList_New(obj->as_set_size);

    for ( i = 0; i < obj->as_set_size; i++ ) {
        if ( PyList_SetItem(as_set, i,
                    PyLong_FromLong((long) *(obj->as_set+i))) == -1 ) {
            Py_XDECREF(as_set);
            return NULL;
        }
    }

    return as_set;
}


/*
 *  Return the communities as a python list object. The tuples are flattened
 *  one after each other. If an error is encountered null is returned and
 *  the error message is set.
 */
static PyObject *get_communities_list(RouteEntry *obj) {
    PyObject *communities;
    int i;

    communities = PyList_New(obj->communities_size);

    for ( i = 0; i < obj->communities_size; i++ ) {
        if ( PyList_SetItem(communities, i,
                    PyLong_FromLong((long) *(obj->communities+i))) == -1 ) {
            Py_XDECREF(communities);
            return NULL;
        }
    }

    return communities;
}


/*
 * Compare two RouteEntry objects and return an integer less than, equal to, or
 * greater than zero if obj1 is found, respectively, to be less than, equal to,
 * or greater than obj2.
 */
static int re_compare(RouteEntry *obj1, RouteEntry *obj2) {
    PyObject *nexthop1, *nexthop2;
    int difference;

    /* Lowest prefix should sort first */
    if ( PyObject_RichCompareBool(obj1->prefix, obj2->prefix, Py_LT) ) {
        return -1;
    } else if ( PyObject_RichCompareBool(obj1->prefix, obj2->prefix, Py_GT) ) {
        return 1;
    }

    /* Higher local preference should sort first */
    if ( obj1->preference > obj2->preference ) {
        return -1;
    } else if ( obj1->preference < obj2->preference ) {
        return 1;
    }

    /* Shortest AS path should sort first */
    if ( obj1->as_path_size < obj2->as_path_size ) {
        return -1;
    } else if ( obj1->as_path_size > obj2->as_path_size ) {
        return 1;
    }

    /* Lowest origin should sort first */
    if ( obj1->origin < obj2->origin ) {
        return -1;
    } else if ( obj1->origin > obj2->origin ) {
        return 1;
    }

    /* Lowest peer ASN should sort first */
    if ( obj1->peer < obj2->peer ) {
        return -1;
    } else if ( obj1->peer > obj2->peer ) {
        return 1;
    }

    /* Lowest nexthop (python string compare) should sort first */
    nexthop1 = PyUnicode_FromString(obj1->nexthop);
    nexthop2 = PyUnicode_FromString(obj2->nexthop);

    difference = PyUnicode_Compare(nexthop1, nexthop2);
    Py_XDECREF(nexthop1);
    Py_XDECREF(nexthop2);

    if ( difference != 0 ) {
        return difference;
    }

    /* Compare the AS Paths */
    difference = compare_lists(obj1->as_path, obj2->as_path, obj1->as_path_size,
            obj2->as_path_size);

    if ( difference != 0 ) {
        return difference;
    }

    /* Compare the AS Sets */
    difference = compare_lists(obj1->as_set, obj2->as_set, obj1->as_set_size,
            obj2->as_set_size);

    if ( difference != 0 ) {
        return difference;
    }

    /* Compare the Communities, the last chance for them to be different */
    return compare_lists(obj1->communities, obj2->communities,
            obj1->communities_size, obj2->communities_size);
}


// ========================== PYTHON METHODS  ==========================


/*
 * Deallocate a route entry object.
 */
static void re_dealloc(RouteEntry *self) {
    free_memory(self);
    Py_TYPE(self)->tp_free((PyObject *)self);
}


/*
 * Method called when the a new object is created.
 */
static PyObject *re_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
    RouteEntry *self;

    self = (RouteEntry *)type->tp_alloc(type, 0);
    if ( self != NULL ) {
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


/*
 * Initialise a new route entry object.
 */
static int re_init(RouteEntry *self, PyObject *args, PyObject *kwds) {
    static char *kwlist[] = {"origin", "peer", "prefix", "nexthop",
        "as_path", "as_set", "communities", "preference", NULL};

    PyObject *prefix = NULL;
    PyObject *as_path = NULL;
    PyObject *nexthop = NULL;
    PyObject *as_set = NULL;
    PyObject *communities = NULL;
    int i;

    if ( !PyArg_ParseTupleAndKeywords(args, kwds, "bIOO|OOOI", kwlist,
               &self->origin, &self->peer, &prefix, &nexthop,
                &as_path, &as_set, &communities, &self->preference) ) {
        return -1;
    }

    if ( PyUnicode_Check(nexthop) ) {
        /* If we got a string nexthop save it */
        self->nexthop = strdup(PyUnicode_AsUTF8(nexthop));
    } else {
        /* Otherwise set it to a default value */
        self->nexthop = strdup("");
    }

    /* Initialise the prefix */
    if ( init_prefix(self, prefix) == -1 ) {
        return -1;
    }

    /* Process and save the AS path */
    if ( as_path != NULL && as_path != Py_None ) {
        if ( re_set_as_path(self, as_path) == NULL ) {
            return -1;
        }
    }

    /* Process the AS set if provided */
    if ( as_set != NULL && as_set != Py_None ) {
        if ( !PyList_Check(as_set) && !PySet_Check(as_set) ) {
            PyErr_SetString(PyExc_AttributeError,
                "AS set has to be either a list or a set instance");
            return -1;
        }

        /*
         * Turn the list into a set or make a new set (preserve the initial
         * arguments as pop will destroy the list)
         */
        as_set = PySet_New(as_set);

        /* If we have items, allocate space in our AS set list */
        self->as_set_size = (uint16_t)PySet_Size(as_set);
        if ( self->as_set_size > 0 ) {
            self->as_set = malloc(self->as_set_size * sizeof(uint32_t));
        }

        for ( i = 0; i < self->as_set_size; i++ ) {
            PyObject *obj = PySet_Pop(as_set);
            if ( obj == NULL ) {
                Py_DECREF(as_set);
                return -1;
            }

            /* If the item is a string convert it to a python number */
            if ( PyUnicode_Check(obj) ) {
                PyObject *tmp = obj;
                obj = PyLong_FromUnicodeObject(obj, 10);
                Py_DECREF(tmp);

                if ( obj == NULL ) {
                    Py_DECREF(as_set);
                    return -1;
                }
            }

            /* extract the number, making sure that it is valid */
            if ( parse_32bit_value(obj, self->as_set + i) < 0 ) {
                Py_DECREF(obj);
                Py_DECREF(as_set);
                PyErr_SetString(PyExc_AttributeError,
                        "Failed to parse 32 bit ASN");
                return -1;
            }

            /* Free the set item */
            Py_DECREF(obj);
        }

        /* Free the created set */
        Py_DECREF(as_set);
    }

    /* Process and save the communities if provided */
    if ( communities != NULL && communities != Py_None ) {
        /* Use the community parser to covert to a list of tuple integers */
        PyObject *args = Py_BuildValue("(O)", communities);
        communities = PyObject_CallObject(comParser, args);
        Py_XDECREF(args);
        if ( communities == NULL ) {
            return -1;
        }

        /* If we have items allocate space in our list */
        self->communities_size = (uint16_t)PyList_Size(communities) * 2;
        if ( self->communities_size > 0 ) {
            self->communities =
                malloc(self->communities_size * sizeof(uint32_t));
        }

        /* Save to our list */
        for ( i = 0; i < self->communities_size; i++ ) {
            PyObject *obj = PyList_GetItem(communities, i / 2);
            PyObject *t1 = PyTuple_GetItem(obj, 0);
            PyObject *t2 = PyTuple_GetItem(obj, 1);

            /* Save the first element of the tuple */
            if ( parse_32bit_value(t1, self->communities + i) < 0 ) {
                Py_DECREF(communities);
                PyErr_SetString(PyExc_AttributeError,
                    "Overflown first community tuple number (max 32 bits)");
                return -1;
            }

            /* Save the second element to the tuple */
            i++;
            if ( parse_32bit_value(t2, self->communities + i) < 0 ) {
                Py_DECREF(communities);
                PyErr_SetString(PyExc_AttributeError,
                    "Overflown second community tuple number (max 32 bits)");
                return -1;
            }
        }

        Py_DECREF(communities);
    }

    return 0;
}


/*
 * Rich comparator method that compares two objects and returns a result
 */
static PyObject *re_richcmp(PyObject *obj1, PyObject *obj2, int operator) {
    int compare_result;
    int compare_raw;

    /* Validate the type of the objects we are comparing */
    if ( !PyObject_IsInstance(obj1, (PyObject*)&RouteEntryType) ) {
        PyErr_SetString(PyExc_AttributeError,
                "Can only compare route entry objects");
        return NULL;
    }

    if ( !PyObject_IsInstance(obj2, (PyObject*)&RouteEntryType) ) {
        PyErr_SetString(PyExc_AttributeError,
                "Can only compare route entry objects");
        return NULL;
    }

    /* Determine the ordering of the two objects */
    compare_raw = re_compare((RouteEntry *)obj1, (RouteEntry *)obj2);

    /* Check if the ordering matches what the comparison operator wanted */
    switch (operator) {
        case Py_LT: compare_result = compare_raw <  0; break;
        case Py_LE: compare_result = compare_raw <= 0; break;
        case Py_EQ: compare_result = compare_raw == 0; break;
        case Py_NE: compare_result = compare_raw != 0; break;
        case Py_GT: compare_result = compare_raw >  0; break;
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
 * Get a string representation of the route entry.
 */
static PyObject *re_str(RouteEntry *obj) {
    PyObject *as_path;
    PyObject *res;

    if ( (as_path = re_as_path(obj)) == NULL ) {
        return NULL;
    }

    res = PyUnicode_FromFormat("%S peer %u (nexthop: %s %S)",
            obj->prefix, obj->peer, obj->nexthop, as_path);
    Py_XDECREF(as_path);
    return res;
}


/*
 * Hash function
 */
static Py_hash_t re_hash(RouteEntry *obj){
    Py_hash_t res;
    PyObject *tup = Py_BuildValue("(OIsB)", obj->prefix, obj->peer,
            obj->nexthop, obj->origin);
    res = PyObject_Hash(tup);
    Py_XDECREF(tup);
    return res;
}


/*
 * Return the state of the object (for pickling)
 */
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


/*
 * Create a new list in target based on existing source python list. Will
 * modify the target and size arguments to describe the new list and return
 * 0 on success. Any failure will return -1, leaving target and size in an
 * undefined state.
 */
static int restore_list(PyObject *source, uint32_t **target, uint16_t *size) {
    /* check that the source is actually a python list */
    if ( !PyList_Check(source) ) {
        PyErr_SetString(PyExc_AttributeError,
            "Invalid dictionary item type. Expected list");
        return -1;
    }

    *size = (uint16_t)PyList_Size(source);

    if ( *size > 0 ) {
        int i;

        /* create the list and copy all the elements into it */
        *target = malloc(*size * sizeof(uint32_t));

        for ( i = 0; i < *size; i++ ) {
            PyObject *obj = PyList_GetItem(source, i);
            if ( !obj ) {
                return -1;
            }

            /* every element is a 32 bit integer (ASNs or communities) */
            if ( parse_32bit_value(obj, *target + i) < 0 ) {
                PyErr_SetString(PyExc_AttributeError,
                        "Invalid dictionary child value");
                return -1;
            }
        }
    } else {
        *target = NULL;
    }

    return 0;
}


/*
 * Restore the state of an object based on a state dictionary (for pickling)
 */
static PyObject *re_setstate(RouteEntry *self, PyObject *d) {
    PyObject *origin = PyDict_GetItemString(d, "origin");
    PyObject *peer = PyDict_GetItemString(d, "peer");
    PyObject *prefix = PyDict_GetItemString(d, "prefix");
    PyObject *nexthop = PyDict_GetItemString(d, "nexthop");
    PyObject *as_path = PyDict_GetItemString(d, "as_path");
    PyObject *as_set = PyDict_GetItemString(d, "as_set");
    PyObject *com = PyDict_GetItemString(d, "communities");
    PyObject *preference = PyDict_GetItemString(d, "preference");
    uint64_t value;
    char *strvalue;

    /* make sure the dictionary has all fields */
    if ( origin == NULL || peer == NULL || prefix == NULL ||
            nexthop == NULL || as_path == NULL || as_set == NULL ||
            com == NULL || preference == NULL ) {
        PyErr_SetString(PyExc_AttributeError,
            "Invalid set state dictionary. Not all fields received");
        return NULL;
    }

    /* Free up the old resources (if they exist) */
    free_memory(self);

    /* Validate and restore the origin */
    if ( !PyLong_Check(origin) ) {
        PyErr_SetString(PyExc_AttributeError,
            "Invalid dictionary item type (origin). Expected number");
        return NULL;
    }

    value = PyLong_AsLong(origin);
    if ( value < 0 || value > 2 ) {
        PyErr_SetString(PyExc_AttributeError,
            "Invalid dictionary value (origin)");
        return NULL;
    }
    self->origin = (uint8_t)value;

    /* Validate and restore the peer ASN */
    if ( parse_32bit_value(peer, &self->peer) < 0 ) {
        PyErr_SetString(PyExc_AttributeError,
            "Invalid dictionary value (peer)");
        return NULL;
    }

    /* Validate and restore the prefix */
    if ( init_prefix(self, prefix) == -1 ) {
        return NULL;
    }

    /* Validate and restore the next hop string */
    if ( !PyUnicode_Check(nexthop) ) {
        PyErr_SetString(PyExc_AttributeError,
            "Invalid dictionary item type (nexthop). Expected string");
        return NULL;
    }

    if ( (strvalue = PyUnicode_AsUTF8(nexthop)) == NULL ) {
        PyErr_SetString(PyExc_AttributeError,
            "Invalid dictionary value (nexthop)");
        return NULL;
    }
    self->nexthop = strdup(strvalue);

    /* Validate and restore the preference */
    if ( parse_32bit_value(preference, &self->preference) < 0 ) {
        PyErr_SetString(PyExc_AttributeError,
            "Invalid dictionary value (preference)");
        return NULL;
    }

    /* validate and restore the AS path list */
    if ( restore_list(as_path, &self->as_path, &self->as_path_size) < 0 ) {
        return NULL;
    }

    /* validate and restore the AS set list */
    if ( restore_list(as_set, &self->as_set, &self->as_set_size) < 0 ) {
        return NULL;
    }

    /* validate and restore the communities list */
    if ( restore_list(com, &self->communities, &self->communities_size) < 0 ) {
        return NULL;
    }

    Py_RETURN_NONE;
}


/*
 * Make a deep copy of a route entry object.
 */
static PyObject *re_deepcopy(RouteEntry *self, PyObject *memo) {
    PyObject *obj;
    RouteEntry *result;
    int i;

    /* Allocate and initialise a new object */
    obj = PyObject_Init(_PyObject_New(&RouteEntryType), &RouteEntryType);
    result = (RouteEntry *)obj;

    /*
     * XXX Note that the ID is implemented in c python as the memory address
     * of the object. Its defined by the builtin_id function (which we can't
     * call). We will get the memory location by executing the functions
     * method call to retrieve the ID.
     */
    PyDict_SetItem(memo, PyLong_FromVoidPtr(obj), (PyObject *)result);

    /* Copy the details of the object */
    result->origin = self->origin;
    result->peer = self->peer;
    result->nexthop = strdup(self->nexthop);
    result->preference = self->preference;

    /* XXX: SHOULD WE MAKE A NEW PREFIX? */
    result->prefix = self->prefix;
    Py_XINCREF(result->prefix);

    /* Copy all the items in the AS Path */
    result->as_path_size = self->as_path_size;
    if ( result->as_path_size != 0 ) {
        result->as_path = malloc(result->as_path_size * sizeof(uint32_t));
        for ( i = 0; i < result->as_path_size; i++ ) {
            *(result->as_path+i) = *(self->as_path+i);
        }
    } else {
        result->as_path = NULL;
    }

    /* Copy all the items in the AS Set */
    result->as_set_size = self->as_set_size;
    if ( result->as_set_size != 0 ) {
        result->as_set = malloc(result->as_set_size * sizeof(uint32_t));
        for ( i = 0; i < result->as_set_size; i++ ) {
            *(result->as_set+i) = *(self->as_set+i);
        }
    } else {
        result->as_set = NULL;
    }

    /* Copy all the items in the Communities list */
    result->communities_size = self->communities_size;
    if ( result->communities_size != 0 ) {
        result->communities =
            malloc(result->communities_size * sizeof(uint32_t));
        for ( i = 0; i < result->communities_size; i++ ) {
            *(result->communities+i) = *(self->communities+i);
        }
    } else {
        result->communities = NULL;
    }

    return (PyObject *)result;
}


// ========================== PYTHON ATTRIBUTES ==========================


/*
 * Return the route entries AS Path as a Python list object. If an error occurs
 * null is returned and the error string message is set.
 */
static PyObject *re_as_path(RouteEntry *obj) {
    PyObject *as_path;
    int i;

    as_path = PyList_New(obj->as_path_size);
    for ( i = 0; i < obj->as_path_size; i++ ) {
        if ( PyList_SetItem(as_path, i,
                    PyLong_FromLong((long) *(obj->as_path+i))) == -1 ) {
            Py_XDECREF(as_path);
            return NULL;
        }
    }

    return as_path;
}


/*
 *  Update the AS Path list with a list of AS Paths. Returns NULL on failure
 *  and None on success.
 */
static PyObject *re_set_as_path(RouteEntry *obj, PyObject *as_path) {
    uint16_t as_path_size;
    uint32_t *data;
    int i;

    if ( !PyList_Check(as_path) ) {
        PyErr_SetString(PyExc_AttributeError, "AS path has to be a list");
        return NULL;
    }

    as_path_size = (uint16_t)PyList_Size(as_path);

    if ( as_path_size > 0 ) {
        data = malloc(as_path_size * sizeof(uint32_t));
    } else {
        data = NULL;
    }

    for ( i = 0; i < as_path_size; i++ ) {
        PyObject *obj = PyList_GetItem(as_path, i);
        if ( !obj ) {
            free(data);
            return NULL;
        }

        /*
         * Object is borrowed reference but if we have a string we have
         * a new reference. Increment the count to allow for easy handling
         * (we will decrement automatically later)
         */
        Py_INCREF(obj);

        /* If the item is a string convert it to a python number */
        if ( PyUnicode_Check(obj) ) {
            PyObject *tmp = obj;
            obj = PyLong_FromUnicodeObject(obj, 10);
            Py_DECREF(tmp);

            /* Conversion from string to python int (long) failed */
            if ( !obj ) {
                free(data);
                return NULL;
            }
        }

        /* Process a python number */
        if ( parse_32bit_value(obj, data + i) < 0 ) {
            free(data);
            Py_DECREF(obj);
            PyErr_SetString(PyExc_AttributeError, "Invalid ASN");
            return NULL;
        }

        Py_DECREF(obj);
    }

    /* If we already have an allocated list then free it */
    if ( obj->as_path_size != 0 ) {
        free(obj->as_path);
    }

    if ( as_path_size == 0 ) {
        obj->as_path = NULL;
        obj->as_path_size = 0;
    } else {
        obj->as_path = data;
        obj->as_path_size = as_path_size;
    }

    Py_RETURN_NONE;
}


/*
 *  Return the AS Set of the route entry as a python set.
 */
static PyObject *re_as_set(RouteEntry *obj) {
    PyObject *as_set;
    PyObject *res;

    if ( (as_set = get_as_set_list(obj)) == NULL ) {
        return NULL;
    }

    /* Return None if there is an empty AS Set */
    if ( PyList_Size(as_set) == 0 ) {
        Py_DECREF(as_set);
        Py_RETURN_NONE;
    }

    /* Convert the list to a set and return the result */
    res = PySet_New(as_set);
    Py_DECREF(as_set);
    return res;
}


/*
 * Add elements to the AS Set of the route entry.
 */
static PyObject *re_add_as_set(RouteEntry *self, PyObject *as_set) {
    PyObject *set;
    int i;

    /* Make sure the attribute is a list or a set element */
    if ( !PyList_Check(as_set) && !PySet_Check(as_set) ) {
        PyErr_SetString(PyExc_AttributeError,
            "AS set has to be either a set attribute or a list");
        return NULL;
    }

    /* Copy an existing set or turn a list into an AS set */
    if ( (set = PySet_New(as_set)) == NULL ) {
        return NULL;
    }

    /* create an array to store items we need to add (that aren't already) */
    uint32_t dataList[PySet_Size(set)];
    int dataIndex = 0;

    /* Iterate through the AS set */
    int set_size = PySet_Size(set);
    for ( i = 0; i < set_size; i++ ) {
        PyObject *obj;
        uint32_t value;
        int found;
        int j;

        /* Pop an item from the set */
        obj = PySet_Pop(set);
        if ( obj == NULL ) {
            Py_DECREF(set);
            return NULL;
        }

        /* Parse and validate the ASN */
        if ( parse_32bit_value(obj, &value) < 0 ) {
            Py_DECREF(set);
            Py_DECREF(obj);
            PyErr_SetString(PyExc_AttributeError, "Trying to add invalid ASN");
            return NULL;
        }

        /* Free the popped set value */
        Py_DECREF(obj);

        /* Check if we already have the item in our AS set */
        found = 0;
        for ( j = 0; j < self->as_set_size; j++ ) {
            if ( value == *(self->as_set + j) ) {
                found = 1;
                break;
            }
        }

        /* If the item is already in our as set just skip it */
        if ( found ) {
            continue;
        }

        /* Check if we already have the item in our AS path */
        for ( j = 0; j < self->as_path_size; j++ ) {
            if ( value == *(self->as_path + j) ) {
                found = 1;
                break;
            }
        }

        /* If item isn't in the AS path or AS set then add it to the array */
        if ( !found ) {
            dataList[dataIndex] = value;
            dataIndex++;
        }
    }

    /* Free the set */
    Py_DECREF(set);

    /* Resize our list if we have more elements to add */
    if ( dataIndex > 0 ) {
        uint16_t new_size = self->as_set_size + dataIndex;
        void *ptr = realloc(self->as_set, new_size * sizeof(uint32_t));
        if ( ptr == NULL ) {
            PyErr_SetString(PyExc_MemoryError,
                "Can't resize as-set list. Operation failed");
            return NULL;
        }
        self->as_set = ptr;

        /* Add the new ASNs to the list */
        for ( i = 0; i < dataIndex; i++ ) {
            *(self->as_set + self->as_set_size + i) = dataList[i];
        }
        self->as_set_size = new_size;
    }

    Py_RETURN_NONE;
}


/*
 *  Reconstruct and return a set of communities as two element tuples.
 *  As per the module convention if the communities set is empty we
 *  will return None.
 */
static PyObject *re_communities(RouteEntry *obj) {
    PyObject *communities;
    PyObject *result;
    int num_tuples;
    int i;

    num_tuples = obj->communities_size / 2;

    /* empty set, return None */
    if ( num_tuples == 0 ) {
        Py_RETURN_NONE;
    }

    communities = PyList_New(num_tuples);
    for ( i = 0; i < obj->communities_size; i++ ) {
        PyObject *tuple = PyTuple_New(2);
        /* set the first element of the tuple to the first of the pairs */
        if ( PyTuple_SetItem(tuple, 0,
                    PyLong_FromLong((long) *(obj->communities+i))) != 0 ) {
            Py_XDECREF(tuple);
            Py_XDECREF(communities);
            return NULL;
        }

        /* set the second element of the tuple to the next item in the list */
        i++;
        if ( PyTuple_SetItem(tuple, 1,
                    PyLong_FromLong((long) *(obj->communities+i))) != 0 ) {
            Py_XDECREF(tuple);
            Py_XDECREF(communities);
            return NULL;
        }

        /* Add the tuple to the list */
        if ( PyList_SetItem(communities, ((i - 1) / 2), tuple) != 0 ) {
            Py_XDECREF(tuple);
            Py_XDECREF(communities);
            return NULL;
        }
    }

    result = PySet_New(communities);
    Py_XDECREF(communities);
    return result;
}


/*
 * Add communities to the communities list of the route entry
 */
static PyObject *re_add_communities(RouteEntry *self, PyObject *com) {
    int i;

    /* Validate the attribute */
    if ( com == Py_None || PyList_Size(com) == 0 ) {
        Py_RETURN_NONE;
    }

    if ( !PyList_Check(com) ) {
        PyErr_SetString(PyExc_AttributeError,
            "Invalid community attribute. Expected list");
        return NULL;
    }

    /* create an array to store items we need to add (that aren't already) */
    uint32_t dataList[PyList_Size(com) * 2];
    int dataIndex = 0;

    /* Iterate through the community tuples */
    for ( i = 0; i < PyList_Size(com); i++ ) {
        PyObject *t1;
        PyObject *t2;
        PyObject *obj;
        uint32_t value1, value2;
        int found;
        int j;

        obj = PyList_GetItem(com, i);
        if ( obj == NULL ) {
            return NULL;
        }

        if ( !PyTuple_Check(obj) || PyTuple_Size(obj) != 2 ) {
            PyErr_SetString(PyExc_AttributeError,
                "Attribute has to be a list of 2 element tuples");
            return NULL;
        }

        t1 = PyTuple_GetItem(obj, 0);
        t2 = PyTuple_GetItem(obj, 1);

        /* Parse and validate the first element of the tuple */
        if ( parse_32bit_value(t1, &value1) < 0 ) {
            PyErr_SetString(PyExc_AttributeError,
                "Overflown first community tuple number (max 32 bits)");
            return NULL;
        }

        /* Parse and validate the second element of the tuple */
        if ( parse_32bit_value(t2, &value2) < 0 ) {
            PyErr_SetString(PyExc_AttributeError,
                "Overflown second community tuple number (max 32 bits)");
            return NULL;
        }

        /* check if the community already exists in the list */
        found = 0;
        for ( j = 0; j < self->communities_size; j += 2 ) {
            if ( value1 == *(self->communities + j) &&
                    value2 == *(self->communities + j + 1) ) {
                found = 1;
                break;
            }
        }

        /* If the tuple isn't already in the community list then store it */
        if ( found == 0 ) {
            dataList[dataIndex] = value1;
            dataList[dataIndex+1] = value2;
            dataIndex += 2;
        }
    }

    /* Resize our community list if we have more elements to add */
    if ( dataIndex > 0 ) {
        uint16_t new_size = self->communities_size + dataIndex;
        void *ptr = realloc(self->communities, new_size * sizeof(uint32_t));
        if ( ptr == NULL ) {
            PyErr_SetString(PyExc_MemoryError,
                "Can't resize community list. Operation failed");
            return NULL;
        }
        self->communities = ptr;

        /* Add the new communities to the list */
        for ( i = 0; i < dataIndex; i++ ) {
            *(self->communities + self->communities_size + i) = dataList[i];
        }
        self->communities_size = new_size;
    }

    Py_RETURN_NONE;
}


/*
 * Remove communities from the route entry.
 */
static PyObject *re_remove_communities(RouteEntry *self, PyObject *com) {
    PyObject *set;
    int length;
    int end;
    int i;
    int j;

    /* Don't do any work if we don't have any communities */
    if ( self->communities_size == 0 ) {
        Py_RETURN_NONE;
    }

    /* Convert the list of communities to remove into a set */
    set = PySet_New(com);
    if ( set == NULL ) {
        return NULL;
    }

    /* iterate through the set of communities and remove them from our list */
    length = PySet_Size(set);
    end = self->communities_size - 1;
    for ( i = 0; i < length; i++ ) {
        PyObject *t1;
        PyObject *t2;
        PyObject *obj;
        uint32_t v1, v2;

        obj = PySet_Pop(set);
        if ( obj == NULL ) {
            Py_DECREF(set);
            return NULL;
        }

        if ( !PyTuple_Check(obj) || PyTuple_Size(obj) != 2 ) {
            Py_DECREF(set);
            Py_DECREF(obj);
            PyErr_SetString(PyExc_AttributeError,
                "Attribute has to be a list of 2 element tuples");
            return NULL;
        }

        /* Get the tuple items (borrowed reference) */
        t1 = PyTuple_GetItem(obj, 0);
        t2 = PyTuple_GetItem(obj, 1);

        /* Save the first element of the tuple */
        if ( parse_32bit_value(t1, &v1) < 0 ) {
            Py_DECREF(set);
            Py_DECREF(obj);
            PyErr_SetString(PyExc_AttributeError,
                    "Overflown first community tuple number (max 32 bits)");
            return NULL;
        }

        /* Save the second element to the tuple */
        if ( parse_32bit_value(t2, &v2) < 0 ) {
            Py_DECREF(set);
            Py_DECREF(obj);
            PyErr_SetString(PyExc_AttributeError,
                    "Overflown second community tuple number (max 32 bits)");
            return NULL;
        }

        /* Free the popped set value (new reference) */
        Py_DECREF(obj);

        /* Iterate through the item to see if we can find it */
        for ( j = 0; j < self->communities_size; j += 2 ) {
            if ( v1 == *(self->communities + j) &&
                    v2 == *(self->communities + j + 1) ) {
                if ( j < end - 1 ) {
                    /* copy the final item over top of the item to be removed */
                    *(self->communities + j) = *(self->communities + end - 1);
                    *(self->communities + j + 1) = *(self->communities + end);
                }
                /* cut off the last element, we don't need it anymore */
                end -= 2;
                break;
            }
        }
    }

    /* Free the copied set */
    Py_DECREF(set);

    /* Resize the communities list if we removed elements */
    if ( end != (self->communities_size - 1) ) {
        int newSize = end + 1;
        if ( newSize > 0 ) {
            /* Reallocate the memory section (make smaller) */
            void *ptr = realloc(self->communities, newSize * sizeof(uint32_t));
            if ( ptr == NULL ) {
                PyErr_SetString(PyExc_MemoryError,
                    "Can't resize community list. Operation failed");
                return NULL;
            }

            /* Update the new pointer and new size */
            self->communities = ptr;
            self->communities_size = newSize;
        } else {
            /* If the list is empty free the memory and set the size to 0 */
            free(self->communities);
            self->communities = NULL;
            self->communities_size = 0;
        }
    }

    Py_RETURN_NONE;
}


/*
 * Update the nexthop attribute of a route entry.
 */
static PyObject *re_set_nexthop(RouteEntry *obj, PyObject *nexthop) {
    if ( PyUnicode_Check(nexthop) ) {
        /* If we got a string nexthop update the old attribute */
        free(obj->nexthop);
        obj->nexthop = strdup(PyUnicode_AsUTF8(nexthop));
    } else {
        /* Otherwise set a default value */
        free(obj->nexthop);
        obj->nexthop = strdup("");
    }

    Py_RETURN_NONE;
}


// ========================== PYTHON MODULE METHODS ==========================


/*
 * Generate and return the AS Path announcement string in the ExaBGP format.
 */
static PyObject *re_announce_as_path_str(RouteEntry *obj) {
    PyObject *as_path = PyUnicode_FromString("");
    PyObject *result;
    int i;

    for ( i = 0; i < obj->as_path_size; i++ ) {
        PyObject *new_as_path;
        if ( i == 0 ) {
            new_as_path = PyUnicode_FromFormat("%U%u", as_path,
                    *(obj->as_path+i));
        } else {
            new_as_path = PyUnicode_FromFormat("%U %u", as_path,
                    *(obj->as_path+i));
        }

        Py_XDECREF(as_path);
        as_path = new_as_path;
    }

    /* Generate the AS Set string for ExaBGP */
    PyObject *as_set = PyUnicode_FromString("");
    for ( i = 0; i < obj->as_set_size; i++ ) {
        PyObject *new_as_set =
            PyUnicode_FromFormat("%U %u", as_set, *(obj->as_set+i));
        Py_XDECREF(as_set);
        as_set = new_as_set;
    }

    if ( obj->as_set_size > 0 ) {
        PyObject *new_as_set = PyUnicode_FromFormat("(%U )", as_set);
        Py_XDECREF(as_set);
        as_set = new_as_set;
        result = PyUnicode_FromFormat("as-path [%U %U]", as_path, as_set);
    } else {
        result = PyUnicode_FromFormat("as-path [%U]", as_path);
    }

    Py_XDECREF(as_path);
    Py_XDECREF(as_set);
    return result;
}


/*
 * Generate and return the community announcement string in ExaBGP format
 */
static PyObject *re_announce_communities_str(RouteEntry *obj) {
    PyObject *communities;
    PyObject *result;
    int i;

    if ( obj->communities_size == 0 ) {
        return PyUnicode_FromFormat("");
    }

    communities = PyUnicode_FromString("");
    for ( i = 0; i < obj->communities_size; i += 2 ) {
        PyObject *new_com;
        if ( (i+2) == obj->communities_size ) {
            new_com = PyUnicode_FromFormat("%U%u:%u", communities,
                *(obj->communities+i), *(obj->communities+i+1));
        } else {
            new_com = PyUnicode_FromFormat("%U%u:%u ", communities,
                *(obj->communities+i), *(obj->communities+i+1));
        }

        Py_XDECREF(communities);
        communities = new_com;
    }

    result = PyUnicode_FromFormat("community [%U]", communities);
    Py_XDECREF(communities);
    return result;
}

/*
 * This could have been done using the buffer protocol, but we still would
 * have needed a special function to restore the object, so we'll do them
 * both the same way.
 */
static PyObject *save_to_buffer(RouteEntry *self, PyObject *arg) {
    PyObject *return_value = NULL;
    Py_buffer buffer = {NULL, NULL};

    if ( !PyArg_Parse(arg, "w*:save_to_buffer", &buffer) ) {
        goto exit;
    }
    return_value = save_to_buffer_impl(self, &buffer);

exit:
    if ( buffer.obj ) {
        PyBuffer_Release(&buffer);
    }

    return return_value;
}


/*
 * Copy datalen bytes of data from *data into the given buffer and increment
 * the offset counter by the same amount. This function does no checking,
 * assumes that the buffer sizes have all been checked beforehand.
 */
static void buffer_pack(Py_buffer *buffer, void *data, uint32_t datalen,
        uint32_t *offset) {
    memcpy(buffer->buf + *offset, data, datalen);
    *offset += datalen;
}


/*
 * Copy datalen bytes of data from the given buffer into *data and increment
 * the offset counter by the same amount. This function does no checking,
 * assumes that the buffer sizes have all been checked beforehand.
 */
static void buffer_unpack(Py_buffer *buffer, void *data, uint32_t datalen,
        uint32_t *offset) {
    memcpy(data, buffer->buf + *offset, datalen);
    *offset += datalen;
}


/*
 * Determine how many bytes are required to store the given route entry.
 */
static uint32_t calculate_size(uint8_t family, RouteEntry *self) {
    uint32_t required;

    /* base size required to store this route entry, minus the prefix */
    required = sizeof(family) + sizeof(self->peer) + sizeof(self->preference) +
        sizeof(self->origin) + strlen(self->nexthop) + 1 +
        sizeof(self->as_path_size) + (self->as_path_size * sizeof(uint32_t)) +
        sizeof(self->as_set_size) + (self->as_set_size * sizeof(uint32_t)) +
        sizeof(self->communities_size) +
        (self->communities_size * sizeof(uint64_t));

    switch ( family ) {
        case AF_INET: required += 5; break;
        case AF_INET6: required += 17; break;
        default: assert(0);
    };

    return required;
}


static PyObject *save_to_buffer_impl(RouteEntry *self, Py_buffer *buffer) {
    uint32_t required;
    uint32_t i = 0;
    uint8_t family;

    /* determine address family for the contained prefix */
    if ( PyObject_IsInstance(self->prefix, IPv4Type) ) {
        family = AF_INET;
    } else if ( PyObject_IsInstance(self->prefix, IPv6Type) ) {
        family = AF_INET6;
    } else {
        assert(0);
    }

    /* make sure the buffer is long enough before we try to store anything */
    required = calculate_size(family, self);
    if ( buffer->len < required ) {
        return PyLong_FromLong(-1);
    }

    /* store the address family so we know how to treat the prefix */
    buffer_pack(buffer, &family, sizeof(family), &i);

    if ( PyObject_IsInstance(self->prefix, IPv4Type) ) {
        /* IPv4, store 32bit IP address and 8bit prefix length */
        buffer_pack(buffer, &((IPv4*)self->prefix)->ip,
                sizeof(((IPv4*)self->prefix)->ip), &i);
        buffer_pack(buffer, &((IPv4*)self->prefix)->prefixlen,
                sizeof(((IPv4*)self->prefix)->prefixlen), &i);
    } else if ( PyObject_IsInstance(self->prefix, IPv6Type) ) {
        /* IPv6, store IP address as 2x 64bit and an 8bit prefix length */
        buffer_pack(buffer, &((IPv6*)self->prefix)->upper,
                sizeof(((IPv6*)self->prefix)->upper), &i);
        buffer_pack(buffer, &((IPv6*)self->prefix)->lower,
                sizeof(((IPv6*)self->prefix)->lower), &i);
        buffer_pack(buffer, &((IPv6*)self->prefix)->prefixlen,
                sizeof(((IPv6*)self->prefix)->prefixlen), &i);
    }

    /* store values we know must exist */
    buffer_pack(buffer, &self->peer, sizeof(self->peer), &i);
    buffer_pack(buffer, &self->preference, sizeof(self->preference), &i);
    buffer_pack(buffer, &self->origin, sizeof(self->origin), &i);

    /* write the whole nexthop string, with null terminator */
    buffer_pack(buffer, self->nexthop, strlen(self->nexthop) + 1, &i);

    /* store variable length AS path list */
    buffer_pack(buffer, &self->as_path_size, sizeof(self->as_path_size), &i);
    if ( self->as_path_size > 0 ) {
        buffer_pack(buffer, self->as_path,
                self->as_path_size * sizeof(uint32_t), &i);
    }

    /* store variable length AS set */
    buffer_pack(buffer, &self->as_set_size, sizeof(self->as_set_size), &i);
    if ( self->as_set_size > 0 ) {
        buffer_pack(buffer, self->as_set,
                self->as_set_size * sizeof(uint32_t), &i);
    }

    /* store variable length communities list */
    buffer_pack(buffer, &self->communities_size,
            sizeof(self->communities_size), &i);
    if ( self->communities_size > 0 ) {
        buffer_pack(buffer, self->communities,
                self->communities_size * sizeof(uint64_t), &i);
    }

    assert(required == i);

    return PyLong_FromUnsignedLong(i);
}



static PyObject *load_from_buffer(RouteEntry *self, PyObject *arg) {
    PyObject *return_value = NULL;
    Py_buffer buffer = {NULL, NULL};

    if ( !PyArg_Parse(arg, "w*:load_from_buffer", &buffer) ) {
        goto exit;
    }
    return_value = load_from_buffer_impl(self, &buffer);

exit:
    if ( buffer.obj ) {
        PyBuffer_Release(&buffer);
    }

    return return_value;
}

/*
 * TODO this requires an existing RouteEntry object to read into
 *
 *
 * XXX could do create_from_buffer() that doesn't need existing route entry
 */
static PyObject *load_from_buffer_impl(RouteEntry *self, Py_buffer *buffer) {
    uint32_t i = 0;
    uint8_t family;

    /* we're reusing an existing route entry, so remove anything it has set */
    free_memory(self);

    /* address family is first so we know what sort of prefix we are getting */
    buffer_unpack(buffer, &family, sizeof(family), &i);

    //XXX will need to check buffer length as we go? cause otherwise don't know
    // what things are and how big they are?

    /*
     * need to create a new prefix object to replace the one that we removed
     * https://eli.thegreenplace.net/2012/04/16/python-object-creation-sequence
     */
    if ( family == AF_INET ) {
        /* IPv4, load 32bit IP address and 8bit prefix length */
        IPv4 *prefix;
        self->prefix = ((PyTypeObject*)IPv4Type)->tp_alloc(
                (PyTypeObject*)IPv4Type, 0);
        prefix = ((IPv4*)self->prefix);

        buffer_unpack(buffer, &prefix->ip, sizeof(prefix->ip), &i);
        buffer_unpack(buffer, &prefix->prefixlen,
                sizeof(prefix->prefixlen), &i);
    } else if ( family == AF_INET6 ) {
        /* IPv6, load IP address as 2x 64bit and an 8bit prefix length */
        IPv6 *prefix;
        self->prefix = ((PyTypeObject*)IPv6Type)->tp_alloc(
                (PyTypeObject*)IPv6Type, 0);
        prefix = ((IPv6*)self->prefix);

        buffer_unpack(buffer, &prefix->upper, sizeof(prefix->upper), &i);
        buffer_unpack(buffer, &prefix->lower, sizeof(prefix->lower), &i);
        buffer_unpack(buffer, &prefix->prefixlen,
                sizeof(prefix->prefixlen), &i);
    } else {
        assert(0);
    }

    /* load values we know must exist */
    buffer_unpack(buffer, &self->peer, sizeof(self->peer), &i);
    buffer_unpack(buffer, &self->preference, sizeof(self->preference), &i);
    buffer_unpack(buffer, &self->origin, sizeof(self->origin), &i);

    /* TODO not storing a length makes reading nexthop slightly annoying */
    self->nexthop = malloc(strlen(buffer->buf + i) + 1);
    buffer_unpack(buffer, self->nexthop, strlen(buffer->buf + i) + 1, &i);

    /* load variable length AS path list */
    buffer_unpack(buffer, &self->as_path_size, sizeof(self->as_path_size), &i);
    if ( self->as_path_size > 0 ) {
        self->as_path = malloc(self->as_path_size * sizeof(uint32_t));
        buffer_unpack(buffer, self->as_path,
                self->as_path_size * sizeof(uint32_t), &i);
    }

    /* load variable length AS set */
    buffer_unpack(buffer, &self->as_set_size, sizeof(self->as_set_size), &i);
    if ( self->as_set_size > 0 ) {
        self->as_set = malloc(self->as_set_size * sizeof(uint32_t));
        buffer_unpack(buffer, self->as_set,
                self->as_set_size * sizeof(uint32_t), &i);
    }

    /* load variable length communities list */
    buffer_unpack(buffer, &self->communities_size,
            sizeof(self->communities_size), &i);
    if ( self->communities_size > 0 ) {
        self->communities = malloc(self->communities_size * sizeof(uint64_t));
        buffer_unpack(buffer, self->communities,
                self->communities_size * sizeof(uint64_t), &i);
    }

    return PyLong_FromUnsignedLong(i);
}


static PyObject *create_from_buffer(PyObject *cls, PyObject *arg) {
    RouteEntry *self = NULL;
    PyObject *length = NULL;
    Py_buffer buffer = {NULL, NULL};

    if ( !PyArg_Parse(arg, "w*:create_from_buffer", &buffer) ) {
        goto exit;
    }

    /* create a new route entry object */
    if ( (self = (RouteEntry*)re_new((PyTypeObject*)cls, 0, 0)) == NULL ) {
        goto exit;
    }

    /* populate it */
    length = load_from_buffer_impl(self, &buffer);

exit:
    if ( buffer.obj ) {
        PyBuffer_Release(&buffer);
    }

    return Py_BuildValue("(OO)", self, length);
}


// ========================== INITIALISE THE MODULE ==========================


/*
 * Register the types and the module
 */
PyMODINIT_FUNC PyInit_RouteEntry(void) {
    PyObject *module;
    PyObject *prefixDict;
    PyObject *prefIMP;
    PyObject *comParseIMP;
    PyObject *comDict;

    if ( PyType_Ready(&RouteEntryType) < 0 ) {
        return NULL;
    }

    module = PyModule_Create(&remodule);
    if ( module == NULL ) {
        return NULL;
    }

    Py_INCREF(&RouteEntryType);
    PyModule_AddObject(module, "RouteEntry", (PyObject *)&RouteEntryType);

    /* add the static attributes */
    PyModule_AddObject(module, "DEFAULT_LOCAL_PREF",
            PyLong_FromLong(DEFAULT_LOCAL_PREF));
    PyModule_AddObject(module, "ORIGIN_IGP", PyLong_FromLong(ORIGIN_IGP));
    PyModule_AddObject(module, "ORIGIN_EGP", PyLong_FromLong(ORIGIN_EGP));
    PyModule_AddObject(module, "ORIGIN_INCOMPLETE",
            PyLong_FromLong(ORIGIN_INCOMPLETE));

    /*
     * Load the prefix and community modules just once so we can reuse them
     * without having to load them every time.
     */
    prefIMP = PyImport_ImportModule("Prefix");
    prefixDict = PyModule_GetDict(prefIMP);
    IPv4Type = PyDict_GetItemString(prefixDict, "IPv4");
    IPv6Type = PyDict_GetItemString(prefixDict, "IPv6");
    PrefixFactory = PyDict_GetItemString(prefixDict, "Prefix");
    Py_XDECREF(prefIMP);

    comParseIMP = PyImport_ImportModule("bgpsdn.CommunityParser");
    comDict = PyModule_GetDict(comParseIMP);
    comParser = PyDict_GetItemString(comDict, "communities_to_tuple_array");
    Py_XDECREF(comParseIMP);

    return module;
}
