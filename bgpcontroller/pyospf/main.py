# !/usr/bin/env python
# -*- coding:utf-8 -*-

from pyospf import log
from pyospf.core.core import init_probe

from multiprocessing import Process
from ctypes import cdll, byref, create_string_buffer

class Listener(Process):
    def __init__(self, out_queue, config):
        Process.__init__(self, name="ospf_topo")
        self.out_queue = out_queue

        # Retrieve the config and set the defaults if a field has one
        self.config = config
        self._set_config_default("area", "0.0.0.0")
        self._set_config_default("hello_interval", 10)
        self._set_config_default("link_type", "Broadcast")
        self._set_config_default("options", "E,O")
        self._set_config_default("mtu", 1500)
        self._set_config_default("rxmt_interval", 5)
        self._set_config_default("packet_display", False)


    def _set_config_default(self, name, default):
        """
            Check if the current config dictionary alredy has a attribute
            defined, if it dosen't we will create it and set it to a default
            value
        """
        if name not in self.config:
            self.config[name] = default

    def run(self):
        # Rename the process
        libc = cdll.LoadLibrary("libc.so.6")
        buff = create_string_buffer(len(self.name))
        buff.value = (self.name.encode())
        libc.prctl(15, byref(buff), 0, 0, 0)

        # Initiate the listener and OSPF logger
        log.init_log()
        init_probe(self.config, self.out_queue)
