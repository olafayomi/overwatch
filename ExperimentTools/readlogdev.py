#!/usr/bin/env python
import os
import sys
import re
from datetime import datetime, timedelta
from dateutil.parser import parse 
import math
import numpy as np
import statistics
import argparse
import pathlib

basepath = '/home/ubuntu/DITG-LOGS/DECODED-LOGS'
txPattern = 'txTime>[0-9]{1,2}\:[0-9]{1,2}\:[0-9]{1,2}\.[0-9]+'
rxPattern = 'rxTime>[0-9]{1,2}\:[0-9]{1,2}\:[0-9]{1,2}\.[0-9]+'

def getTxStamp(line):
    txPattern = 'txTime>[0-9]{1,2}\:[0-9]{1,2}\:[0-9]{1,2}\.[0-9]+'
    txMatch = re.findall(txPattern, line)
    if not txMatch:
        return None
    tx = txMatch[0].split('>')
    txStamp = datetime.strptime(tx[1], "%H:%M:%S.%f")
    return txStamp

def getRxStamp(line):
    rxPattern = 'rxTime>[0-9]{1,2}\:[0-9]{1,2}\:[0-9]{1,2}\.[0-9]+'
    rxMatch = re.findall(rxPattern, line) 
    if not rxMatch:
        return None
    rx = rxMatch[0].split('>')
    rxStamp = datetime.strptime(rx[1], "%H:%M:%S.%f")
    return rxStamp

def rxAll(lines): 
    rxStamps = [] 
    for line in lines:
        rxStamp = getRxStamp(line)
        rxStamps.append(rxStamp)
    return rxStamps

def txAll(lines):
    txStamps = [] 
    for line in lines:
        txStamp = getTxStamp(line)
        txStamps.append(txStamp)
    return txStamps

def CalculateDelay(DITGloglines): 
    min_d, max_d = float('inf'), float('-inf')
    min_id = 0
    max_id = 0
    _delays = []
    for index, line in enumerate(DITGloglines):
        txTimeObj = getTxStamp(line)
        rxTimeObj = getRxStamp(line)

        if txTimeObj and rxTimeObj:
            delta = rxTimeObj - txTimeObj
            deltaMS = delta.total_seconds() * 1000 
            _delays.append(deltaMS)

            if deltaMS  < min_d:
                min_d = deltaMS
                min_id = index

            if deltaMS > max_d:
                max_d = deltaMS
                max_id = index

    return _delays, min_d, max_d, min_id, max_id

def PrintDelay(_delays):
    for delay in _delays:
        print(delay)

def PrintTs(_timestamps):
    for txtimestamp in _timestamps:
        print(txtimestamp.strftime("%H:%M:%S.%f"))

def PrintStats(_max_delay, _min_delay,_max_idx,_min_idx,_delays,_lines):
    print("Max delay is %s ms" %_max_delay)
    print("Max delay was reported at:\n\t %s\n" %_lines[_max_idx])
    print("Min delay is %s" %_min_delay)
    print("Min delay was reported at:\n\t %s\n" %_lines[_min_idx])
    print("Mean delay is %s" %np.mean(_delays))
    print("Standard deviation is %s" %np.std(_delays, dtype= np.float))
    print("95th percentile of delay is %s" %np.percentile(_delays, 95))
    print("98th percentile of delay is %s" %np.percentile(_delays, 98))
    print("99th percentile of delay is %s" %np.percentile(_delays, 99))
    print("50th percentile of delay is %s" %np.percentile(_delays, 50))
    print("There are %s packets in the log" %len(_lines))
    print("\n\n")

def duration_stats(_lines, duration):
    run = True
    ind = 0
    while run:
        line = _lines[ind]
        _del, _min_d, _max_d, _min_id, _max_id = CalculateDelay(_lines)
        duration_tx = txAll(_lines)
        duration_rx = rxAll(_lines)
        txTime = getTxStamp(line)
        abs_end_ts = txTime + timedelta(seconds=duration)
        duration_end_ts = min(duration_rx, key=lambda d: abs(d - abs_end_ts))
        duration_end_id = duration_rx.index(duration_end_ts)
        pkts = _lines[ind:duration_end_id+1]
        log_delay, logmin_delay, logmax_delay, logmin_id, logmax_id = \
            CalculateDelay(pkts)
        sample = _del[ind:duration_end_id+1]
        print("Delay statistics observed between %s and %s:"
                %(txTime.strftime("%H:%M:%S.%f"),
                    duration_end_ts.strftime("%H:%M:%S.%f")))
        print("   Number of packets in interval: %s" %len(sample))
        #print("   Number of packets in log_delay is %s" %len(log_delay))
        #print("   Min Delay (logmin_delay): %s" %logmin_delay)
        print("   Minimum delay: %s ms" %min(sample))
        #print("   Max Delay (logmax_delay): %s" %logmax_delay) 
        print("   Maximum delay: %s ms" %max(sample))
        print("   Mean delay: %s ms"  %np.mean(sample))
        print("   Standard deviation of delay: %s ms"
                %np.std(sample, dtype=np.float))
        sem = np.std(sample, dtype=np.float) / np.sqrt(np.size(sample))
        print("   Standard error of delay: %s" %sem)
        print("\n")
        #PrintStats(logmax_delay, logmin_delay, logmax_id, logmin_id,log_delay, pkts)
        ind = duration_end_id + 1
        
        if ind >= len(duration_rx): 
            run = False


