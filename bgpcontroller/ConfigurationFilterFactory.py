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
import Filter
from Configuration import ConfigValidator

class FilterFactory(object):
    """
        Factory to initialise objects based on the filter config section.
    """
    def __init__(self, asn):
        self.log = logging.getLogger("Config.Filter")
        self.asn = asn

    def build(self, cfg):
        """
            Iterate through all filters defined in the config file and
            construct their object representations.
        """
        filters = []

        for filter_cfg in cfg:
            if "onmatch" in filter_cfg:
                obj = Filter.Filter(filter_cfg["name"], filter_cfg["onmatch"])
            else:
                obj = Filter.Filter(filter_cfg["name"])

            # If the filter has rules process them
            if "rules" in filter_cfg:
                for filter_rule in filter_cfg["rules"]:
                    obj.add_rule(self._build_filter_rule(filter_rule))

            # If the filter defines actions process them
            if "actions" in filter_cfg:
                for filter_action in filter_cfg["actions"]:
                    # Retrieve the value of the action
                    if "value" in filter_action:
                        value = self._translate_self_asn(filter_action["value"])
                    else:
                        value = None

                    if value is None:
                        raise Exception("Config: Missing action for value %s" %
                                (filter_action["action"]))

                    # Add the appropriate action
                    if filter_action["action"] == "ADD_COMMUNITY":
                        obj.add_action(Filter.Filter.ADD_COMMUNITY, value)
                    elif filter_action["action"] == "REMOVE_COMMUNITY":
                        obj.add_action(Filter.Filter.REMOVE_COMMUNITY, value)
                    elif filter_action["action"] == "PREPEND_ASPATH":
                        obj.add_action(Filter.Filter.PREPEND_ASPATH, value)
                    else:
                        raise Exception("Config: Unknown filter action %s" %
                                (filter_action["action"]))

            # Add the filter to the list of initialised filters
            filters.append(obj)

        return filters

    def _build_filter_rule(self, cfg_section):
        """
            Build a filter rule based on its type
        """
        if cfg_section["type"] == "AlwaysMatch":
            return self._build_normal_filter_rule(Filter.AlwaysMatchRule,
                    cfg_section, value_req=False)
        elif cfg_section["type"] == "InvertFilter":
            return self._build_nested_filter_rule(Filter.InvertFilterRule,
                    cfg_section, has_on_match=False)
        elif cfg_section["type"] == "MatchPrefixLength":
            ConfigValidator.validate_any_type(cfg_section["match"], [int, str],
                    "match", "MatchPrefixLength")
            return self._build_normal_filter_rule(Filter.MatchPrefixLengthRule,
                    cfg_section)
        elif cfg_section["type"] == "PrefixFilter":
            ConfigValidator.validate_list_type(cfg_section["match"], str,
                    "match", "PrefixFilter", strict_list=False)
            return self._build_normal_filter_rule(Filter.PrefixFilterRule,
                    cfg_section)
        elif cfg_section["type"] == "MartiansFilter":
            return self._build_normal_filter_rule(Filter.MartiansFilterRule,
                    cfg_section, value_req=False)
        elif cfg_section["type"] == "CommunityFilter":
            return self._build_normal_filter_rule(Filter.CommunityFilterRule,
                    cfg_section)
        elif cfg_section["type"] == "NoExportFilter":
            return self._build_normal_filter_rule(Filter.NoExportFilterRule,
                    cfg_section, value_req=False)
        elif cfg_section["type"] == "PeerFilter":
            ConfigValidator.validate_list_type(cfg_section["match"], int,
                    "match", "PeerFilter", strict_list=False)
            return self._build_normal_filter_rule(Filter.PeerFilterRule,
                    cfg_section)
        elif cfg_section["type"] == "OriginFilter":
            ConfigValidator.validate_list_type(cfg_section["match"], int,
                    "match", "OriginFilter", strict_list=False)
            return self._build_normal_filter_rule(Filter.OriginFilterRule,
                    cfg_section)
        else:
            raise Exception("Config: Unknown filter rule %s" %
                    cfg_section["type"])

    def _build_normal_filter_rule(self, class_type, cfg_section,
            value_req=True, has_on_match=True):
        """
            Instantiate a standard filter rule that contains a match field
            and a value to match on.
        """
        match = cfg_section["match"] if "match" in cfg_section else None
        match = self._translate_self_asn(match)

        onmatch = cfg_section["onmatch"] if "onmatch" in cfg_section else None

        if value_req and match is None:
            raise Exception("Config: Filter %s missing match value" %
                    cfg_section["type"])
        elif not value_req and match is not None:
            self.log.warning("Filter %s ignoring unnecessary match attribute",
                    cfg_section["type"])

        if not has_on_match and onmatch is not None:
            self.log.warning("Filter %s ignoring unnecessary onmatch attribute",
                    cfg_section["type"])

        if value_req:
            if has_on_match and onmatch is not None:
                return class_type(match, onmatch=onmatch)
            else:
                return class_type(match)
        else:
            if has_on_match and onmatch is not None:
                return class_type(onmatch=onmatch)
            else:
                return class_type()

    def _build_nested_filter_rule(self, class_type, cfg_section,
            has_on_match=True):
        """
            Instantiate a nested filter rule that contains a nested filter as
            its value.
        """
        match = cfg_section["match"] if "match" in cfg_section else None
        onmatch = cfg_section["onmatch"] if "onmatch" in cfg_section else None

        if match is None:
            raise Exception("Config: Filter %s missing match value" %
                    cfg_section["name"])

        if not has_on_match and onmatch is not None:
            self.log.warning("Filter %s ignoring unnecessary onmatch attribute",
                    cfg_section["type"])

        if has_on_match and onmatch is not None:
            return class_type(self._build_filter_rule(match), onmatch=onmatch)
        else:
            return class_type(self._build_filter_rule(match))

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
            return (self.asn if (isinstance(obj, str) and
                obj.lower() == "self.asn") else obj)
