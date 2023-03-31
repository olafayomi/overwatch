import asyncio
import sys
import time
from multiprocessing import cpu_count
from queue import Queue
from threading import Thread
from typing import List
from gufo.ping import Ping
import perfmon_pb2 as perfmsg
import struct
import os
import sys
from collections import OrderedDict
import statistics as stat
from fractions import Fraction
from decimal import Decimal
from decimal import getcontext
import csv
from datetime import datetime

# Maximal amounts of CPU used
MAX_CPU = 8
# Number of worker tasks within every thread
N_TASKS = 50


def encode_msg_size(size: int) -> bytes:
    return struct.pack("<I", size)


def create_msg(content: bytes) -> bytes:
    size = len(content)
    return encode_msg_size(size) + content


def worker(data: List[str], srcAddr: str,  result_queue: Queue) -> None:
    """
    Thread worker, started within every thread.

    Args:
        data: List of IP addresses to ping.
        result_queue: Queue to push results back.
    """
    # Create separate event loop per each thread
    loop = asyncio.new_event_loop()
    # And set it as default
    asyncio.set_event_loop(loop)
    # Run asynchronous worker within every thread
    loop.run_until_complete(async_worker(data, srcAddr, result_queue))
    # Cleanup
    loop.close()


async def async_worker(data: List[str], srcAddr: str, result_queue: Queue) -> None:
    """
    Asynchronous worker. Started for each thread.

    Args:
        data: List of IP addresses to ping.
        result_queue: Queue to push results back.
    """

    async def task(addr_queue: asyncio.Queue, done: asyncio.Event) -> None:
        """
        Worker task. Up to N_TASKS spawn per thread.

        Args:
            addr_queue: Queue to pull addresses to ping. Stops when
                pulled None.
            done: Event to set when processing complete.
        """
        while True:
            # Pull address or None
            addr = await addr_queue.get()
            if not addr:
                # Stop on None
                break
            # Send ping and await the result
            #rtt = await ping.ping(addr)
            ping = Ping(src_addr=srcAddr)
            #rtts = []
            #n = 0
            #async for rtt in ping.iter_rtt(addr, interval=1.0, count=3):
            #    if rtt is None:
            #        print(f"Request timeout for icmp_seq {n}")
            #    else:
            #        rtts.append(rtt)
            #    n += 1

            # We just do a single RTT now
            rtt = await ping.ping(addr)
            if rtt is None:
                print(f"Request timeout for icmp request to {addr}")

            # Push measured result to a main thread
            result_queue.put((addr, rtt))
        # Report worker is stopped.
        done.set()

    # Create ping socket per each thread
    ping = Ping()
    # Address queue
    addr_queue = asyncio.Queue(maxsize=2 * N_TASKS)
    # List of events to check tasks is finished
    finished = []
    # Effective tasks is limited by:
    # * Available addresses
    # * Imposed limit
    n_tasks = min(len(data), N_TASKS)
    # Create and run tasks
    loop = asyncio.get_running_loop()
    for _ in range(n_tasks):
        cond = asyncio.Event()
        loop.create_task(task(addr_queue, cond))
        finished.append(cond)
    # Push data to address queue,
    # may be blocked if we'd pushed too many
    for x in data:
        await addr_queue.put(x)
    # Push stopping None for each task
    for _ in range(n_tasks):
        await addr_queue.put(None)
    # Wait for each task to complete
    for cond in finished:
        await cond.wait()