if __name__ == "__main__":
    argParser = argparse.ArgumentParser(
            description='Extract and print delay values from D-ITG text logs',
            usage='%(prog)s [--logfile DITG_log_file --start-time  start_time --end-time End-time --range number_of_packets]')
    argParser.add_argument('--logfile', dest='ditglog', help='Decode DITG log file', default=None)
    argParser.add_argument('--delay', dest='delay', action='store_true')
    argParser.add_argument('--no-delay', dest='delay', action='store_false')
    argParser.add_argument('--timestamp', dest='timestamp', action='store_true')
    argParser.add_argument('--no-timestamp', dest='timestamp',
                           action='store_false')
    argParser.add_argument('--stat', dest='stats', action='store_true')
    argParser.add_argument('--no-stat', dest='stats', help='Does not print stat',
                           action='store_false') 
    argParser.add_argument('--start-time', dest='start_time', help='Transmitted timestamp of first packet',
                           default=None)
    argParser.add_argument('--opt-duration', dest='duration', help='Optimisation window to interrogate in seconds',
                            type=int, default=None)
    group = argParser.add_mutually_exclusive_group()
    group.add_argument('--end-time', dest='endtime', help='Received Timestamp of last packet',
                           default=None) 
    group.add_argument('--range', dest='num_of_pkts', help='Number of packets to print', type=int,
                           default=None)
    
    argParser.set_defaults(stats=False, delay=False, timestamp=False) 
    args = argParser.parse_args() 
    
    if args.ditglog is None:
        print("DITG log file not provided!!!\n")
        sys.exit(-1)

    filepath = basepath+'/'+args.ditglog
    filepath_obj = pathlib.Path(filepath) 
    
    if filepath_obj.is_file() is False:
        print("%s does not exist!!!" %filepath_obj)
        sys.exit(-1) 

    with open(filepath) as fp:
        lines = fp.readlines() 
        min_delay, max_delay = float('inf'), float('-inf')
        min_idx = 0 
        max_idx = 0
        delays = []
        txTimeStamps = txAll(lines)
        rxTimeStamps = rxAll(lines)
        run = True
        ind = 0
        if len(txTimeStamps) != len(rxTimeStamps):
            print("List of transmitted not equal to received")
            sys.exit(1)

        delays, min_delay, max_delay, min_idx, max_idx = CalculateDelay(lines)

        if args.delay and not args.start_time:
            PrintDelay(delays)

        if args.timestamp and not args.start_time:
            PrintTs(txTimeStamps)

        if args.stats and not args.start_time:
            PrintStats(max_delay,min_delay,max_idx,min_idx,delays,lines)
    
        if args.duration and not args.start_time:
            duration_stats(lines, args.duration)         

        if args.start_time:
            start_time = datetime.strptime(args.start_time, "%H:%M:%S.%f")
            start_idx = txTimeStamps.index(start_time) 

            if start_time not in txTimeStamps:
                print("Timestamp provided not in log")
                sys.exit(1)

            if not args.endtime and not args.num_of_pkts:
                print("Rx timestamps or number of packets to check not provided!!!")
                sys.exit(1)

            if args.endtime: 
                end_time = datetime.strptime(args.endtime, "%H:%M:%S.%f")
                if end_time not in rxTimeStamps:
                    print("End timestamp not present in log")
                    sys.exit(1)

                end_idx = rxTimeStamps.index(end_time)
                if start_idx >= end_idx: 
                    print("End timestamp cannot be earlier than start timestamp!!!")
                    sys.exit(1)
                
                _lines  = lines[start_idx:end_idx+1]
                _del, _min_d, _max_d, _min_id, _max_id = CalculateDelay(_lines)
                _txTimeSt = txAll(_lines)
                _rxTimeSt = rxAll(_lines)

                if args.stats:
                    print("Stats for packets between %s and %s" %(start_time.strftime("%H:%M:%S.%f"), end_time.strftime("%H:%M:%S.%f")))
                    PrintStats(_max_d,_min_d,_max_id,_min_id,_del,_lines)

                if args.delay:
                    PrintDelay(_del)

                if args.timestamp:
                    PrintTs(_txTimeSt)
            
                if args.duration: 
                    duration_stats(_lines, args.duration)

            if args.num_of_pkts:
                num_of_pkts = args.num_of_pkts + start_idx
                if num_of_pkts > len(lines):
                    print("Range of packets can not be greater than total of number of packets!!!")
                    sys.exit(1)

                _lines = lines[start_idx:num_of_pkts]
                _del, _min_d, _max_d, _min_id, _max_id = CalculateDelay(_lines)
                _txTimeSt = txAll(_lines)
                _rxTimeSt = rxAll(_lines)
                end_time = rxTimeStamps[num_of_pkts]

                if args.stats:
                    print("Stats for packets between %s and %s" %(start_time.strftime("%H:%M:%S.%f"), end_time.strftime("%H:%M:%S.%f")))
                    PrintStats(_max_d,_min_d,_max_id,_min_id,_del,_lines)

                if args.delay:
                    PrintDelay(_del)

                if args.timestamp:
                    PrintTs(_txTimeSt)
              
                if args.duration:
                    duration_stats(_lines, args.duration)

