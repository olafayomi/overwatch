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
from datetime import datetime
import perfmon_pb2 as perfmsg
import struct
import os


def encode_msg_size(size: int) -> bytes:
    return struct.pack("<I", size)


def create_msg(content: bytes) -> bytes:
    size = len(content)
    return encode_msg_size(size) + content


def decode_msg_size(size_bytes: bytes) -> int:
    return struct.unpack("<I", size_bytes)[0]


class Path1Protocol:
    def __init__(self, pathsock):
        self.alpha = 0.125
        self.clients = {}
        self.srcAddr = "55::4"
        self.send_ping_task = None
        self.send_update_task = None
        self.pathsock = pathsock

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        message = data.decode()
        msg_list = message.split(",")
        client_addr = addr[0]
        # s_time = time.monotonic()
        if len(msg_list) == 3:
            self.clients[client_addr] = [(None, None), 0]
            self.send_ping_task = asyncio.create_task(self.send_ping(addr))
            self.send_update_task = asyncio.create_task(self.send_update())
        else:
            # r_time = time.monotonic()
            r_time = asyncio.get_running_loop().time()
            pkt_s_time = float(msg_list[4])
            print(f"On {self.srcAddr} for {client_addr} received: {r_time}, sent: {pkt_s_time}")
            rtt = (r_time - pkt_s_time) * 1000
            ertt, rtt_prev = self.clients[client_addr][0]
            if ertt is None:
                ertt = rtt
                self.clients[client_addr][0] = (ertt, rtt)
            else:
                ertt = ((1 - self.alpha) * ertt) + (self.alpha * rtt)
                self.clients[client_addr][0] = (ertt, rtt)
        # ping = f"Ping,{client_addr},{self.srcAddr},{self.message_counter},{s_time}"
        # self.transport.sendto(ping.encode(), addr)
        # self.message_counter += 1
        print(f"{str(datetime.now())}: Printing clients here for {self.srcAddr}: {self.clients}")

    async def send_ping(self, addr):
        event = asyncio.Event()
        while True:
            # s_time = time.monotonic()
            s_time = asyncio.get_running_loop().time()
            ping = f"Ping,{addr[0]},{self.srcAddr},{self.clients[addr[0]][1]},{s_time}"
            self.transport.sendto(ping.encode(), addr)
            self.clients[addr[0]][1] += 1
            await asyncio.sleep(1)
        event.clear()

    async def send_update(self):
        event = asyncio.Event()
        while True:
            rtt_msgs = perfmsg.ClRTTMsgs()
            for client_addr, vals in self.clients.items():
                ertt, rtt = vals[0]
                if ertt is not None:
                    cl = rtt_msgs.cl_rtt.add()
                    cl.address = client_addr
                    cl.ertt = ertt
                    cl.rtt = rtt
            msg_encoded = rtt_msgs.SerializeToString()
            msg = create_msg(msg_encoded)
            os.write(self.pathsock, msg)
            await asyncio.sleep(1)
        event.clear()


if __name__ == '__main__':

    loop = asyncio.get_event_loop()
    print("Starting the path 1 server")
    sockfile = '/home/ubuntu/path1.sock'
    path1sock = os.open(sockfile, os.O_WRONLY)
    # listen = loop.create_datagram_endpoint(
    #    lambda: Path1Protocol(path1sock),
    #    local_addr=('55::4', 12346))
    # transport, protocol = loop.run_until_complete(listen)

    try:
        transport, protocol = loop.run_until_complete(loop.create_datagram_endpoint(
            lambda: Path1Protocol(path1sock),
            local_addr=('55::4', 12346),
            reuse_address=True))
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        print("Game server is shutting down.")
    finally:
        if protocol.send_ping_task is not None:
            protocol.send_ping_task.cancel()
        if protocol.send_update_task is not None:
            protocol.send_update_task.cancel()
        transport.close()
        loop.run_until_complete(transport.wait_closed())
        loop.close()
