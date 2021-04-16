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

import json
import time
from copy import deepcopy
from abc import abstractmethod, ABCMeta
from multiprocessing import Process, Queue
from queue import Empty
from ctypes import cdll, byref, create_string_buffer
from collections import defaultdict
from Prefix import Prefix
from RouteEntry import RouteEntry, DEFAULT_LOCAL_PREF
import random
import logging
from PolicyObject import PolicyObject, ACCEPT
import perfmon_pb2 as perfmsg
import struct
import select
import os
from google.protobuf.json_format import MessageToDict

def decode_msg_size(size_bytes: bytes) -> int:
    return struct.unpack("<I", size_bytes)[0]


class BasePARModule(Process):
    __metaclass__ = ABCMeta

    def __init__(self, name, command_queue, prefixes, peer_addrs):
        Process.__init__(self, name=name)

        self.command_queue = command_queue
        self.prefixes = []
        for prefix in prefixes:
            self.prefixes.append(Prefix(prefix))
        self.routes = {prefix: set() for prefix in self.prefixes}
        self.daemon = True
        self.enabled_peers = peer_addrs
        self.mailbox = Queue()
        self.last_performed = 0
        self.best_routes = {}
        self.counter = 0
        self.actions = {
            "add": self._process_add_route,
            "remove": self._process_remove_route,
            "get": self._process_send_best_route,
        }
        self.unixsock = '/home/ubuntu/perf.sock'
        os.mkfifo(self.unixsock)

    def __str__(self):
        return "Performance-Aware Module(type: %s)" % (self.name)

    def run(self):
        libc = cdll.LoadLibrary("libc.so.6")
        buff = create_string_buffer(len(self.name)+5)
        buff.value = ("foo " + self.name).encode()
        libc.prctl(15, byref(buff), 0, 0, 0)

        callbacks = []

        try:
            perfpipe = os.open(self.unixsock, os.O_RDONLY | os.O_NONBLOCK)
            try:
                poll = select.poll()
                poll.register(perfpipe, select.POLLIN)
                try:
                    while True:
                        #curr_time = time.time()
                        #if self.last_performed != 0:
                        #    time_diff = curr_time - self.last_performed
                        #    if time_diff > 120:
                        #        best_routes = self._send_latest_best_route()
                        #        self.command_queue.put(("par-update", {
                        #            "routes": best_routes,
                        #            "type": self.name,
                        #        }))
                        if (perfpipe, select.POLLIN) in poll.poll(500): 
                            msg_size_bytes = os.read(perfpipe, 4)
                            msg_size = decode_msg_size(msg_size_bytes) 
                            msg_content = os.read(perfpipe, msg_size)
                            perfnode = perfmsg.ExitNode() 
                            exitnode = perfnode.FromString(msg_content)
                            node = exitnode.name
                            nexthop = exitnode.address
                            self.best_routes = self._fetch_route(node, nexthop)
                            if len(self.best_routes) != 0: 
                                self.command_queue.put(("par-update", {
                                    "routes": self.best_routes,
                                    "type": self.name,
                                }))
                                self.log.info("PARMetricsModule RUN RECEIVED PERFOMANCE UPDATE AND NOTIFIED CONTROLLER TO UPDATE DATAPLANE WITH: %s" %self.best_routes)
                        else:
                            pass

                        try:
                            msgtype, message = self.mailbox.get(block=True, timeout=1)
                        except Empty:
                            for callback, timeout in callbacks:
                                self.log.debug("No recent messages, callback %s triggereed" %
                                        callback)
                                callback()
                            callbacks.clear()
                            continue

                        # if it's been too long since we added a callback, deal with it
                        # now before continuing to process messages
                        while len(callbacks) > 0 and callbacks[0][1] < time.time():
                            self.log.debug("Triggering overdue callback %s" % callback)
                            callback, timeout = callbacks.pop(0)
                            callback()

                        if msgtype in self.actions:
                            # actions may trigger a callback (e.g. advertising routes) but
                            # we don't want to repeatedly perform these actions, so delay
                            # briefly in case we get more messages
                            callback = self.actions[msgtype](message)
                            if callback and not any(callback == x for x, y in callbacks):
                                callbacks.append((callback, time.time() + 10))
                        else:
                            self.log.warning("Ignoring unknown message type %s" % msgtype)
                        del message
                finally:
                    poll.unregister(perfpipe) 
            finally:
                os.close(perfpipe)
        finally:
            os.remove(self.unixsock)

    def _process_add_route(self, message):
        for route in message["routes"]:
            self.log.info("BANDWIDTH_DIMEJI_BBBBBBB _process_add_route: %s" %route)
            self.log.info("BANDWIDTH_DIMEJI_FBDSDBFDSD _process_add_route: prefix type is %s" % type(route))
            pfx = route.prefix
            self.log.info("BANDWIDTH_DIMEJI_CHECKING PFX is %s" %pfx)
            self.log.info("BANDWIDTH_DIMEJI_CHECKING PFX TYPE is %s" %type(pfx))
            #prefx = pfx.prefix()
            if pfx not in self.prefixes:
                continue
            self.routes[pfx].add((route, message["from"]))
            #for route in message["routes"][prefix]:
            #    self.routes[prefix].add((route, message["from"]))
        self.log.info("BANDWIDTH_DIMEJI_BBBBB _process_add_route: %s" %self.routes)
        return

    def _process_remove_route(self, message):
        if message["prefix"] in self.prefixes:
            self.log.info("BANDWIDTH_DIMEJI _process_remove_route Prefix: %s and for Route %s\n\n\n" %(message["prefix"], message["route"]))
            self.routes[message["prefix"]].remove((message["route"],message["from"]))
            self.counter = 0
    
    @abstractmethod
    def _send_latest_best_route(self):
        pass
    
    @abstractmethod
    def _fetch_route(self, exitpeer, nexthop):
        pass

    @abstractmethod
    def _process_send_best_route(self, message):
        self.log.info("PARMetricsModule_DIMEJI_BBB _process_send_best_route print before pass!!!!!!!")
        pass