#with open(filepath) as fp:
#    lines = fp.readlines()
#    min_delay, max_delay = float('inf'), float('-inf')
#    min_idx = 0 
#    max_idx = 0
#    delays = []
#    txTimeStamps = txAll(lines)
#    rxTimeStamps = rxAll(lines)
#    run = True
#    ind = 0
#    if len(txTimeStamps) != len(rxTimeStamps):
#        print("List of transmitted not equal to received")
#        sys.exit(1)
#
#    delays, min_delay, max_delay, min_idx, max_idx = CalculateDelay(lines)
#
#    while run:
#        line = lines[ind]
#        txTime = getTxStamp(line) 
#        sampleTs = txTime + timedelta(seconds=180)
#            
#        closestTs = min(rxTimeStamps, key=lambda d:  abs(d - sampleTs))
#        idxclosest = rxTimeStamps.index(closestTs)
#        pkts = lines[ind:idxclosest+1]
#        log_delay, logmin_delay, logmax_delay, logmin_id, logmax_id = \
#            CalculateDelay(pkts)
#
#        sample_delay = delays[ind:idxclosest+1]
#        #print("Delay statistics observed between %s and %s:"
#        #        %(txTime.strftime("%H:%M:%S.%f"),
#        #            closestTs.strftime("%H:%M:%S.%f")))
#        #print("   Number of packets in interval: %s" %len(sample_delay))
#        #print("   Minimum delay: %s ms" %min(sample_delay))
#        #print("   Maximum delay: %s ms" %max(sample_delay))
#        #print("   Mean delay: %s ms"  %np.mean(sample_delay))
#        #print("   Standard deviation of delay: %s ms"
#        #        %np.std(sample_delay, dtype=np.float))
#        sem = np.std(sample_delay, dtype=np.float) / np.sqrt(np.size(sample_delay))
#        #print("   Standard error of delay: %s" %sem)
#        #print("\n")
#
#        
#    
#        
#        
#        #print("Number of packets seen in 90 seconds timeframe is %s" %len(opt_window))
#        #print("packet on line %s is %s" %(idxclosest, lines[idxclosest]))
#        #print("Packet on line %s is %s" %(idxclosest+1, lines[idxclosest+1]))
#        #print("90 seconds from %s is %s" %(txTime.strftime("%H:%M:%S.%f"),sampleTs.strftime("%H:%M:%S.%f")))
#        #print("Closest timestamp to %s is %s" %(sampleTs.strftime("%H:%M:%S.%f"), closestTs.strftime("%H:%M:%S.%f")))
#        #print("Start index is %s and End index is %s" %(ind, idxclosest))
#        #print("\n")
#        ind = idxclosest + 1
#        if ind >= len(rxTimeStamps): 
#            run = False
#
#    #print("Max delay is %s ms" %max_delay)
#    #print("Max delay was reported at:\n\t %s\n" %lines[max_idx])
#    #print("Min delay is %s" %min_delay)
#    #print("Min delay was reported at:\n\t %s\n" %lines[min_idx])
#    #print("Mean delay is %s" %statistics.mean(delays))
#    #print("Mean delay is %s" %np.mean(delays))
#
#    #print("Std Deviation is %s" %statistics.stdev(delays))
#    #print("Numpy std deviation is %s" %np.std(delays, dtype= np.float))
#
#
#    #print("95th percentile of delay is %s" %np.percentile(delays, 95))
#    #print("98th percentile of delay is %s" %np.percentile(delays, 98))
#    #print("99th percentile of delay is %s" %np.percentile(delays, 99))
#    #print("50th percentile of delay is %s" %np.percentile(delays, 50))
#    
#    #print("There are %s lines in the file" %len(lines))
#    #for txtimestamp in txTimeStamps:
#    #    print(txtimestamp.strftime("%H:%M:%S.%f"))
#    for delay in delays:
#        print(delay)
#        
#
#        #print("Transmission time: %s" %tx)
#        #if not line:
#    
#    #    break
