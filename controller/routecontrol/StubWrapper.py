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

import grpc
from functools import partial
import sys


class StubWrapper:

    def __init__(self, service_module, stub_name, host, port, timeout=10):
        channel = grpc.insecure_channel('{0}:{1}'.format(host, port))
        try:
            grpc.channel_ready_future(channel).result(timeout=10)
        except grpc.FutureTimeoutError:
            sys.exit('Error connecting to server')
        self.stub = getattr(service_module, stub_name)(channel)
        self.timeout = timeout

    def __getattr__(self, attr):
        return partial(self._wrapped_call, self.stub, attr)

    def __wrapped_call(self, *args, **kwargs):
        try:
            return getattr(args[0], args[1])(
                args[2], **kwargs, timeout=self.timeout)
        except grpc.RpcError as e:
            print('Call {0} failed with {1}'.format(args[1], e.code()))
            raise
