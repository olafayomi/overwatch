#!/usr/bin/env python
import os
import sys
import argparse
import pathlib
import subprocess
import glob

basepath = '/home/ubuntu/DITG-LOGS'
if __name__ == "__main__": 
    argParser = argparse.ArgumentParser(
            description='Decode D-ITG logs to text logs', 
            usage='%(prog)s [--pattern AS6H1-RECV-20210605]')
    argParser.add_argument('--pattern', dest='pattern', help='Filename pattern to check',
                           default=None)
    args = argParser.parse_args()

    if args.pattern is None:
        print("File name pattern not provided!!!\n") 
        sys.exit(-1)

    path = basepath+'/'+'*'+args.pattern+'*'

    for name in glob.glob(path):
        print("Decoding: %s" %name)
        pathname  = pathlib.Path(name) 
        d = 'DECODED' 
        decoded = pathname.with_name(f"{pathname.stem}-{d}{pathname.suffix}")
        decodedlog = basepath+'/'+'DECODED-LOGS/'+decoded.name
        cmdlist = ['/usr/bin/ITGDec', name, '-l', decodedlog]
        command = subprocess.run(cmdlist)
        print("\n")
        
