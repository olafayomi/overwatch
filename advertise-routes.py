#!/usr/bin/env python


# Copyright (c) 2020, WAND Network Research Group
#                     Department of Computer Science
#                     University of Waikato
#                     Hamilton
#                     New Zealand
#
# Author Dimeji Fayomi (oof1@students.waikato.ac.nz)
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

import sys
import time

messages = [
        'announce route 160.10.0.0/24 next-hop self',
        'announce route 250.20.0.0/24 next-hop self',
        'announce route 250.30.0.0/24 next-hop self',
        'announce route 170.0.0.0/24 next-hop self',
]

time.sleep(30)

for message in messages:
    sys.stdout.write(message + '\n')
    sys.stdout.flush()
    time.sleep(1)

while True:
    time.sleep(1)
