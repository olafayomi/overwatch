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

import errno
import json
import select
import socket
import logging

def ControlConnection(outgoing_queue, command_queue):
    log = logging.getLogger("ControlCon")

    command_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    command_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    command_sock.bind(("localhost", 9877))
    command_sock.listen(1)

    # XXX for now, we will just have a single control connection
    while True:
        conn, _ = command_sock.accept()

        # run forever, or at least until the parent process is killed
        while True:
            # we'll always expect to want to read any data that is available
            read_fds = [conn]

            # add to the set if there is any data we need to write
            if not outgoing_queue.empty():
                write_fds = [conn]
            else:
                write_fds = []

            # poll to check if we have data in our queue to write
            timeout = 0.1

            try:
                active = select.select(read_fds, write_fds, [], timeout)
            except select.error as e:
                if e[0] == errno.EINTR:
                    continue
                else:
                    log.critical("Error during select: %s", e[1])
                    return

            # TODO move some of the message parsing etc over to here?
            if conn in active[0]:
                # read a control message from the socket
                raw = conn.recv(1024)
                if len(raw) == 0:
                    log.info("eof")
                    break

                try:
                    message = json.loads(str(raw, "utf-8"))
                except ValueError:
                    log.error("Received invalid JSON message")
                    continue

                # put it on the command queue to be processed
                log.debug(message)
                command_queue.put(("control", message))

            if conn in active[1]:
                # get a message from the queue
                message = outgoing_queue.get()
                # write it to the control socket
                conn.send(json.dumps(message))

        conn.close()
    command_sock.close()
