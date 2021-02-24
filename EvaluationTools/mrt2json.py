#!/usr/bin/python
""" This script processes MRT dump files that contains the RIB
    of a particular router. It outputs a csv file containing the
    AS length, AS path, Next hop and originated time for the prefix
    supplied as an argument. This csv file determines whether overwatch
    and PAR has any impact on the RIB of an external peer that is connected
    to a network providing PAR
"""

import json
import sys
from mrtparse import *
from argparse import ArgumentParser
import glob
import csv
import os

def main(dump_file, csvoutput, pfx):
    with open(csvoutput, 'a') as f:
        riblist = []
        i = 0
        csvwriter = csv.writer(f, dialect='pipes')
        for entry in Reader(dump_file):
            riblist.append(json.dumps(entry.data))
       
        for entry in riblist:
            ent = json.loads(entry)
            if 'prefix' in ent:
                if ent['prefix'] == pfx:
                    entry_count = ent['entry_count'] 
                    #print(ent)
                    #print("\n\n")
                    rib_entries = ent['rib_entries']
                    for i in range(entry_count):
                        orig_time = rib_entries[i]['originated_time']
                        as_len = rib_entries[i]['path_attributes'][1]['value'][0]['length']
                        as_path = rib_entries[i]['path_attributes'][1]['value'][0]['value']
                        for attr in rib_entries[i]['path_attributes']:
                            if attr['flag'] == 128:
                                next_hop = attr['value']['next_hop']
                        str_nexthop = ','.join(map(str, next_hop))
                        str_aspath = ','.join(map(str, as_path))
                        str_time = ','.join(map(str, orig_time))
                        csvwriter.writerow((str(dump_file), as_len, str_aspath, '{0:<8s}'.format(str_nexthop), str_time))
                        #print("Prefix originated at %s" %(orig_time[1]))
                        #print("AS length is %s" %(as_len))
                        #print("AS Path is %s" %(as_path))
                        #print("Next hop is %s" %(next_hop))
                        #print("\n\n")

if __name__ == '__main__':
    argParser = ArgumentParser(
            description='Fetch RIB entry details for a prefix from MRT dumps',
            usage='%(prog)s [-P prefix -O output.csv -I mrt_filename_patterns]')
    argParser.add_argument('-P', dest='prefix', help='The prefix to search',
                           default=None)
    argParser.add_argument('-O ', dest='csvfile', help='CSV file to write RIB details',
                           default=None)
    argParser.add_argument('-I', dest='mrtdump_pattern', help='Filename pattern for MRT dump',
                           default=None)
    args = argParser.parse_args()

    csv.register_dialect('pipes', delimiter='|')


    if args.prefix is None:
        print("Prefix to search not provided!!!")
        sys.exit(-1)

    if args.csvfile is None:
        print("CSV file to write results not provided!!!") 
        sys.exit(-1)

    if args.mrtdump_pattern is None:
        print("MRT filename pattern and directory not provided!!!")
        sys.exit(-1)

    if not os.path.exists(args.csvfile):
        with open(args.csvfile, 'a') as f:
            header = csv.writer(f, dialect='pipes')
            header.writerow(('MRTdump', 'AS-length', 'AS-path', 'Next-hop', 'OriginatedTime'))

    for name in glob.glob(args.mrtdump_pattern):
        print(name)
        main(name, args.csvfile, args.prefix)
