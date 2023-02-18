#!/usr/bin/env python
import numpy as np
import argparse
import pathlib
import glob
import csv


if __name__ == "__main__":

    argParser = argparse.ArgumentParser(
            description='Process game client message logs',
            usage='%(prog)s [-i dirname -o csv-output-results')

    argParser.add_argument('-i', dest='dirname',
                           help='Directory where game client message logs are stored',
                           type=str,
                           default='/home/ubuntu/gClient-logs')

    argParser.add_argument('-o', dest='output',
                           help='File to output results of all game clients',
                           type=argparse.FileType('w'),
                           default=None)

    argParser.add_argument('-t', dest='threshold',
                           help='Game threshold to accepted or reject client in ms',
                           type=int,
                           default=60)

    args = argParser.parse_args()

    if args.output is None:
        raise SystemExit("No filename supplied for result ouput")

    if not pathlib.Path(args.dirname).exists():
        raise SystemExit("Directory for the game client messages does not exist")

    csvlogs = glob.glob(f'{args.dirname}/*.csv')
    if not csvlogs:
        raise SystemExit("No .csv for clients found in {args.dirname}.")

    with args.output as f:
        writer = csv.writer(f, delimiter='|')
        writer.writerow(["Hostname", "IP address", "Number of messages",
                         "Duration", "Min RTT", "Median RTT", "Mean RTT",
                         "Max RTT", "90th Percentile", "Accepted"])
        for csvlog in csvlogs:
            with open(csvlog, 'r') as csvfile:
                header = next(csvfile)
                reader = csv.reader(csvfile, delimiter='|')
                p = pathlib.Path(csvlog)

                rtts = []
                timestamp = []
                for row in reader:
                    f1 = row[0].split(",", 1)
                    ip = f1[0]
                    timestamp.append(row[1])
                    rtts.append(float(row[2]))
                minRTT = np.min(rtts)
                maxRTT = np.max(rtts)
                medRTT = np.median(rtts)
                avgRTT = np.mean(rtts)
                percentile = np.percentile(rtts, 90)
                duration = float(timestamp[-1]) - float(timestamp[0])
                if percentile <= args.threshold:
                    accepted = True
                else:
                    accepted = False
                writer.writerow([p.stem, ip, len(rtts), duration, minRTT,
                                 medRTT, avgRTT, maxRTT, percentile,
                                 accepted])
