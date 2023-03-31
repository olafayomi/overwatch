#!/bin/bash
DATE=`date "+%Y%m%d"`

helpFunction()
{
  echo ""
  echo "Usage: $0 -s script -n num_run -d duration"
  echo -e "\t-s IPMininet topology script to run"
  echo -e "\t-n Number of times to run the IPMininet script for an experiment"
  #echo -e "\t-d Duration of each run in minutes"
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

  echo "Deleting csv files in /home/ubuntu/gClient-control-logs"
  rm  -rf /home/ubuntu/gClient-control-logs/*
  echo "Done!!!, csv files deleted"

  echo "Deleting sock files in /home/ubuntu"
  rm  -rf /home/ubuntu/bandwidth.sock
  rm  -rf /home/ubuntu/differentiated.sock
  rm  -rf /home/ubuntu/latency.sock
  rm  -rf /home/ubuntu/loss.sock
  rm  -rf /home/ubuntu/perf.sock
  rm  -rf /home/ubuntu/host4.sock
  rm  -rf /home/ubuntu/host5.sock
  echo "Done!!!, Sock files deleted"

  echo "Remove clients.txt"
  rm -rf /home/ubuntu/clients.txt
  echo "Done!!!, clients.txt removed"

  echo "Delete links"
  /sbin/ip link del dev Sw1Tp1
  /sbin/ip link del dev Sw2Tp2
  /sbin/ip link del dev Sw2Tp3
  echo "Done!!!, Links deleted"
}

while getopts "s:n:d:" opt
do
   case "$opt" in 
      s ) script="$OPTARG" ;;
      n ) num_run="$OPTARG" ;;
      #d ) duration="$OPTARG" ;;
      ? ) helpFunction ;;
   esac
done

# Print helpFunction in case parameters are empty
#if [ -z "$script" ]||[ -z "$num_run" ] || [ -z "$duration" ]
if [ -z "$script" ]||[ -z "$num_run" ]
then
   echo "Some or all of the parameters are empty";
   helpFunction
fi

re='^[0-9]+$' 

if ! [[ $num_run =~ $re ]] ; then 
   echo "ERROR: Number of run supplied is not a number"  >&2;  exit 1
fi

#if ! [[ $duration =~ $re ]] ; then 
#   echo "ERROR: Duration supplied is not a number" >&2; exit 1
#fi

if [ ! -f "$script" ]; then
   echo "IPMininet script cannot be found!!!" >&2; exit 1
fi


for i in $(seq 1 $num_run);
do
   echo -e "Experiment run $i\n";
   /usr/bin/python $script 
   source /home/ubuntu/PAR-EMULATOR/bin/activate
   /home/ubuntu/PAR-EMULATOR/bin/python process-game-msm.py -i ~/gClient-control-logs -p 90 -o ~/Ovw-Eval-Results/AS34410/expt-$DATE-$i-7-percent-Threshold-Continous-Weighted-Measurements-with-0.125-alpha
   mv /home/ubuntu/Ovw-Eval-Results/AS34410/msmModule/msmtiming  /home/ubuntu/Ovw-Eval-Results/AS34410/msmModule/msmtiming-$DATE-$i-7-percent-Threshold-Continous-Weighted-Measurements-with-0.125-alpha
   deactivate
   cleanup
done
