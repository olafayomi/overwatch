#!/usr/bin/env python
# Copyright (c) 2023, WAND Network Research Group
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


import asyncio
import time


class EchoServerProtocol:
    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        message = data.decode()
        receive_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        port = addr[1]
        # print(f"Received {message} at {receive_time} from port {port}")
        response = f"Received {message} at {receive_time}".encode()
        self.transport.sendto(response, addr)


if __name__ == '__main__':

    loop = asyncio.get_event_loop()
    print("Starting the game server")
    listen = loop.create_datagram_endpoint(
            EchoServerProtocol, local_addr=('55::1', 12345))
    transport, protocol = loop.run_until_complete(listen)

    try:
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        print("Game server is shutting down.")
    finally:
        transport.close()
        loop.close()
