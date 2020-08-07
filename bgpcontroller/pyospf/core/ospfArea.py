#!/usr/bin/env python
# -*- coding:utf-8 -*-

import traceback
from collections import defaultdict
import sys
from pyospf.core.interfaceStateMachine import ISM
from pyospf.utils.timer import Timer

HOLD_TIMER = 10

class OspfArea(object):

    transit_capability = False            # unused
    external_routing_capability = False   # unused
    stub_def_cost = 0                     # unused

    def __init__(self, oi, topo_queue):
        self.router_lsa = dict()
        self.network_lsa = dict()
        self.summary_lsa = dict()
        self.summary_asbr_lsa = dict()
        self.opaque9_lsa = dict()
        self.opaque10_lsa = dict()
        self.topo_queue = topo_queue
        self.holdTimer = None

        self.oi = oi
        self.area_id = oi.config['area']

        #one probe has only one interface connect to one area, so there is only one ism in area.
        self.interface = ISM(self)

    def int_to_ip(self, ip):
        a = ip >> 24
        b = (ip >> 16) & 0x00ff
        c = (ip >> 8) & 0x0000ff
        d = ip & 0xff
        return "%d.%d.%d.%d" % (a, b, c, d)

    def topo_change(self):
        """
            Indicate that a topology change has occured. This method will advertise
            the topology change if no updates occur within the hold timer period. If
            an another topo change is signaled the timer is reset.
        """
        # Check if the hold timer needs to be re-created
        if self.holdTimer is None or self.holdTimer.stopFlag == True:
            # TODO: MODIFY TO USE LOG
            print("Hold timer is stopped, initiating ....", file=sys.stderr)
            sys.stderr.flush()
            self.holdTimer = Timer(HOLD_TIMER, action=self._compute_change, once=True)
            self.holdTimer.start()
        else:
            # TODO: MODIFY TO USE LOG
            print("Hold timer is running, reseting ...", file=sys.stderr)
            sys.stderr.flush()
            self.holdTimer.reset()

    def _compute_change(self):
        """
            From the link state database build up the topology of the network
            as a dictionary of router IDs and link addresses with costs.
        """

        # TODO: MODIFY TO USE LOG
        print("COMPUTING CHANGE", file=sys.stderr)
        sys.stderr.flush()
        try:
            topo = {}
            assoc = {}

            # Final data to advertise as our new topology, links in the format,
            #RID1 to RID2 with cost using addr RID2 interface
            links = defaultdict(list)

            # XXX
            #    As per the RFC the data field of the LS entry in the LS-database
            #    will hold the routers interface IP.
            #
            #    The ID can have one of the following, depending on the link type:
            #        Point-to-Point = neighbour RID
            #        Transit (default) = desginated router interface addr
            #        Link to stub = IP network number
            #        Virtual Link = neighbour router ID
            # XXX

            for lsa in self.router_lsa:
                router = self.router_lsa[lsa]
                lsid = self.int_to_ip(router["H"]["LSID"])
                if not lsid in topo:
                    topo[lsid] = {}

                # TODO: MODIFY TO USE LOG
                #print("LSID", lsid, file=sys.stderr)
                rt = topo[lsid]
                for link_num in router["V"]["LINKS"]:
                    link = router["V"]["LINKS"][link_num]
                    id = self.int_to_ip(link["ID"])
                    data = self.int_to_ip(link["DATA"])
                    cost = link["METRICS"][0]

                    # TODO: MODIFY TO USE LOG
                    #print("\tLink (num, id, data, cost)", link_num, id, data, cost,
                    #    file=sys.stderr)

                    if not id in rt:
                        rt[data] = {}

                    if not id == data:
                        rt[data]["ip"] = id
                    else:
                        rt[data]["ip"] = None
                    rt[data]["cost"] = cost

                    # Add the association of a interface to its router ID
                    assoc[data] = lsid

            # TODO: MODIFY TO USE LOG
            #print("ASSOC", assoc, file=sys.stderr)
            #sys.stderr.flush()

            # Iterate a second time to generate the final advertisment of the topo and fix the
            # designated router links
            for rid in topo:
                r = topo[rid]
                for ip in r:
                    is_empty = False
                    if r[ip]["ip"] is None:
                        r[ip]["ip"] = self._find_link_peer_address(topo, ip)

                        # Flag the link as invalid and empty (most likely this is our probe
                        # connection or its not part of the OSPF mesh)
                        if r[ip]["ip"] is None:
                            is_empty = True

                    if not is_empty:
                        # If the other end IP can't be associated with a RID skip the IP
                        # A router may have lost all connections or a segment is not avaialble
                        # in our network
                        if r[ip]["ip"] not in assoc:
                            continue

                        # If the association is not invalid add the link information
                        to_rid = assoc[r[ip]["ip"]]
                        if to_rid:
                            links[rid].append((to_rid, r[ip]["ip"], r[ip]["cost"]))

            # TODO: MODIFY TO USE LOG
            #print ("LINK", links, file=sys.stderr)
            #sys.stderr.flush()

            # Send the new topology information
            self.topo_queue.put(
                ("build_topology", links)
            )
        except Exception:
            # TODO: MODIFY TO USE LOG MODULE
            #print("LSA DUMP --- PASS EXCEPTION ---", file=sys.stderr)
            #for lsa in self.router_lsa:
            #    router = self.router_lsa[lsa]
            #    lsid = self.int_to_ip(router["H"]["LSID"])
            #    print("LSID", lsid, file=sys.stderr)
            #    rt = topo[lsid]
            #    for link_num in router["V"]["LINKS"]:
            #        link = router["V"]["LINKS"][link_num]
            #        id = self.int_to_ip(link["ID"])
            #        data = self.int_to_ip(link["DATA"])
            #        cost = link["METRICS"][0]
            #        print("\tLink (num, id, data, cost)", link_num, id, data, cost,
            #            file=sys.stderr)
            #sys.stderr.flush()
            #traceback.print_exc(file=sys.stderr)
            pass

    def _find_link_peer_address(self, topo, target_ip):
        """
            Iterate through an already defined topology object for an adequate
            other end address. Addresses are saved in the topo object as two
            IPs of the link, a local link and a other neighbour address.

            Return either the correct IP addresses for the target IP or null if
            no adequate address could be found with the info we have avaialble
        """
        for rid in topo:
            r = topo[rid]
            for ip in r:
                if r[ip]["ip"] is not None:
                    if ip == target_ip:
                        return r[ip]["ip"]
                    elif r[ip]["ip"] == target_ip:
                        return ip
        return None
