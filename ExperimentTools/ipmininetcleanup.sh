#!/bin/bash
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

