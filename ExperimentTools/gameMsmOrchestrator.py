import socket
import perfmon_pb2 as perfmsg
import struct
import os
import sys
from collections import OrderedDict
import time
from datetime import datetime
import asyncio
import statistics as stat
from fractions import Fraction
from decimal import Decimal
from decimal import getcontext
import multiprocessing
import concurrent.futures
import csv
import select


def encode_msg_size(size: int) -> bytes:
    return struct.pack("<I", size)


def create_msg(content: bytes) -> bytes:
    size = len(content)
    return encode_msg_size(size) + content


def decode_msg_size(size_bytes: bytes) -> int:
    return struct.unpack("<I", size_bytes)[0]


if __name__ == "__main__":
    latsock = '/home/ubuntu/latency.sock'
    sock4path = '/home/ubuntu/path1.sock'
    sock5path = '/home/ubuntu/path2.sock'

    os.mkfifo(sock4path)
    os.mkfifo(sock5path)

    sock4 = os.open(sock4path, os.O_RDONLY | os.O_NONBLOCK)
    sock5 = os.open(sock5path, os.O_RDONLY | os.O_NONBLOCK)

    poll = select.poll()
    poll.register(sock4, select.POLLIN)
    poll.register(sock5, select.POLLIN)

    msm_sockets = [sock4, sock5]
    parsocks = [latsock]
    # Link measurements to egress nodes
    msmAddrExit = OrderedDict()
    msmAddrExit["55::4"] = ["Tp1ASr2", "100::2", 0.0]
    msmAddrExit["55::5"] = ["Tp1ASr3", "100::3", 0.0]

    clients = {}
    timer = None

    file_handlers = []
    for sock in parsocks:
        fifo = os.open(sock, os.O_WRONLY)
        file_handlers.append(fifo)


    with open('/home/ubuntu/Ovw-Eval-Results/AS34410/msmModule/msmtiming', 'w') as msmtimef:
        writer = csv.writer(msmtimef, delimiter='|')
        writer.writerow(["Measurement start time", "Number of Clients", "Number of measurements", "Duration"])

    while True:
        if timer is None:
            timer = time.monotonic()
        init_time = str(datetime.now())
        print("Initiating measurements for clients added at %s"
              % (str(datetime.now())))
        t1 = time.perf_counter()
        msg = perfmsg.DstMsmMsgs()
        events = poll.poll()

        #for sock in ready_to_read:
        for sock, event in events:
            if sock == sock4:
                msg_size_bytes = os.read(sock, 4)
                msg_size = decode_msg_size(msg_size_bytes)
                msg_recvd = os.read(sock, msg_size)
                # print(f"Length of received message is {len(msg_recvd)}")
                cl_rtts_msg = perfmsg.ClRTTMsgs()
                cl_rtts = cl_rtts_msg.FromString(msg_recvd)
                for cl_rtt in cl_rtts.cl_rtt:
                    cl_addr = cl_rtt.address
                    if cl_addr not in clients:
                        clients[cl_addr] = [(None, None), (None, None)]
                    ertt = cl_rtt.ertt
                    rtt = cl_rtt.rtt
                    clients[cl_addr][0] = (ertt, rtt)

            if sock == sock5:
                msg_size_bytes = os.read(sock, 4)
                msg_size = decode_msg_size(msg_size_bytes)
                msg_recvd = os.read(sock, msg_size)
                # print(f"Length of received message from sock5 is {len(msg_recvd)}")
                cl_rtts_msg = perfmsg.ClRTTMsgs()
                cl_rtts = cl_rtts_msg.FromString(msg_recvd)
                for cl_rtt in cl_rtts.cl_rtt:
                    cl_addr = cl_rtt.address
                    if cl_addr not in clients:
                        clients[cl_addr] = [(None, None), (None, None)]
                    ertt = cl_rtt.ertt
                    rtt = cl_rtt.rtt
                    clients[cl_addr][1] = (ertt, rtt)

        t2 = time.perf_counter()
        t_delta = t2 - t1
        print("Measurement completed in %s seconds  for clients: %s"
              % (t_delta, clients.keys()))

        for client, lat_values in clients.items():
            p1_ertt, p1_rtt = lat_values[0]
            p2_ertt, p2_rtt = lat_values[1]

            if (p1_ertt is not None) and (p2_ertt is not None):
                dstMsm = msg.dstMsm.add()
                dstMsm.DstAddr = client
                msm_for_p1 = dstMsm.node.add()
                msm_for_p1.name = msmAddrExit["55::4"][0]
                msm_for_p1.address = msmAddrExit["55::4"][1]
                msm_for_p1.estDelay = round(p1_ertt, 1)
                msm_for_p2 = dstMsm.node.add()
                msm_for_p2.name = msmAddrExit["55::5"][0]
                msm_for_p2.address = msmAddrExit["55::5"][1]
                msm_for_p2.estDelay = round(p2_ertt, 1)
            
            print(f"Client: {client}  Path 1 Est/Actual Delay: {p1_ertt}/{p1_rtt}ms  Path 2 Est/Actual Delay: {p2_ertt}/{p2_rtt}ms")
    
        if time.monotonic() - timer >= 1.0:
            msg_encoded = msg.SerializeToString()
            if len(msg_encoded) != 0:
                msg = create_msg(msg_encoded)
                for fifo in file_handlers:
                    os.write(fifo, msg)

            with open('/home/ubuntu/Ovw-Eval-Results/AS34410/msmModule/msmtiming', 'a') as f_o:
                row = [init_time, len(clients), 2, t_delta]
                writer = csv.writer(f_o, delimiter='|')
                writer.writerow(row)

            print("Msm module sent latency msms to Overwatch for clients at %s"
                  % (str(datetime.now())))
            timer = None
