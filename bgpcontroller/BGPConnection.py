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
# @Author : Brendon Jones (Original Disaggregate Router)
# @Author : Dimeji Fayomi

import errno
import json
import os
import select
import sys
import logging


def BGPConnection(outgoing_queue, command_queue):
    # remove buffering for stdin so that it works properly with select(),
    # otherwise if we don't read all the data available then it will block
    # forever...

    # Python 3.5 has a bug where you can't read unbuffered IO anymore. This
    # restriction doesn't apply to bytes IO so we can use RB instead.
    # https://mail.python.org/pipermail/python-dev/2008-December/084439.html
    sys.stdin = os.fdopen(sys.stdin.fileno(), 'rb', 0)

    log = logging.getLogger("BGPCon")

    # run forever, or at least until the parent process is killed
    while True:
        # we'll always expect to want to read any data that is available
        read_fds = [sys.stdin.fileno()]

        # add stdout to the set if there is any data we need to write
        if not outgoing_queue.empty():
            write_fds = [sys.stdout.fileno()]
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
                log.critical(
                        "Error during select: %s. Stopping connection", e[1])
                return

        # TODO move some of the message parsing etc over to here?
        if sys.stdin.fileno() in active[0]:
            # read a message from exabgp over stdin
            line = str(sys.stdin.readline(), "utf-8")

            if line is not None and len(line) != 0:
                try:
                    message = json.loads(line)
                    # put it on the command queue to be processed
                    command_queue.put(("bgp", message))
                except Exception:
                    log.error("Invalid json read from standard in")
                    continue

        if sys.stdout.fileno() in active[1]:
            # get a message from the queue
            message = outgoing_queue.get()
            # everything in this queue is just raw bytes, not protobuf messages
            #message = message.decode("utf-8")
            #log.debug("================ WRITING ================")
            #log.debug(message)
            # write it to exabgp over stdout
            print(message)
            sys.stdout.flush()
