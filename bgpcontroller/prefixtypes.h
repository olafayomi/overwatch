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

#ifndef PREFIXTYPES_H
#define PREFIXTYPES_H

#include <Python.h>
#include <stdint.h>
#include "structmember.h"

typedef struct {
    PyObject_HEAD
    uint32_t ip;
    uint8_t prefixlen;
} IPv4;

typedef struct {
    PyObject_HEAD
    uint64_t upper;
    uint64_t lower;
    uint8_t prefixlen;
} IPv6;

#endif
