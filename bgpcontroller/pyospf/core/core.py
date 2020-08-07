#!/usr/bin/env python
# -*- coding:utf-8 -*-

import logging
import threading

from pyospf.core.ospfInstance import OspfInstance

LOG = logging.getLogger(__name__)

def init_probe(config, topo_queue):
    oi = OspfInstance(config, topo_queue)
    oi.run()