class Bandwidth(BasePARModule):
    def __init__(self, name, command_queue, prefixes, peer_addrs):
        super(Bandwidth, self).__init__(name, command_queue, prefixes, peer_addrs)
        self.log = logging.getLogger("BANDWIDTH")
        #self.actions = {
        #    "get": self._process_send_best_route,
        #}
        self.command_queue = command_queue


    def _fetch_route(self, exitpeer, nexthop): 
        best_routes  = {}
        for prefix, routes_desc in self.routes.items():
            for desc in routes_desc:
                route, exitnode = desc
                if (exitnode == exitpeer) and (nexthop == route.nexthop): 
                    best_routes[prefix] = [desc]
        self.log.info("PARMetricsModule_DIMEJI_VALIDATION _FETCH_ROUTE returning: %s" %best_routes)
        return best_routes
 

    def _send_latest_best_route(self):
        self.last_performed = time.time()
        best_routes = {}
        for prefix, routes in self.routes.items():
            max_index = len(routes) - 1
            if (len(routes) != 0) and (self.counter <= max_index):
                #self.counter += 1
                lroutes = list(routes)
                self.log.info("BANDWIDTH_DIMEJI _send_latest_best_route length of available routes for PAR is %s" %len(routes))
                self.log.info("BANDWIDTH_DIMEJI _send_latest_best_route send route %s for counter %s\n\n" %(lroutes[self.counter], self.counter))
                best_routes[prefix] = [lroutes[self.counter]]
                self.counter += 1
                if self.counter > max_index:
                    self.log.info("BANDWDITH_DIMEJI _send_latest_best_route self.counter is %s to be set to 0\n\n" %self.counter)
                    self.counter = 0
            elif len(routes) == 1:
                self.counter = 0
                lroutes = list(routes)
                self.log.info("BANDWIDTH_DIMEJI _send_latest_best_route length of available routes for PAR is %s" %len(routes))
                self.log.info("BANDWIDTH_DIMEJI _send_latest_best_route send route %s for counter %s\n\n" %(lroutes[self.counter], self.counter))
                best_routes[prefix] = [lroutes[self.counter]]
                self.counter += 1
                best_routes[prefix] = [random.choice(list(routes))]
            else:
                best_routes[prefix] = []

        self.log.info("BANDWITH_DIMEJI _send_latest_best_route: %s" % best_routes)
        return best_routes

    def _process_send_best_route(self, message):
        if message["from"] not in self.enabled_peers:
            return
        if len(self.best_routes) == 0:
            best_routes = self._send_latest_best_route()
            self.command_queue.put(("par-update", {
                "routes": best_routes,
                "type": self.name,
            }))
        else:
            self.command_queue.put(("par-update", {
                "routes": self.best_routes,
                "type": self.name,
            }))
        self.log.info("BANDWIDTH_DIMEJI_FJDDHGDJDH^&*^SDHFKDHDH _Process_send_best_route message sent !!!")
        return

