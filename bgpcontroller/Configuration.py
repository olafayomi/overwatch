#!/usr/bin/env python

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

import os.path
import yaml


class ConfigLoader(object):
    def __init__(self, conf_file="config.yaml"):
        """
            Load and parse the yaml formatted config file and save the top
            level sections for later processing.
        """
        self.conf_file = conf_file

        # YAML parse the config file and retrieve the top level conf items
        with open(self.conf_file, "r") as stream:
            config = yaml.safe_load(stream)

        self.asn = config["asn"]
        self.grpc_port = config["grpc-port"]
        self.grpc_address = config["grpc-address"]

        # Retrieve the local topology and local import routes config file paths
        # NOTE: all referenced files from the config will be loaded relative
        # to the location of the config file !
        self.local_topology = config["local_topology"]
        if isinstance(self.local_topology, list):
            for topo_sec in self.local_topology:
                if "static_file" in topo_sec:
                    topo_sec["static_file"] = self.relative_path(
                            topo_sec["static_file"])

                    if (not isinstance(topo_sec["static_file"], str) or
                            not os.path.isfile(topo_sec["static_file"])):
                        raise Exception("Config: Local topology file %s doesn't exist"
                                        % (topo_sec["static_file"]))

        elif isinstance(self.local_topology, str):
            self.local_topology = self.relative_path(self.local_topology)

            if (not isinstance(self.local_topology, str) or
                    not os.path.isfile(self.local_topology)):
                raise Exception("Config: Local topology file %s doesn't exist"
                                % (self.local_topology))
        else:
            raise Exception("Config: local_topology can either be a list or a string. Invalid type!")

        # Get the local route import file, peers, tables and filters sections
        self.local_routes = self.relative_path(config["local_routes"]) if "local_routes" in config else ""

        if "bgpspeakers" in config:
            self.bgpspeakers = config["bgpspeakers"]
        else:
            raise Exception("Config: No bgpspeakers defined in file %s" % conf_file)

        #if "peers" in config:
        #    self.peers = config["peers"]
        #else:
            #raise Exception("Config: No peers defined in file %s" % conf_file)

        if "tables" in config:
            self.tables = config["tables"]
        else:
            raise Exception("Config: No tables defined in file %s" % conf_file)

        if "filters" in config:
            self.filters = config["filters"]

        if "performance-aware" in config:
            performance_aware = config["performance-aware"]
            self.PARTrafficTypes = {}
            if isinstance(performance_aware, dict) and \
                (len(performance_aware) != 0):
                for traffictype, flows in performance_aware.items():
                    self.PARTrafficTypes[traffictype] = flows['flows']
            else:
                raise Exception("Config: No performance-aware traffic defined in file %s" % conf_file)


    def relative_path(self, filename):
        """
            Return an absolute file path relative to the configuration files
            parent directory.
        """
        conf_dir = os.path.dirname(self.conf_file)
        return os.path.join(conf_dir, filename)

    def clean(self):
        """
            Remove references from large yaml config sections such as the
            peers, table and filters array. This method needs to be called
            once the config sections have been processed.
        """
        
        #if self.peers:
        #    del self.peers
        del self.tables
        del self.filters
        del self.bgpspeakers
        del self.local_topology
        if hasattr(self, 'PARTrafficTypes'):
            del self.PARTrafficTypes


class ConfigValidator(object):
    @staticmethod
    def validate_type(field, expected_type, field_name, parent_name):
        """
            Validate a field type, if the type doesn't match a exception will
            be thrown.
        """
        if not isinstance(field, expected_type):
            raise Exception("Config: %s of %s has invalid type, expected %s, got %s" % (
                    field_name, parent_name, expected_type.__name__, type(field).__name__))

    @staticmethod
    def validate_any_type(field, expected_types, field_name, parent_name):
        """
            Validate a field type from a list of types. If the field doesn't
            match any of the types in the expected type list then a exception
            will be thrown.
        """
        for t in expected_types:
            try:
                ConfigValidator.validate_type(field, t, field_name, parent_name)
                return
            except:
                continue

        types_str = " or ".join(["%s" % t.__name__ for t in expected_types])
        raise Exception("Config: %s of %s has invalid type, expected %s, got %s" % (
                field_name, parent_name, types_str, type(field).__name__))

    @staticmethod
    def validate_list_type(field, expected_type, field_name, parent_name,
                           strict_list=True):
        """
            Validate a list of items for a specific field type, if not valid
            an exception will be thrown.
        """
        if isinstance(field, list):
            for item in field:
                ConfigValidator.validate_type(item, expected_type,
                                              field_name, parent_name)
        elif strict_list is False:
            ConfigValidator.validate_type(field, expected_type,
                                          field_name, parent_name)
        else:
            raise Exception("Config: %s of %s has to be a list" % (
                    field_name, parent_name))

    @staticmethod
    def extract_array_data(field, expected_type, field_name, parent_name,
                           strict_list=False):
        """
            Validate a fields type and retrieve the data as an array.
        """
        if strict_list and not isinstance(field, list):
            raise Exception("Config: %s of %s has to be a list" % (
                    field_name, parent_name))

        data = []
        if isinstance(field, list):
            for item in field:
                ConfigValidator.validate_type(item, expected_type,
                                              field_name, parent_name)
                data.append(item)
        else:
            ConfigValidator.validate_type(field, expected_type,
                                          field_name, parent_name)
            data.append(field)

        return data
