##
* Originated timestamp for a prefix is off by one second between MRT dumps collected over a period of time. It is not significant enough to 
change the results or indicate that routes are flapping and this seems to be as a result of time drifting/time shifting as seen by the output
of date and hwclock on the where the emulation is being run.
```
 date --rfc-3339=ns; hwclock
```
