# DOCUMENTATION #

This file documents the commands and configurations required to use different
tools for my research and emulating PAR with overwatch in IPMininet or GNS3. 



## Exabgp
After installing exabgp with pip, create a directory in the home directory 
of the user where you will be running exabgp
```
mdkir -p ~/.exabgp/etc
mkdir -p ~/.exabgp/scripts
```
Copy the config below into ~/.exabgp/etc/exabgp.env
```

[exabgp.api]
ack = true
chunk = 1
cli = true
compact = false
encoder = json
pipename = 'exabgp'
respawn = true
terminate = false

[exabgp.bgp]
openwait = 60

[exabgp.cache]
attributes = true
nexthops = true

[exabgp.daemon]
daemonize = false
drop = true
pid = ''
umask = '0o137'
user = 'nobody'

[exabgp.log]
all = true 
configuration = true
daemon = true
destination = 'stdout'
enable = true
level = INFO
message = true
network = true
packets = false
parser = true
processes = true
reactor = true
rib = false
routes = true
short = false
timers = false

[exabgp.pdb]
enable = false

[exabgp.profile]
enable = false
file = ''

[exabgp.reactor]
speed = 1.0

[exabgp.tcp]
acl = false
bind = ''
delay = 0
once = false
port = 179
```
Create named pipes for exabgp cli 

```
mkdir /home/ubuntu/run
mkfifo /home/ubuntu/run/exabgp.{in,out}
chmod 600 /home/ubuntu/run/exabgp.{in,out}
```
In some cases it might be better to create the named pipes in /var/run
```
mkfifo /var/run/exabgp.{in.out}
chmod 666 /var/run/exabgp.{in,out}
```
to run exabgp with configs

```
env exabgp.daemon.deamonize=false exabgp ~/.exabgp/etc/exabgp.conf --env ~/.exabgp/etc/exabgp.env
```

## Overwatch
### We're using Cpython bytecode with overwatch.
To install and generate the cpython bytecode, cd into the overwatch directory
```
cd ~/git-repos/overwatch
```
Install overwatch in the python virtualenv with
```
source  PAR-EMULATOR/bin/activate
python setup.py build
python setup.py install
```
Copy ```Prefix.cpython-36m-x86_64-linux-gnu.so``` and ```RouteEntry.cpython-36m-x86_64-linux-gnu.so``` from the lib directory of the virtualenv to the bgpcontroller directory of the overwatch code 
```
cp ~/PAR-EMULATOR/lib64/python3.6/site-packages/Overwatch-1.0.0-py3.6-linux-x86_64.egg/Prefix.cpython-36m-x86_64-linux-gnu.so  ~/git-repos/overwatch/bgpcontroller

cp ~/PAR-EMULATOR/lib64/python3.6/site-packages/Overwatch-1.0.0-py3.6-linux-x86_64.egg/RouteEntry.cpython-36m-x86_64-linux-gnu.so ~/git-repos/overwatch/bgpcontroller 
```
