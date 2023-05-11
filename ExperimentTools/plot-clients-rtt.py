#!/usr/bin/env python
import numpy as np
import argparse
import pathlib
import glob
import matplotlib.pyplot as plt
import matplotlib.dates as matdates
from matplotlib.ticker import AutoMinorLocator
import matplotlib
import pandas as pd
import re
import datetime 


def timeTicks(x, pos):
    d = datetime.timedelta(seconds=x)
    return str(d)
    #return "{:02d}:{:02d}".format(int(x//60), int(x%60))


def key(s):
    return tuple(map(int, re.findall(r'\d+', s)))


def get_numeric_part(filename):
    path = pathlib.Path(filename)
    return int(re.findall(r'\d+', path.stem)[0])
    

if __name__ == "__main__":

    argParser = argparse.ArgumentParser(
            description='Plot line chart to compare responsive of modes',
            usage='%(prog)s [-i dirname -o graphs')

    argParser.add_argument('-i', dest='dirname',
                           help='Directory where game client message logs are stored',
                           type=str,
                           default='/home/ubuntu/gClient-control-logs')

    argParser.add_argument('-o', dest='output',
                           help='File to output results of all game clients',
                           type=str,
                           default=None)

    args = argParser.parse_args()

    if args.output is None:
        raise SystemExit("No filename supplied for result ouput")

    if not pathlib.Path(args.dirname).exists():
        raise SystemExit("Directory for the game client messages does not exist")

    csvlogs = glob.glob(f'{args.dirname}/*.csv')
    if not csvlogs:
        raise SystemExit("No .csv for clients found in {args.dirname}.")

    csvlogs = sorted(csvlogs, key=get_numeric_part)

    dfs = []
    for csvlog in csvlogs:
        path = pathlib.Path(csvlog)
        df = pd.read_csv(csvlog, sep='|', index_col=False)
        host = path.stem
        df['Client'] = host
        dfs.append(df)
    df = pd.concat(dfs)
    df['Receive Time'] = pd.to_datetime(df['Receive Time'], unit='s')
    df['Receive Time'] = df['Receive Time'].dt.floor('s')
    pivot_table = pd.pivot_table(df, index='Receive Time', values='RTT', aggfunc='count')

    fig, ax1 = plt.subplots(figsize=(11.69, 8.27))
    ax2 = ax1.twinx()
    ax1.set_xlabel('Receive Time')
    ax1.set_ylabel('RTT (ms)')
    ax2.set_ylabel('Number of clients')
    secLocator = matdates.SecondLocator(bysecond=[20,40])
    minorFmt = matdates.DateFormatter('%S')
    secLocator.MAXTICKS  = 40000

    #locator = matdates.AutoDateLocator(minticks=1, maxticks=5)
    #locator.MAXTICKS = 40000
    #formatter = matdates.ConciseDateFormatter(locator)
    #formatter.formats = ['%y',  # ticks are mostly years
    #                     '%b',       # ticks are mostly months
    #                     '%d',       # ticks are mostly days
    #                     '%H:%M:%S',    # hrs
    #                     '%M:%S',    # min
    #                     '%S.%f', ]  # secs
    #ax1.xaxis.set_major_locator(locator)
    #ax1.xaxis.set_major_formatter(formatter)
    #ax1.xaxis.set_minor_locator(secLocator)
    #ax1.xaxis.set_minor_formatter(minorFmt)
    formatter = matplotlib.ticker.FuncFormatter(timeTicks)
    ax1.xaxis.set_major_formatter(formatter)
    #xloc = matdates.MinuteLocator(interval = 5)
    ax1.xaxis.set_major_locator(matplotlib.ticker.AutoLocator())
    #ax1.xaxis.set_major_locator(plt.MultipleLocator(1*60))

    ax1.xaxis.set_minor_locator(AutoMinorLocator())
    #ax1.xaxis.set_major_locator(plt.MultipleLocator(1*60))
    #ax1.xaxis.set_minor_formatter(minorFmt)
    #ax1.xaxis.set_minor_locator(secLocator)

    #ax1.minorticks_on()
    #plt.setp(ax1.xaxis.get_minorticklabels(), rotation=90)
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=90)
             #horizontalalignment='center')

    for client, group in df.groupby('Client'):
        ax1.scatter(group['Receive Time'], group['RTT'], s=2,
                    label=client)

    colormap = plt.cm.gist_ncar
    colorst = [colormap(i) for i in np.linspace(0, 0.9, len(ax1.collections))]
    
    for t, j1 in enumerate(ax1.collections):
        j1.set_color(colorst[t])

    ax1.set_ylim(ymin=0)
    ax1.set_xlabel('Game session duration (%H:%M:%S)')
    ax1.set_ylabel('RTT (ms)')
    ax2.set_ylabel('Number of Clients')
    #ax1.set_title(f"Scenario 4: RTT of clients when BGP's default path for half the clients is bad\n"
    #              f"and Overwatch is running with decision period T of 1 seconds\n"
    #              f"and game session duration of 10 minutes")
    ax1.set_title(f"Scenario 2: RTT of clients when BGP's default path for half the clients is bad\n"
                  f"and Overwatch is not running" )

    ax1.axhline(y=60, color='g', linestyle='-')

    ax2.plot(pivot_table.index, pivot_table['RTT'], color='blue', label='Clients in game')
    ax2.tick_params(axis='y', colors='blue')
    #ax2.yaxis.label.set_color('blue')
    #ax2.spines['right'].set_color('blue')
    ax2.set_ylim([0, max(pivot_table['RTT'])+1])

    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    handles = handles1 + handles2
    labels = labels1 + labels2
    ax1.legend(handles, labels, fontsize='small', loc=(1.04, 1), ncol=4)
    ax1.grid(True)
    plt.tight_layout()
    plt.show()

