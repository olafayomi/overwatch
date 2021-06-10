#!/usr/bin/env python
import os
import sys
import argparse
import pathlib
import csv
import glob
import fnmatch
import re 
from datetime import datetime, timedelta


basepath = '/home/ubuntu/DITG-LOGS/DECODED-LOGS'
txPattern = 'txTime>[0-9]{1,2}\:[0-9]{1,2}\:[0-9]{1,2}\.[0-9]+'
rxPattern = 'rxTime>[0-9]{1,2}\:[0-9]{1,2}\:[0-9]{1,2}\.[0-9]+'
csv_dir = '/home/ubuntu/CSV-DELAYS/'
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


if __name__ == "__main__":
    argParser = argparse.ArgumentParser(
            description='Write delay values from Decoded DITG logs to csv file',
            usage='%(prog)s [--date 2021064 --runs 20]')
    argParser.add_argument('--date', dest='date_str',
                           help='Date string to search for D-ITG log filenames',
                           default=None)
    argParser.add_argument('--runs', dest='runs',
                           help='Number of experiments', type=int,
                           default=None)
    argParser.add_argument('--H1', dest='h1_pfx',
                           help='String pattern to append to date to list AS6H1 D-ITG log filenames',
                           default='AS6H1-RECV')
    argParser.add_argument('--H2', dest='h2_pfx',
                           help='String pattern to append to date to list AS6H2 D-ITG log filenames',
                           default='AS6H2-RECV-30-45MS-RANGE') 
    argParser.add_argument('--csv', dest='csvname', help='String name to use for naming CSV files',
                           default=None)
    args = argParser.parse_args()

    if args.date_str is None:
        print("Date pattern not provided!!!\n")
        sys.exit(-1) 

    if args.csvname is None:
        csvname = args.date_str
    else:
        csvname = args.csvname

    path = basepath+'/'+'*'+args.date_str+'*'

    for i in range(1, args.runs+1):
        path = basepath+'/'+'*'+args.date_str+'-'+str(i)+'-*'
        filepaths = glob.glob(path) 
        if not filepaths:
            print("D-ITG Decoded logs do not exist for %s!!!" %(args.date_str+'-'+str(i)))
            continue
        print("filepaths seen by glob: %s" %filepaths)

        if len(filepaths) > 2:
            print("More than two log files seen, fix this!!!!")
            sys.exit(-1)

        for log in filepaths:
            print("i is %s"  %i)
            if fnmatch.fnmatch(log, '*'+args.h1_pfx+'*'):
                print("We got AS6H1 logs: %s" %log)
                with open(log) as f:
                    h1_lines = f.readlines()
                    h1_min, h1_max = float('inf'), float('-inf') 
                    h1_min_idx = 0 
                    h1_max_idx = 0
                    h1_delays = []
                    h1_txTimeStamps = txAll(h1_lines) 
                    h1_rxTimeStamps = rxAll(h1_lines)
                    h1_delays, h1_min, h1_max, h1_min_idx, h1_max_idx = CalculateDelay(h1_lines)


            if fnmatch.fnmatch(log, '*'+args.h2_pfx+'*'):
                print("We got AS6H2 logs: %s" %log)
                with open(log) as f:
                    h2_lines = f.readlines() 
                    h2_min, h2_max = float('inf'), float('-inf') 
                    h2_min_idx = 0 
                    h2_max_idx = 0
                    h2_delays = []
                    h2_txTimeStamps = txAll(h2_lines) 
                    h2_rxTimeStamps = rxAll(h2_lines)
                    h2_delays, h2_min, h2_max, h2_min_idx, h2_max_idx = CalculateDelay(h2_lines)

        if len(h1_delays) >= len(h2_delays): 
            max_csvlines = len(h1_delays)
        else: 
            max_csvlines  = len(h2_delays) 
            
        header = ['No of Packets','Transmitted Timestamp for AS6H1', 'Delay for AS6H1',
                  'Transmitted Timestamp for AS6H2','Delay for AS6H2']

        csvfilepath = csv_dir+csvname+'-'+str(i)+'.csv'

        if pathlib.Path(csvfilepath).is_file():
            print("%s exists!!!" %csvfilepath)
            continue

        with open(csvfilepath, 'w', newline='') as csvfile: 

            writer = csv.writer(csvfile)
            writer.writerow(header) 
            for i in range(0, max_csvlines):
                try:
                    h1_tx = h1_txTimeStamps[i].strftime("%H:%M:%S.%f")
                except IndexError:
                    h1_tx = " "

                try:
                    h2_tx = h2_txTimeStamps[i].strftime("%H:%M:%S.%f")
                except IndexError:
                    h2_tx = " "

                try:
                    h1_delay = h1_delays[i]
                except IndexError:
                    h1_delay = " "

                try: 
                    h2_delay = h2_delays[i]
                except IndexError: 
                    h2_delay = ""

                content = [i+1, h1_tx, h1_delay ,h2_tx, h2_delay] 
                writer.writerow(content)
        print("Generated: %s" %csvfilepath)
        print("\n")
