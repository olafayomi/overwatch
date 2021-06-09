#!/bin/bash
DATE=`date "+%Y%m%d"`

helpFunction()
{
  echo ""
  echo "Usage: $0 -s script -n num_run -d duration"
  echo -e "\t-s IPMininet topology script to run"
  echo -e "\t-n Number of times to run the IPMininet script for an experiment"
  echo -e "\t-d Duration of each run in minutes"
  exit 1 # Exit script after printing help 
}

cleanup()
{
  echo "Clean ipmininet artefacts ...."
  /usr/bin/python -m ipmininet.clean
  echo "Done!!!"

  echo "Deleting config files in /tmp"
  rm -rf /tmp/resolv_*
  rm -rf /tmp/ospf*
  rm -rf /tmp/bgpd*
  rm -rf /tmp/hosts*
  rm -rf /tmp/exabgp*
  rm -rf /tmp/quagga*
  rm -rf /tmp/tmp*
  rm -rf /tmp/zebra_*
  echo "Done!!!, config files deleted"

  echo "Deleting sock file in /home/ubuntu"
  rm  -rf /home/ubuntu/perf.sock
  echo "Done!!!, Sock file deleted"

  echo "Delete links"
  /sbin/ip link del dev as3sw1
  /sbin/ip link del dev s1
  /sbin/ip link del dev s2
  /sbin/ip link del dev s3
  echo "Done!!!, Links deleted"
}

while getopts "s:n:d:" opt
do
   case "$opt" in 
      s ) script="$OPTARG" ;;
      n ) num_run="$OPTARG" ;;
      d ) duration="$OPTARG" ;;
      ? ) helpFunction ;;
   esac
done

# Print helpFunction in case parameters are empty
if [ -z "$script" ]||[ -z "$num_run" ] || [ -z "$duration" ]
then
   echo "Some or all of the parameters are empty";
   helpFunction
fi

re='^[0-9]+$' 

if ! [[ $num_run =~ $re ]] ; then 
   echo "ERROR: Number of run supplied is not a number"  >&2;  exit 1
fi

if ! [[ $duration =~ $re ]] ; then 
   echo "ERROR: Duration supplied is not a number" >&2; exit 1
fi

if [ ! -f "$script" ]; then
   echo "IPMininet script cannot be found!!!" >&2; exit 1
fi

for i in $(seq 1 $num_run);
do
   echo -e "Experiment run $i\n";
   /usr/bin/python $script --gen-duration 600000 --best-delay 20 --date-append $DATE --expt-no $i --runtime $duration
   cleanup
done

#python PARTopoV6DelayMulti.py --date-append 20210604 --expt-no 2 --runtime 16
