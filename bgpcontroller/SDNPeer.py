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

from Peer import Peer
from PolicyObject import ACCEPT
from RouteEntry import DEFAULT_LOCAL_PREF
from Routing import BrendonRouting

class SDNPeer(Peer):
    def __init__(self, name, asn, address, control_queue,
            internal_command_queue,
            preference=DEFAULT_LOCAL_PREF,
            default_import=ACCEPT,
            default_export=ACCEPT):

        super(SDNPeer, self).__init__(name, asn, address, control_queue,
                internal_command_queue, preference, default_import,
                default_export)

        self.log = logging.getLogger("BGPPeer")
        self.routing = BrendonRouting(self.name)

        #self.actions.update({
        #    "update": self._process_table_update,
        #})

    def _do_announce(self, prefix, route):
        self.log.debug("SDNPEER ANNOUNCE %s %s" % (prefix, route))

    def _do_withdraw(self, prefix, route):
        self.log.debug("SDNPEER WITHDRAW %s %s" % (prefix, route))
