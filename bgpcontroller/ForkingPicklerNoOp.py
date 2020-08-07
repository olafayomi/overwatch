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



# https://bugs.python.org/issue28053
# https://stackoverflow.com/questions/45119053/how-to-change-the-serialization-method-used-by-pythons-multiprocessing

from multiprocessing36.reduction import ForkingPickler, AbstractReducer

# "Pickler" for use with multiprocessing.queue that won't modify the data at
# all, allowing me to use my own (faster) serialisation.
class ForkingPicklerNoOp(ForkingPickler):
    def __init__(self, *args):
        super(ForkingPicklerNoOp, self).__init__(*args)

    @classmethod
    def dumps(cls, obj, protocol=None):
        return obj

    @classmethod
    def loads(cls, obj, protocol=None):
        return obj

def dump(obj, afile, protocol=None):
    ForkingPicklerNoOp(afile, protocol, dump(obj))

class PickleNoOpReducer(AbstractReducer):
    ForkingPickler = ForkingPicklerNoOp
    register = ForkingPicklerNoOp.register
    dump = dump
