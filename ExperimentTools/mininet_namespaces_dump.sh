#!/bin/bash
#for pid in $(/bin/ps -ef | grep mininet  | awk '{print $2}' | awk '{if(NR>1)print}')
for pid in $(/bin/ps -ef | grep mininet  | awk '{print $2}')
do
    cat /proc/"$pid"/net/dev
done
