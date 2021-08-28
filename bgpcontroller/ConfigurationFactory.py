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

import logging

from BGPPeer import BGPPeer
from SDNPeer import SDNPeer
from BGPSpeaker import BGPSpeaker
from RouteTable import RouteTable
from PolicyObject import ACCEPT
from RouteEntry import DEFAULT_LOCAL_PREF
from Configuration import ConfigLoader, ConfigValidator
from ConfigurationFilterFactory import FilterFactory
import PARMetricsModule


class ConfigFactory(object):
    """
        Load all the configuration parameters and build the required objects
        such as peers, filters and tables.
    """

    def __init__(self, internal_command_queue, outgoing_exabgp_queue,
                 outgoing_control_queue, configname="config.yaml"):

        self.log = logging.getLogger("Config")

        self.filters = []
        self.peers = []
        self.tables = []
        self.bgpspeakers = []
        self.local_topology = []
        self.PARModules = []
        self.datapathID = []

        self.config_loader = ConfigLoader(configname)
        self.grpc_port = self.config_loader.grpc_port
        self.grpc_address = self.config_loader.grpc_address

        # Build object to compare stuff for performance-aware prefixes
        # Do something here. to be done later
        ### TODO: Delete _self._build_bwidht_monitor and
        ###       self.build_latency_monitor. These have been
        ###       superseded by self._build_traffic_modules.
        if hasattr(self.config_loader, 'bandwidth'):
            self._build_bwidth_monitor(internal_command_queue,
                                       outgoing_control_queue)

        if hasattr(self.config_loader, 'latency'):
            self.build_latency_monitor(internal_command_queue,
                                       outgoing_control_queue)

        if hasattr(self.config_loader, 'PARTrafficTypes'):
            self._build_traffic_modules(internal_command_queue,
                                        outgoing_control_queue)
        # Build the filters, tables and peers objects from the config file
        self._build_filters()
        self._build_tables(outgoing_control_queue)
        self._build_speakers(outgoing_exabgp_queue, outgoing_control_queue,
                             internal_command_queue)

        #self._build_peers(outgoing_exabgp_queue, outgoing_control_queue,
        #                  internal_command_queue, self.config_loader.peers)

        # Process the export to peers of the tables config section
        for table_name in self.config_loader.tables:
            # Retrieve the config section
            table_cfg = self.config_loader.tables[table_name]

            obj = self._get_table(table_name)
            if obj is None:
                raise Exception("Config: Table %s doesn't exist!" % table_name)

            if "export_peers" in table_cfg:
                peers = ConfigValidator.extract_array_data(
                        table_cfg["export_peers"], str, "export_peers",
                        "table %s" % table_name)
                for peer_name in peers:
                    peer = self._get_peer(peer_name)

                    if peer is None:
                        # check if we are exporting to table rather than peer
                        # TODO enforce unique names across all tables and peers
                        peer = self._get_table(peer_name)
                        if peer is None:
                            raise Exception(
                                "Config: Table %s export peer %s doesn't exist!"
                                % (table_name, peer_name))

                    obj.add_export_peer(peer)
                    try:
                        peer.add_import_tables(obj)
                    except AttributeError:
                        # for now, only peers need to know their source tables
                        # TODO allow tables to know so they can request reloads
                        pass

        # Validate the local topology config
        if isinstance(self.config_loader.local_topology, list):
            for topo_sec in self.config_loader.local_topology:
                if "protocol" in topo_sec:
                    # XXX: Add any extra topology protocol names here
                    if topo_sec["protocol"] not in ["ospf"]:
                        raise Exception("Config: Unknown protocol %s" %
                                topo_sec["protocol"])

                    self.local_topology.append(topo_sec)
                elif "static_file" in topo_sec:
                    self.local_topology.append(topo_sec)
                else:
                    raise Exception("Config: Invalid topology section type")
        else:
            # Expand the shorthand to its full dictionary equivalent
            self.local_topology.append(
                    {"static_file": self.config_loader.local_topology})

        # free up memory
        self.config_loader.clean()

    def _build_filters(self):
        """
            Initialise the filters
        """
        factory = FilterFactory(self.asn)
        self.filters = factory.build(self.config_loader.filters)

    def _build_peers(self, outgoing_exabgp_queue, outgoing_control_queue,
            internal_command_queue, peers_cfg):
        """
            Iterate through all peers defined in the config file constructing
            their object representations.
        """
        #for peer_name in self.config_loader.peers:
        for peer_name in peers_cfg:
            # Retrieve the config section and retrieve the peer ASN
            #peer_cfg = self.config_loader.peers[peer_name]
            peer_cfg = peers_cfg[peer_name]
            peerASN = self._translate_self_asn(peer_cfg["asn"])

            # Retrieve optional param attributes, if not defined set to default
            if "preference" in peer_cfg:
                pref = peer_cfg["preference"]
            else:
                pref = DEFAULT_LOCAL_PREF
            if "default_import" in peer_cfg:
                def_imp = peer_cfg["default_import"]
            else:
                def_imp = ACCEPT
            if "default_export" in peer_cfg:
                def_exp = peer_cfg["default_export"]
            else:
                def_exp = ACCEPT
            if "enable-par" in peer_cfg:
                enable_par = peer_cfg["enable-par"]
            else:
                enable_par = False

            try:
                dpport = peer_cfg["dp-grpc"]
            except KeyError:
                raise Exception("Config: Peer %s is PAR enabled but\
                    DP-GRPC port not defined" % peer_name)
            self.datapathID.append((peer_cfg["address"], dpport))


            # Validate the required fields that need strict data type
            ConfigValidator.validate_type(peerASN, int, "ASN",
                    "peer %s" % peer_name)
            ConfigValidator.validate_type(peer_cfg["type"], str, "type",
                    "peer %s" % peer_name)
            ConfigValidator.validate_type(peer_cfg["address"], str, "address",
                    "peer %s" % peer_name)
            ConfigValidator.validate_type(pref, int, "preference",
                    "peer %s" % peer_name)
            ConfigValidator.validate_type(def_imp, bool, "default_import",
                    "peer %s" % peer_name)
            ConfigValidator.validate_type(def_exp, bool, "default_export",
                    "peer %s" % peer_name)
            if enable_par is True:
                ConfigValidator.validate_type(dpport, int, "dp-grpc",
                        "peer %s" % peer_name)

            if peer_cfg["type"].lower() == "bgp":
                obj = BGPPeer(peer_name, peerASN, peer_cfg["address"],
                        outgoing_exabgp_queue, outgoing_control_queue,
                        internal_command_queue, preference=pref,
                        default_import=def_imp, default_export=def_exp,
                        par=enable_par)
            elif peer_cfg["type"].lower() == "sdn":
                obj = SDNPeer(peer_name, peerASN, peer_cfg["address"],
                        None, outgoing_control_queue, internal_command_queue,
                        default_import=def_imp, default_export=def_exp)
            else:
                raise Exception("Config: Peer %s has an unknown type %s" % (
                            peer_name, peer_cfg["type"]))

            # Process any aggregate prefixes if defined
            if "aggregate_prefix" in peer_cfg:
                for aggregate in ConfigValidator.extract_array_data(
                        peer_cfg["aggregate_prefix"],
                        str, "aggregate_prefix", "peer %s" % peer_name):
                    obj.add_aggregate_prefix(aggregate)

            # Get interfaces for installing segments routes, raise error if not defined
            ### Disable this!!! Controller should query dataplane for interfaces.
            #if "interfaces" not in peer_cfg:
            #    raise Exception("Peer does not have interfaces for installing segments!!!")
            #else:
            #    interfaces = []
            #    for interface in ConfigValidator.extract_array_data(
            #            peer_cfg["interfaces"], str, "interfaces",
            #            "peer %s" % peer_name):
            #        interfaces.append(interface)
            #    obj.interfaces = interfaces

            # Process table associates of the peer (if defined)
            if "tables" in peer_cfg:
                tables = []
                for table in ConfigValidator.extract_array_data(
                        peer_cfg["tables"], str, "tables",
                        "peer %s" % peer_name):

                    tb = self._get_table(table)
                    if tb is None:
                        raise Exception("Config: Unknown table %s in Peer %s" %
                                (table, peer_name))

                    tables.append(tb)
                obj.export_tables = tables

            # Process any filter associations and add the peer to the
            # initialised list
            self._associate_filters(obj, peer_cfg)
            self.peers.append(obj)

    def _build_tables(self, outgoing_control_queue):
        """
            Build the table objects from the configuration section
        """
        for table_name in self.config_loader.tables:
            # Retrieve the config section
            table_cfg = self.config_loader.tables[table_name]

            if "default_import" in table_cfg:
                def_imp = table_cfg["default_import"]
            else:
                def_imp = ACCEPT
            if "default_export" in table_cfg:
                def_exp = table_cfg["default_export"]
            else:
                def_exp = ACCEPT

            # Validate the fields
            ConfigValidator.validate_type(def_imp, bool, "default_import",
                    "table %s" % table_name)
            ConfigValidator.validate_type(def_exp, bool, "default_export",
                    "table %s" % table_name)

            obj = RouteTable(table_name, outgoing_control_queue,
                    default_import=def_imp, default_export=def_exp)

            # Process any aggregate prefixes if defined
            if "aggregate_prefix" in table_cfg:
                for aggregate in ConfigValidator.extract_array_data(
                        table_cfg["aggregate_prefix"],
                        str, "aggregate_prefix", "table %s" % table_name):
                    obj.add_aggregate_prefix(aggregate)

            self._associate_filters(obj, table_cfg)
            self.tables.append(obj)

    def _build_speakers(self, outgoing_exabgp_queue, outgoing_control_queue,
                        internal_command_queue):
        """
            Build the BGP speaker objects from the configuration section
        """
        for speaker in self.config_loader.bgpspeakers:
            # Retrieve the config section
            speaker_cfg = self.config_loader.bgpspeakers[speaker]
            peer_addrs = []
            # Validate the fields
            ConfigValidator.validate_type(speaker_cfg["address"], str, "address",
                                          "BGP Speaker %s" % speaker)
            ConfigValidator.validate_type(speaker_cfg["type"], str, "type",
                                          "BGP Speaker %s" % speaker)
            
            self._build_peers(outgoing_exabgp_queue, outgoing_control_queue,
                              internal_command_queue, speaker_cfg["peers"])
            for peer_name in speaker_cfg["peers"]:
                peer_addrs.append(speaker_cfg["peers"][peer_name]
                                  ["address"])
            obj = BGPSpeaker(speaker, speaker_cfg["address"], speaker_cfg["type"],
                             peer_addrs, internal_command_queue, outgoing_control_queue)
            self.bgpspeakers.append(obj)

    def _build_bwidth_monitor(self, internal_command_queue,
                              outgoing_control_queue):
        """
            Build the PAR bandwidth object from the configuration section
        """
        prefixes = self.config_loader.bandwidth
        enabled_peers = []
        for speaker in self.config_loader.bgpspeakers:
            speaker_cfg = self.config_loader.bgpspeakers[speaker]
            for peer_name in speaker_cfg["peers"]:
                peerdict = speaker_cfg["peers"][peer_name]
                if "enable-par" not in peerdict:
                    continue

                if peerdict["enable-par"] is True:
                    enabled_peers.append(peerdict["address"])
        obj = PARMetricsModule.Bandwidth("bandwidth", internal_command_queue,
                                         prefixes, enabled_peers)
        self.PARModules.append(obj)


    def _build_traffic_modules(self, internal_command_queue,
                              outgoing_control_queue):
        """
            Build the PAR traffic module object from the configuration section
        """
        enabled_peers = []
        for speaker in self.config_loader.bgpspeakers:
            speaker_cfg = self.config_loader.bgpspeakers[speaker]
            for peer_name in speaker_cfg["peers"]:
                peerdict = speaker_cfg["peers"][peer_name]
                if "enable-par" not in peerdict:
                    continue

                if peerdict["enable-par"] is True:
                    enabled_peers.append(peerdict["address"])
                    
        for traffic, flows in self.config_loader.PARTrafficTypes.items():
            self.log.info("Print flows: %s" %flows)
            obj = PARMetricsModule.TrafficModule(traffic, internal_command_queue,
                                                 flows, enabled_peers)
            self.PARModules.append(obj) 


    def _associate_filters(self, obj, cfg_section):
        """
            Associate import and export filters for a configuration section
            to a specific config object.
        """
        if "filters" in cfg_section:
            if "import" in cfg_section["filters"]:
                for filter_name in ConfigValidator.extract_array_data(
                        cfg_section["filters"]["import"], str,
                        "import filters", "object %s" % obj.name):
                    filt = self._get_filter(filter_name)

                    if filt is None:
                        raise Exception(
                                "Config: Object %s has unknown filter %s" %
                                (obj.name, filter_name))

                    obj.add_import_filter(filt)

            if "export" in cfg_section["filters"]:
                for filter_name in ConfigValidator.extract_array_data(
                        cfg_section["filters"]["export"], str,
                        "export filters", "object %s" % obj.name):
                    filt = self._get_filter(filter_name)

                    if filt is None:
                        raise Exception(
                                "Config: Object %s has unknown filter %s" %
                                (obj.name, filter_name))

                    obj.add_export_filter(filt)

    def _translate_self_asn(self, obj):
        """
            Replace the self.asn dynamic config keyword with their actual
            value defined in the config for the ASN.
        """
        if isinstance(obj, list):
            translated = []
            for item in obj:
                translated.append(self.asn if (isinstance(item, str) and
                    item.lower() == "self.asn") else item)
            return translated
        else:
            return self.asn if (isinstance(obj, str) and
                obj.lower() == "self.asn") else obj

    def _get_filter(self, name):
        return next((x for x in self.filters if x.name == name), None)

    def _get_peer(self, name):
        return next((x for x in self.peers if x.name == name), None)

    def _get_table(self, name):
        return next((x for x in self.tables if x.name == name), None)

    @property
    def asn(self):
        return self.config_loader.asn

    @property
    def local_routes(self):
        return self.config_loader.local_routes

    def debug(self, peers=None, tables=None, bgpspeakers=None):
        """
            Dump the values of a array of peers and tables
        """
        if peers is None:
            peers = self.peers
        if tables is None:
            tables = self.tables
        if bgpspeakers is None:
            bgpspeakers = self.bgpspeakers

        self.log.debug("---------------------------")

        for p in peers:
            t = "bgp" if isinstance(p, BGPPeer) else "sdn"
            if t == "bgp":
                self.log.debug("Peer(type=%s, asn=%s, name=%s, addr= %s, import=%s, export=%s, pref=%d)" %
                        (t, p.asn, p.name, p.address, p.default_import, p.default_export, p.preference))
            else:
                self.log.debug("Peer(type=%s, asn=%s, name=%s, import=%s, export=%s)" % (t, p.asn, p.name,
                        p.default_import, p.default_export))

            for in_filt in p.import_filter:
                self.log.debug("  FILTER IMP: %s" % str(in_filt))
                for fr in in_filt.rules:
                    self.log.debug("    RULE: %s" % str(fr))
                for fa in in_filt.actions:
                    self.log.debug("    ACTION: %s" % str(fa))

            for out_filt in p.export_filter:
                self.log.debug("  FILTER OUT: %s" % str(out_filt))
                for fr in out_filt.rules:
                    self.log.debug("    RULE: %s" % str(fr))
                for fa in out_filt.actions:
                    self.log.debug("    ACTION: %s" % str(fa))

            self.log.debug("  AGGREGATE PREFIX: %s" % (",".join(["%s" % (x) for x in p.aggregate])))
            self.log.debug("  TABLES:")
            for x in p.export_tables:
                self.log.debug("      %s" % x)


        self.log.debug("")
        self.log.debug("! TABLES: !")
        for t in tables:
            self.log.debug("Table(name=%s, import=%s, export=%s)" %
                (t.name, t.default_import, t.default_export))

            for in_filt in t.import_filter:
                self.log.debug("  FILTER IMP: %s" % str(in_filt))
                for fr in in_filt.rules:
                    self.log.debug("    RULE: %s" % str(fr))
                for fa in in_filt.actions:
                    self.log.debug("    ACTION: %s" % str(fa))

            for out_filt in t.export_filter:
                self.log.debug("  FILTER OUT: %s" % str(out_filt))
                for fr in out_filt.rules:
                    self.log.debug("    RULE: %s" % str(fr))
                for fa in out_filt.actions:
                    self.log.debug("    ACTION: %s" % str(fa))

            self.log.debug("  AGGREGATE PREFIX: %s" % (",".join(["%s" % (x) for x in t.aggregate])))
            self.log.debug("  EXPORT PEERS: %s" % (",".join(["%s" % (x.name) for x in t.export_peers])))
        self.log.debug("-----------------------------------")

if __name__ == "__main__":
    #conf = ConfigFactory(None, None, None, "/scratch/bgpsdn/config.example.yaml")
    conf = ConfigFactory(
                None, None, None,
                "/home/ubuntu/git-repos/overwatch/bgpcontroller/config.yaml")
    conf.debug()

