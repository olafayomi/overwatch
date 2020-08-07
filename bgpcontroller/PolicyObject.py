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
from multiprocessing36 import Process, Queue
from queue import Empty
from ctypes import cdll, byref, create_string_buffer
from collections import defaultdict
from Prefix import Prefix
from RouteEntry import RouteEntry, DEFAULT_LOCAL_PREF
from Filter import Filter, PrefixFilterRule
import messages_pb2 as pb

ACCEPT = True
REJECT = False

class PolicyObject(Process):
    __metaclass__ = ABCMeta

    def __init__(self, name, control_queue,
            default_import=ACCEPT, default_export=ACCEPT):
        Process.__init__(self, name=name)

        # XXX: The self.log attribute is defined by the inheriting classes.
        # This will allow us to specify the correct name for each policy object
        # based on the child module.

        self.control_queue = control_queue
        self.default_import = default_import
        self.default_export = default_export
        self.import_filter = []
        self.export_filter = []
        self.aggregate = []
        self.mailbox = Queue()
        self.daemon = True
        self.actions = {
            #"add_import_filter": self._process_add_import_filter_message,
            #"get_import_filters": self._process_get_import_filters_message,
        }
        self._gauge_metrics = []
        self._histogram_metrics = []
        self.metrics = {}
        self.batchsize = 500000
        self._add_histogram("policy_export_filter_duration")

    def __str__(self):
        return "PolicyObject(%s, import:%s (%d rules) / export:%s (%d rules))" \
            % (self.name, self.default_import, len(self.import_filter),
                    self.default_export, len(self.export_filter))

    def run(self):
        libc = cdll.LoadLibrary("libc.so.6")
        buff = create_string_buffer(len(self.name)+5)
        buff.value = ("foo " + self.name).encode()
        libc.prctl(15, byref(buff), 0, 0, 0)

        # this has to happen once the process is forked, otherwise the metrics
        # will all be created for the parent process
        self._initialise_metrics()

        callbacks = []

        while True:
            try:
                serialised = self.mailbox.get(block=True, timeout=0.1)
            except Empty:
                # if we reach the timeout then no messages have been received
                # for a while, trigger all the callbacks
                for callback, timeout in callbacks:
                    self.log.debug(
                            "%s no recent messages, callback %s triggered",
                            self.name, callback)
                    callback()
                callbacks.clear()
                continue

            message = pb.Message()
            message.ParseFromString(serialised)
            if message.type in self.actions:
                # actions may trigger a callback (e.g. advertising routes) but
                # we don't want to repeatedly perform these actions, so delay
                # briefly in case we get more messages
                callback = self.actions[message.type](message)
                if callback and not any(callback == x for x, y in callbacks):
                    callbacks.append((callback, time.time() + 10))
                    self.log.debug("%s saving callback %s", self.name, callback)
            else:
                self.log.warning("%s ignoring unknown message type %s",
                        self.name, message.type)

            # we don't need to hold onto this message until it gets replaced,
            # delete it now and possibly save a large amount of space
            del message

            # if it's been too long since we added a callback, deal with it
            # now before continuing to process other messages
            while len(callbacks) > 0 and callbacks[0][1] < time.time():
                callback, timeout = callbacks.pop(0)
                self.log.debug("%s Triggering overdue callback %s", self.name,
                        callback)
                callback()


    def add_import_filter(self, filter_):
        # don't allow filters with the same name
        for item in self.import_filter:
            if item.name == filter_.name:
                return False
        self.import_filter.append(filter_)
        return True

    def remove_import_filter(self, name):
        found = False
        for item in self.import_filter:
            if item.name == name:
                found = True
                break
        if found:
            self.import_filter = [
                x for x in self.import_filter if x.name != name
            ]
        return found

    def get_import_filters(self):
        return self.import_filter

    def add_export_filter(self, filter_):
        self.export_filter.append(filter_)

    def add_aggregate_prefix(self, prefix):
        self.aggregate.append(Prefix(prefix))

    def filter_export_routes(self, export_routes, copy=True):
        with self.metrics["policy_export_filter_duration"].time():
            filtered_routes = defaultdict(list)
            for route in export_routes:
                # if filter_export_route() is successful it will return a
                # copy of the route so that filter actions etc don't
                # clobber the original version
                route_copy = self.filter_export_route(route, copy=copy)
                if route_copy and route_copy not in filtered_routes[route.prefix]:
                    filtered_routes[route.prefix].append(route_copy)
            # perform aggregation if required
            if len(self.aggregate) > 0:
                filtered_routes = self._aggregate_routes(filtered_routes)
            return filtered_routes

    def filter_import_route(self, route, copy=False):
        return self._filter_route(self.import_filter, route,
                self.default_import, copy)

    def filter_export_route(self, route, copy=False):
        return self._filter_route(self.export_filter, route,
                self.default_export, copy)

    def _filter_route(self, filters, route, default, copy=False):
        for filter_ in filters:
            result = filter_.match(route)
            if result is True:
                return filter_.apply(route, copy)
            if result is False:
                return None
        if default:
            if copy:
                return deepcopy(route)
            return route
        return None

    def _update_aggregate_route(self, aggregate, route):
        # update communities to include all those from member routes
        aggregate.add_communities(route.communities())

        # update the AS path to contain the longest matching path
        min_path = min(len(aggregate.as_path()), len(route.as_path()))

        if min_path > 0:
            for i in range(min_path):
                if aggregate.as_path()[i] != route.as_path()[i]:
                    # if the ASNs at this point of the path don't match, then
                    # remove them from the aggregate path - they are no longer
                    # common elements to be kept
                    removed = aggregate.as_path()[i:]
                    aggregate.set_as_path(aggregate.as_path()[:i])
                    # add the remainder of the ASNs to the AS set
                    aggregate.add_as_set(list(removed))
                    different = True
                    break
                different = False
            # add all the non-matching ASNs from paths into the AS set
            if different is True:
                aggregate.add_as_set(list(route.as_path()[i:]))
            if different is False and len(route.as_path()) > min_path:
                aggregate.add_as_set(list(route.as_path()[i+1:]))
        elif len(route.as_path()) > 0:
            aggregate.add_as_set(list(route.as_path()))

        if route.as_set() is not None:
            aggregate.add_as_set(route.as_set())
        return aggregate

    def _aggregate_routes(self, filtered_routes):
        aggregate_routes = {}
        for aggregate in self.aggregate:
            # only include the aggregate if at least one of the contributing
            # routes is going to be announced
            for prefix, routes in filtered_routes.items():
                if aggregate.contains(prefix):
                    if aggregate not in aggregate_routes:

                        # create new route here so it doesn't mess with others
                        aggregate_route = RouteEntry(
                                routes[0].origin,
                                0,
                                aggregate,
                                routes[0].nexthop,
                                routes[0].as_path(),
                                routes[0].as_set(),
                                routes[0].communities(),
                                DEFAULT_LOCAL_PREF)

                        for route in routes[1:]:
                            self._update_aggregate_route(aggregate_route, route)

                        aggregate_routes[aggregate] = [aggregate_route]
                    else:
                        # already aggregated prefix, add to the existing one
                        for route in routes:
                            self._update_aggregate_route(
                                    aggregate_routes[aggregate][0], route)
                else:
                    # don't aggregate the prefix, keep it as it is
                    aggregate_routes[prefix] = routes
        return aggregate_routes

    def _process_add_import_filter_message(self, message):
        # make sure the minimum required fields are present in the message
        if not all(arg in message for arg in ["name"]):
            self.log.error("Add import filter failed. Missing name!")
            return False

        if "onmatch" in message:
            import_filter = Filter(message["name"], onmatch=message["onmatch"])
        else:
            import_filter = Filter(message["name"])

        if "prefixes" in message:
            for prefix in message["prefixes"]:
                import_filter.add_rule(PrefixFilterRule(prefix))
        # TODO other filters

        if len(import_filter.rules) == 0 and len(import_filter.actions) == 0:
            result = False
        else:
            result = self.add_import_filter(import_filter)

        self.control_queue.put(json.dumps(result))
        if result:
            self._reload_import_filters()

    def _process_get_import_filters_message(self, message):
        self.control_queue.put([x.toJSON() for x in self.get_import_filters()])

    def _add_gauge(self, name, initial_value):
        # add the gauge to a temporary list so it can be created later on
        self._gauge_metrics.append((name, initial_value))

    def _add_histogram(self, name):
        # add the histogram to a temporary list so it can be created later on
        self._histogram_metrics.append(name)

    def _initialise_metrics(self):
        # don't import anything to do with prometheus until after we are sure
        # the prometheus_multiproc_dir environment variable is set
        from prometheus_client import Gauge, Histogram
        # create all the metrics from the temporary lists built during the
        # policy object initialisation
        for name, value in self._gauge_metrics:
            # descriptions don't seem to work in multiprocess?
            gauge = Gauge(name, None, ["name"])
            # pre-set the label so we don't need to look it up every time
            self.metrics[name] = gauge.labels(name=self.name)
            if value == "now":
                self.metrics[name].set_to_current_time()
            else:
                self.metrics[name].set(value)
        for name in self._histogram_metrics:
            # descriptions don't seem to work in multiprocess?
            histogram = Histogram(name, None, ["name"])
            # pre-set the label so we don't need to look it up every time
            self.metrics[name] = histogram.labels(name=self.name)

    def _create_update_message(self, routes=None, done=True):
        message = pb.Message()
        message.type = pb.Message.UPDATE
        message.update.source = self.name
        if hasattr(self, "asn"):
            message.update.asn = self.asn
        if hasattr(self, "address"):
            message.update.address = self.address
        if routes:
            message.update.routes = routes
        message.update.done = done
        return message