def main() -> None:
    latsock = '/home/ubuntu/latency.sock'
    parsocks = [latsock]
    # Link measurements to egress nodes
    msmAddrExit = OrderedDict()
    msmAddrExit["55::4"] = ["Tp1ASr2", "100::2", 0.0]
    msmAddrExit["55::5"] = ["Tp1ASr3", "100::3", 0.0]

    clients = {}
    alpha = 0.125
    file_handlers = []
    for sock in parsocks:
        fifo = os.open(sock, os.O_WRONLY)
        file_handlers.append(fifo)

    while not os.path.exists('/home/ubuntu/clients.txt'):
        time.sleep(1)
        print(f"File does not exist!!!")

    while os.stat('/home/ubuntu/clients.txt').st_size == 0:
        time.sleep(1)
        print(f"File is empty!!!!")

    with open('/home/ubuntu/Ovw-Eval-Results/AS34410/msmModule/msmtiming', 'w') as msmtimef:
        writer = csv.writer(msmtimef, delimiter='|')
        writer.writerow(["Measurement start time", "Number of Clients", "Number of measurements", "Duration"])

    while True:
        time.sleep(0.005)
        print("Client added at %s," % (str(datetime.now())))
        getcontext().prec = 3
        with open('/home/ubuntu/clients.txt', 'r') as f:
            lines = f.readlines()
            low = Decimal(54.0)
            high = Decimal(60.0)
            for line in lines:
                low += Decimal(0.1)
                high += Decimal(0.1)
                #clients.append(line.rstrip('\n'))
                #clients[line.rstrip('\n')] = [float(high), float(low)]
                if line.rstrip('\n') not in clients:
                    clients[line.rstrip('\n')] = [(None, None), (None, None)]

        n_data = len(clients)
        client_l = [key for key in clients]
        print("Number of clients: %s" % n_data)
        n_workers = min(MAX_CPU, cpu_count(), n_data)
        result_queue_1 = Queue()
        workers_1 = [
            Thread(
                target=worker,
                args=(client_l[n::n_workers], "55::4", result_queue_1),
                name=f"worker1-{n}",
            )
            for n in range(n_workers)
        ]

        result_queue_2 = Queue()
        workers_2 = [
            Thread(
                target=worker,
                args=(client_l[n::n_workers], "55::5", result_queue_2),
                name=f"worker1-{n}",
            )
            for n in range(n_workers)
        ]

        workers = workers_1 + workers_2
        init_time = str(datetime.now())
        print("Initiating measurements for clients added at %s"
              % (str(datetime.now())))
        t1 = time.perf_counter()

        for w in workers:
            w.start()

        success = 0
        p1 = {}
        p2 = {}
        for _ in range(n_data):
            addr1, rtt1 = result_queue_1.get()
            addr2, rtt2 = result_queue_2.get()
            if rtt1 is None:
                print(f"{addr1}: timed out")
                rtt1 = 1
            #else:
                #print(f"rtts is type {type(rtts)}")
                #ms_rtt = []
            rtt = rtt1 * 1000.0
            ertt, rtt_prev = clients[addr1][0]
            if ertt is None:
                p1[addr1] = [(rtt, rtt)]
                clients[addr1][0] = (rtt, rtt)
            else:
                #print(f"Address: {addr1} Previous RTT estimate for P1: {ertt}ms")
                ertt = alpha * ertt  + (1 - alpha) * rtt
                #print(f"Address: {addr1} Current RTT estimate for P1 to be sent: {ertt}ms")
                p1[addr1] = [(ertt, rtt)]
                clients[addr1][0] = (ertt, rtt)
                    

                #for rtt in rtts1:
                #    ms_rtt.append(rtt * 1000.0)
                #p1[addr1] = ms_rtt
            print(f"{addr1}: {p1[addr1]}")

            if rtt2 is None:
                print(f"{addr2}: timed out")
                rtt2 = 1
            #else:
            rtt = rtt2 * 1000.0
            ertt, rtt_prev = clients[addr2][1]
            if ertt is None:
                p2[addr2] = [(rtt, rtt)]
                clients[addr2][1] = (rtt, rtt)
            else:
                #print(f"Address: {addr2} Previous RTT estimate for P2: {ertt}ms")
                ertt = alpha * ertt + (1 - alpha) * rtt
                #print(f"Address: {addr2} Current RTT estimate for P2 to be sent: {ertt}ms")
                p2[addr2] = [(ertt, rtt)]
                clients[addr2][1] = (ertt, rtt)
                #ms_rtt = []
                #for rtt in rtts2:
                #    ms_rtt.append(rtt * 1000.0)
                #p2[addr2] = ms_rtt
            print(f"{addr2}: {p2[addr2]}")
        t2 = time.perf_counter()
        t_delta = t2 - t1
        print("Measurement completed in %s seconds  for clients: %s"
              % (t_delta, client_l))
        msg = perfmsg.DstMsmMsgs()
        for client, lat_values in clients.items():
            dstMsm = msg.dstMsm.add()
            dstMsm.DstAddr = client
            msm_for_p1 = dstMsm.node.add()
            msm_for_p1.name = msmAddrExit["55::4"][0]
            msm_for_p1.address = msmAddrExit["55::4"][1]
            p1_ertt, p1_rtt = p1[client][0]
            msm_for_p1.delay = round(p1_ertt, 1)
            msm_for_p2 = dstMsm.node.add()
            msm_for_p2.name = msmAddrExit["55::5"][0]
            msm_for_p2.address = msmAddrExit["55::5"][1]
            p2_ertt, p2_rtt = p2[client][0]
            msm_for_p2.delay = round(p2_ertt, 1)
            print(f"Client: {client}  Path 1 Delay: {round(p1_ertt, 1)}ms  Path 2 Delay: {round(p2_ertt, 1)}ms")

        msg_encoded = msg.SerializeToString()
        msg = create_msg(msg_encoded)
        
        for fifo in file_handlers:
            os.write(fifo, msg)
        t3 =  time.perf_counter()
        t_send = t3 - t2
        print("Sending message took %s seconds" % t_send)
        print("Msm module sent latency msms to Overwatch for clients at %s"
              % (str(datetime.now())))

        with open('/home/ubuntu/Ovw-Eval-Results/AS34410/msmModule/msmtiming', 'a') as f_o:
            row = [init_time, len(clients), 3, t_delta]
            writer = csv.writer(f_o, delimiter='|')
            writer.writerow(row)

        #print("Msm module sent latency msms to Overwatch for clients at %s"
        #      % (str(datetime.now())))

        for w in workers:
            w.join()

        # Sleep for 10 seconds and repeat all over again
        time.sleep(10)
        #if t_delta < 60:
        #    duration = 60 - t_delta
        #    print("Proceeding to sleep for %s seconds" % duration)
        #    time.sleep(duration)


if __name__ == "__main__":
    main()
