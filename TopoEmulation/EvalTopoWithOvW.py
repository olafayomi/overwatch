from ipmininet.iptopo import IPTopo
from ipmininet.cli import IPCLI
from ipmininet.ipnet import IPNet
from ipmininet.router.config.ospf import OSPFRedistributedRoute
from ipmininet.srv6 import enable_srv6
from ipmininet.router.config import BGP, ebgp_session, set_rr, AccessList, \
     AF_INET6, AF_INET, BorderRouterConfig, RouterConfig, OSPF, OSPF6, \
     bgp_peering, ExaBGPDaemon, STATIC, StaticRoute, CLIENT_PROVIDER, SHARE
from ipmininet.link import IPLink
import argparse
import pathlib
import csv
import statistics as stat
import time
from datetime import datetime
import asyncio
import threading
from collections import OrderedDict
import socket
import perfmon_pb2 as perfmsg 
import struct 
import os 
import sys

def encode_msg_size(size: int) -> bytes:
    return struct.pack("<I", size)

def create_msg(content: bytes) -> bytes:
    size = len(content)
    return encode_msg_size(size) + content


class TestTopo(IPTopo):
    """The topology is composed of 55 ASes. One of the ASes is the
    game server network and it hosts the game serve (AS1). Four of these ASes
    are transit providers while the rest are stub ASes that host the game
    clients. Transit AS2 is the transit provider for the game server network
    and the network running Overwatch. Transit AS3 and AS4 are peers of AS2
    and they provide transit for AS5 which is the ISPs for AS6 to AS55.
    The peerings AS2<->AS3 and AS2<->AS4 provide multiple paths to reach
    AS6 to AS55. """

    def build(self, *args, **kwargs):
        # Add all routers

        GsASr1 = self.bgp('GsASr1')
        Tp1ASr1 = self.bgp('Tp1ASr1')
        Tp1ASr2 = self.bgp('Tp1ASr2')
        Tp1ASr3 = self.bgp('Tp1ASr3')
        Tp2ASr1 = self.bgp('Tp2ASr1')
        Tp2ASr2 = self.bgp('Tp2ASr2')
        Tp3ASr1 = self.bgp('Tp3ASr1')
        Tp3ASr2 = self.bgp('Tp3ASr2')
        Tp4ASr1 = self.bgp('Tp4ASr1')
        Tp5ASr1 = self.bgp('Tp5ASr1')

        AS1R1 = self.bgp('AS1R1')
        AS2R1 = self.bgp('AS2R1')
        AS3R1 = self.bgp('AS3R1')
        AS4R1 = self.bgp('AS4R1')
        AS5R1 = self.bgp('AS5R1')
        AS6R1 = self.bgp('AS6R1')
        AS7R1 = self.bgp('AS7R1')
        AS8R1 = self.bgp('AS8R1')
        AS9R1 = self.bgp('AS9R1')
        AS10R1 = self.bgp('AS10R1')
        AS11R1 = self.bgp('AS11R1')
        AS12R1 = self.bgp('AS12R1')
        AS13R1 = self.bgp('AS13R1')
        AS14R1 = self.bgp('AS14R1')
        AS15R1 = self.bgp('AS15R1')
        AS16R1 = self.bgp('AS16R1')
        AS17R1 = self.bgp('AS17R1')
        AS18R1 = self.bgp('AS18R1')
        AS19R1 = self.bgp('AS19R1')
        AS20R1 = self.bgp('AS20R1')
        AS21R1 = self.bgp('AS21R1')
        AS22R1 = self.bgp('AS22R1')
        AS23R1 = self.bgp('AS23R1')
        AS24R1 = self.bgp('AS24R1')
        AS25R1 = self.bgp('AS25R1')
        AS26R1 = self.bgp('AS26R1')
        AS27R1 = self.bgp('AS27R1')
        AS28R1 = self.bgp('AS28R1')
        AS29R1 = self.bgp('AS29R1')
        AS30R1 = self.bgp('AS30R1')
        AS31R1 = self.bgp('AS31R1')
        AS32R1 = self.bgp('AS32R1')
        AS33R1 = self.bgp('AS33R1')
        AS34R1 = self.bgp('AS34R1')
        AS35R1 = self.bgp('AS35R1')
        AS36R1 = self.bgp('AS36R1')
        AS37R1 = self.bgp('AS37R1')
        AS38R1 = self.bgp('AS38R1')
        AS39R1 = self.bgp('AS39R1')
        AS40R1 = self.bgp('AS40R1')
        AS41R1 = self.bgp('AS41R1')
        AS42R1 = self.bgp('AS42R1')
        AS43R1 = self.bgp('AS43R1')
        AS44R1 = self.bgp('AS44R1')
        AS45R1 = self.bgp('AS45R1')
        AS46R1 = self.bgp('AS46R1')
        AS47R1 = self.bgp('AS47R1')
        AS48R1 = self.bgp('AS48R1')
        AS49R1 = self.bgp('AS49R1')
        AS50R1 = self.bgp('AS50R1')

        Sw1Tp1 = self.addSwitch('Sw1Tp1')
        Sw2Tp2 = self.addSwitch('Sw2Tp2')
        Sw3Tp3 = self.addSwitch('Sw3Tp3')
        #Sw4Gs = self.addSwitch('Sw4Gs')

        Tp1ASr1Sw1 = self.addLink(Tp1ASr1, Sw1Tp1)
        Tp1ASr1Sw1[Tp1ASr1].addParams(ip=("100::1/48",))
        Tp1ASr2Sw1 = self.addLink(Tp1ASr2, Sw1Tp1)
        Tp1ASr2Sw1[Tp1ASr2].addParams(ip=("100::2/48",))
        Tp1ASr3Sw1 = self.addLink(Tp1ASr3, Sw1Tp1)
        Tp1ASr3Sw1[Tp1ASr3].addParams(ip=("100::3/48",))

        # Add controller and ExaBGP speaker node
        Tp1ASctlr = self.addRouter("Tp1ASctlr", config=RouterConfig)
        Tp1ASctlrSw1 = self.addLink(Tp1ASctlr, Sw1Tp1)
        Tp1ASctlrSw1[Tp1ASctlr].addParams(ip=("100::4/48",))
        Tp1ASctlr.addDaemon(ExaBGPDaemon, env = { 'api' : {'cli':'true', 'encoder':'json',
                                                       'ack':'true', 'pipename':'\'exabgp\'',
                                                       'respawn':'true','chunk':1,
                                                       'terminate':'false'},
                                              'bgp' : {'openwait' : 60},
                                              'cache': {'attributes':'true', 'nexthops':'true'},
                                              'daemon': {'daemonize':'false', 'drop':'true', 
                                                         'pid': '\'\'', 'umask':'\'0o137\'', 
                                                         'user':'nobody'},
                                              'log': {'all':'true','configuration':'true','daemon':'true',
                                                      'message':'true','destination':'stdout',
                                                      'enable':'true','level':'INFO','network':'true',
                                                      'packets':'false','parser':'true',
                                                      'processes':'true','reactor':'true',
                                                      'rib':'false','routes':'true','short':'false',
                                                      'timers':'false'},
                                              'pdb': {'enable':'false'},
                                              'profile': { 'enable':'false', 'file':'\'\''},
                                              'reactor': {'speed':'1.0'},
                                              'tcp': {'acl':'false', 'bind':'', 'delay':0,
                                                      'once':'false', 'port': 179}
                                            }, passive=False )

        lTp1Tp2 = self.addLink(Tp1ASr2, Tp2ASr1)
        lTp1Tp2[Tp1ASr2].addParams(ip=("1002::100/48",))
        lTp1Tp2[Tp2ASr1].addParams(ip=("1002::200/48",))

        Tp2ASr1Sw2 = self.addLink(Tp2ASr1, Sw2Tp2)
        Tp2ASr1Sw2[Tp2ASr1].addParams(ip=("200::1/48",))
        Tp2ASr2Sw2 = self.addLink(Tp2ASr2, Sw2Tp2)
        Tp2ASr2Sw2[Tp2ASr2].addParams(ip=("200::2/48",))

        lTp1Tp3 = self.addLink(Tp1ASr3, Tp3ASr1)
        lTp1Tp3[Tp1ASr3].addParams(ip=("1003::100/48",))
        lTp1Tp3[Tp3ASr1].addParams(ip=("1003::300/48",))

        Tp3ASr1Sw3 = self.addLink(Tp3ASr1, Sw3Tp3)
        Tp3ASr1Sw3[Tp3ASr1].addParams(ip=("300::1/48",))
        Tp3ASr2Sw3 = self.addLink(Tp3ASr2, Sw3Tp3)
        Tp3ASr2Sw3[Tp3ASr2].addParams(ip=("300::2/48",))

        # Add Game server host to topology
        gameServer = self.addHost('gameServer')
        lGsR = self.addLink(gameServer, GsASr1)
        lGsR[gameServer].addParams(ip=("55::1/48",))
        #GsRtrLink = self.addLink(GsASr1, Sw4Gs)
        lGsR[GsASr1].addParams(ip=("55::2/48",))

        #msmHost1 = self.addHost('msmHost1')
        #msmlink1 = self.addLink(msmHost1, Sw4Gs)
        #msmlink1[msmHost1].addParams(ip=("55::6/48",))

        #msmHost2 = self.addHost('msmHost2')
        #msmlink2 = self.addLink(msmHost2, Sw4Gs)
        #msmlink2[msmHost2].addParams(ip=("55::7/48",))

        # Add game client hosts to user network, one host per networt!!!

        for i in range(1, 51):
            exec(f"gCl{i} = self.addHost('gCl{i}')")
            exec(f"gClink{i} = self.addLink(AS{i}R1, gCl{i})")
            ip = f"2001:df{str(i).zfill(2)}::2/48"
            exec(f"gClink{i}[AS{i}R1].addParams(ip=('{ip}',))")
            ip = f"2001:df{str(i).zfill(2)}::1/48"
            exec(f"gClink{i}[gCl{i}].addParams(ip=('{ip}',))")

        self.addLinks((GsASr1, Tp1ASr1), (Tp2ASr2, Tp4ASr1),
                      (Tp3ASr2, Tp4ASr1),(GsASr1, Tp5ASr1),
                      (Tp5ASr1, Tp4ASr1))

        link_delay = 8.2

        for i in range(1, 51):
            link = self.addLink(Tp4ASr1, eval("AS{}R1".format(i)),
                                delay="{}ms".format(link_delay/2))
            link_delay += 0.1

        self.addAS(55, (GsASr1,))
        self.addAS(100, (Tp1ASr1, Tp1ASr2, Tp1ASr3, Tp1ASctlr))
        self.addAS(200, (Tp2ASr1, Tp2ASr2))
        self.addAS(300, (Tp3ASr1, Tp3ASr2))
        self.addAS(400, (Tp4ASr1,))
        self.addAS(500, (Tp5ASr1,))

        for i in range(1, 51):
            exec(f"self.addAS(i, (AS{i}R1,))")

        #bgp_peering(self, Tp1ASr1, Tp1ASr2)
        #bgp_peering(self, Tp1ASr1, Tp1ASr3)
        bgp_peering(self, Tp1ASr1, Tp1ASctlr) 
        bgp_peering(self, Tp1ASr2, Tp1ASctlr)
        bgp_peering(self, Tp1ASr3, Tp1ASctlr)

        bgp_peering(self, Tp2ASr1, Tp2ASr2)
        bgp_peering(self, Tp3ASr1, Tp3ASr2)
        
        # Set ACL and prefer one path over the other
        acl4 = AccessList(name='all', entries=('any',), family='ipv4')
        acl = AccessList(name='all6', entries=('any',), family='ipv6')
        #prefer path via Tp3 or Tp2
        Tp1ASr3.get_config(BGP).set_local_pref(100, from_peer=Tp3ASr1,
                                               matching=(acl4,acl))

        Tp1ASr2.get_config(BGP).set_local_pref(200, from_peer=Tp2ASr1,
                                               matching=(acl4,acl))

        ebgp_session(self, GsASr1, Tp1ASr1, link_type=CLIENT_PROVIDER)
        ebgp_session(self, GsASr1, Tp5ASr1, link_type=CLIENT_PROVIDER)

        ebgp_session(self, Tp1ASr2, Tp2ASr1)
        ebgp_session(self, Tp1ASr3, Tp3ASr1)

        # Prefer return path from clients via Tp3 or Tp2
        Tp4ASr1.get_config(BGP).set_local_pref(100, from_peer=Tp2ASr2,
                                               matching=(acl4,acl))
        Tp4ASr1.get_config(BGP).set_local_pref(100, from_peer=Tp3ASr2,
                                               matching=(acl4,acl))
        ebgp_session(self, Tp4ASr1, Tp2ASr2) #, link_type=CLIENT_PROVIDER)
        ebgp_session(self, Tp4ASr1, Tp3ASr2) #, link_type=CLIENT_PROVIDER)
        Tp5ASr1.get_config(BGP).deny(to_peer=GsASr1,
                                     matching=(acl4,acl))
        ebgp_session(self, Tp4ASr1, Tp5ASr1)


        for i in range(1, 51):
            exec(f"ebgp_session(self, AS{i}R1, Tp4ASr1, link_type=CLIENT_PROVIDER)")

        super().build(*args, **kwargs)

    def post_build(self, net):
        for n in net.hosts + net.routers:
            enable_srv6(n)
        super().post_build(net)

    def bgp(self, name):
        r = self.addRouter(name, config=RouterConfig)
        r.addDaemon(BGP,  address_families=(
            AF_INET(redistribute=('connected',)),
            AF_INET6(redistribute=('connected',))))
        return r


#class PARNet(IPNet):
#    def __init__(self, *args, **kwargs):
#        super().__init__(*args, **kwargs)
#      
#    def modifyLink(self, node1, node2, delay="2ms", bw=None,
#                max_queue_size=None, **opts):
#        src_delay = None
#        dst_delay = None
#        src_loss = None
#        dst_loss = None
#        src_max_queue = None
#
#        opts1 = dict(opts)
#        if "params2" in opts1:
#            opts1.pop("params2")
#        try:
#            src_delay = opts.get("params1", {}).pop("delay")
#        except KeyError:
#            pass
#        
#        try:
#            src_loss = opts.get("params1", {}).pop("loss")
#        except KeyError:
#            pass
#
#
#        try:
#            src_max_queue = opts.get("params1", {}).pop("max_queue_size")
#        except KeyError:
#            pass
#
#        opts2 = dict(opts)
#        if "params" in opts2:
#            opts2.pop("params1")
#        try:
#            dst_delay = opts.get("params2", {}).pop("delay")
#        except KeyError:
#            pass
#
#        try:
#            dst_loss = opts.get("params2", {}).pop("loss")
#        except KeyError:
#            pass
#
#
#
#        if (src_delay is not None) or (src_loss is not None) or (src_max_queue is not None):
#            for sw in self.switches:
#                srclink1 = node2.connectionsTo(sw)
#                dstlink1 = node1.connectionsTo(sw)
#                
#                if srclink1 and dstlink1:
#                    break
#
#            print("srclink1 is type %s" %type(srclink1))
#            print(srclink1)
#
#            print("dstlink1 is type %s" %type(dstlink1))
#            print(dstlink1)
#            int1, int2 = srclink1[0]
#            if src_delay:
#                delay_v = src_delay
#            else: 
#                delay_v = 0
#
#            if src_loss:
#                loss_v = src_loss
#            else:
#                loss_v = 0
#                
#            if src_max_queue:
#                queue_size = src_max_queue
#            else:
#                src_del = int(''.join(filter(str.isdigit, src_delay)))
#                queue_size = ((bw * 1000000) * (src_del/1000) * 1.5)/10240
#                
#            print("Queue size to applied: %s"  %queue_size)
#            int2.config(delay=delay_v , max_queue_size=queue_size, loss=loss_v)
#
#            eg_int1,eg_int2 = dstlink1[0]
#            print("bandwidth: %s" %bw)
#            eg_int1.config(bw=bw)
#
#            #int1.config(max_queue_size = 15000)
#            #print(help(int2.config))
#            #print("int1 is type: %s" %type(int1))
#            #print(int2)

class PARNet(IPNet):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
      

    def modifyLink(self, node1, node2, delay="2ms", bw=None, max_queue_size=None, **opts):

        src_params = opts.get("params1", {})
        dst_params = opts.get("params2", {})        
        src_delay = src_params.get("delay")
        src_loss = src_params.get("loss")
        src_max_queue = src_params.get("max_queue_size")
        
        dst_delay = dst_params.get("delay")
        dst_loss = dst_params.get("loss")
        dst_max_queue = dst_params.get("max_queue_size")
        
        for sw in self.switches:
            src_link = node2.connectionsTo(sw)
            dst_link = node1.connectionsTo(sw)
            if src_link and dst_link:
                break

        src_int, _ = src_link[0]
        dst_int, _ = dst_link[0]

        src_delay = src_delay or delay
        src_loss = src_loss or 0
        #src_max_queue = src_max_queue or ((bw * 1000000) * (int(src_delay.rstrip("ms")) / 1000) * 1.5) / 10240
        
        src_int.config(delay=src_delay, max_queue_size=src_max_queue, loss=src_loss)
        dst_int.config(delay=dst_delay, max_queue_size= src_max_queue, loss=dst_loss)

async def sleep(duration):
    await asyncio.sleep(duration)

if __name__ == '__main__':
#async def run_experiment():
    net = PARNet(topo=TestTopo(), use_v4=False)
    bwidthsock = '/home/ubuntu/bandwidth.sock'
    latsock = '/home/ubuntu/latency.sock'
    lossock = '/home/ubuntu/loss.sock'
    diffsock = '/home/ubuntu/differentiated.sock'
    #parsocks = [ bwidthsock, latsock, lossock, diffsock]
    parsocks = [ latsock ]


    tp2_rtt = []
    with open('/home/ubuntu/ping-msms-between-as34410-and-ubisoft-49544/rtts/rtts-via-AS1273-prb51217.csv','r') as f:
        header = next(f)
        reader = csv.reader(f)
        for row in reader:
            tp2_rtt.append(float(row[1]))

    print(len(tp2_rtt))
    tp3_rtt = []
    with open('/home/ubuntu/ping-msms-between-as34410-and-ubisoft-49544/rtts/rtts-via-AS1299-prb51217.csv', 'r') as f:
        header = next(f)
        reader = csv.reader(f)
        for row in reader:
            tp3_rtt.append(float(row[1]))
    print(len(tp3_rtt))
    try:
        net.start()
        # divide rtt by 2 
        tp2_delay = min(tp2_rtt)
        # set tp3 delay to 5ms (to make  10ms rtt) to catch any odd behaviour
        #tp3_delay = 5
        tp3_delay = min(tp3_rtt)
        
        alt_lat = [ tp3_delay if i % 2 == 0 else tp3_delay+2 for i in range(100)]
            
        net.modifyLink(net["Tp2ASr1"], net["Tp2ASr2"],
                       params1={"delay": "{}ms".format(tp2_delay)},
                       params2={"delay": "{}ms".format(tp2_delay)})
        net.modifyLink(net["Tp3ASr1"], net["Tp3ASr2"],
                       params1={"delay": "{}ms".format(tp3_delay)},
                       params2={"delay": "{}ms".format(tp3_delay)})
        print(f'Delay set on Tp2 link is {tp2_delay}ms and RTT should be above {min(tp2_rtt)}ms')
        print(f'Delay set on Tp3 link is {tp3_delay}ms and RTT should be above {min(tp3_rtt)}ms')
        #def run_game_server():
        #    exec(f'net["gameServer"].cmd("python gameServer.py &> /home/ubuntu/gcl-out/gServer.log &")')
        #game_server_thread = threading.Thread(target=run_game_server)
        #game_server_thread.start()
        #net["gameServer"].cmd("python gameServer.py &> /home/ubuntu/gcl-out/gServer.log &")
        net["gameServer"].cmd("python gameServer.py &> /dev/null &")
        net["Tp1ASr1"].cmd("source /home/ubuntu/PAR-EMULATOR/bin/activate")
        net["Tp1ASr1"].cmd("/home/ubuntu/PAR-EMULATOR/bin/python /home/ubuntu/git-repos/srv6-controller/grpc/dataplane-manager.py -e /home/ubuntu/git-repos/srv6-controller/grpc/dataplane_manager.env &> dataplane-Tp1ASr1.log &")


        net["Tp1ASr2"].cmd("source /home/ubuntu/PAR-EMULATOR/bin/activate")
        net["Tp1ASr2"].cmd("/home/ubuntu/PAR-EMULATOR/bin/python /home/ubuntu/git-repos/srv6-controller/grpc/dataplane-manager.py -e /home/ubuntu/git-repos/srv6-controller/grpc/dataplane_manager.env &> dataplane-Tp1ASr2.log &")


        net["Tp1ASr3"].cmd("source /home/ubuntu/PAR-EMULATOR/bin/activate")
        net["Tp1ASr3"].cmd("/home/ubuntu/PAR-EMULATOR/bin/python /home/ubuntu/git-repos/srv6-controller/grpc/dataplane-manager.py -e /home/ubuntu/git-repos/srv6-controller/grpc/dataplane_manager.env &> dataplane-Tp1ASr3.log &")

        time.sleep(1)
        net["Tp1ASr1"].cmd('ping -c 10 100::4 > Tp1ASr1_out &')
        net["Tp1ASr2"].cmd('ping -c 10 100::4 > Tp1ASr2_out &')
        net["Tp1ASr3"].cmd('ping -c 10 100::4 > Tp1ASr3_out &')

        net["Tp1ASctlr"].cmd("source /home/ubuntu/PAR-EMULATOR/bin/activate")
        net["Tp1ASctlr"].cmd("/home/ubuntu/PAR-EMULATOR/bin/python /home/ubuntu/git-repos/overwatch/bgpcontroller/Controller.py /home/ubuntu/config-Tp1AS.yaml &> controller.log &")

        ## Add monitoring configuration
        net["gameServer"].cmd('ip -6 addr add 55::4/48 dev gameServer-eth0')
        net["gameServer"].cmd('ip -6 addr add 55::5/48 dev gameServer-eth0')

        net["Tp1ASr1"].cmd('ip6tables -t mangle -A PREROUTING -i Tp1ASr1-eth1 -p ipv6-icmp -s 55::4 -j MARK --set-mark 40')
        net["Tp1ASr1"].cmd('ip -6 rule add fwmark 40 table 40')
        net["Tp1ASr1"].cmd('ip -6 route add 2001::/16 encap seg6 mode encap segs 100::2 dev Tp1ASr1-eth0 metric 10 table 40')

        net["Tp1ASr1"].cmd('ip6tables -t mangle -A PREROUTING -i Tp1ASr1-eth1 -p ipv6-icmp -s 55::5 -j MARK --set-mark 50')
        net["Tp1ASr1"].cmd('ip -6 rule add fwmark 50 table 50')
        net["Tp1ASr1"].cmd('ip -6 route add 2001::/16 encap seg6 mode encap segs 100::3 dev Tp1ASr1-eth0 metric 10 table 50')
        with open('path2_current_msm.csv', 'w') as f:
            writer = csv.writer(f, delimiter='|')
            writer.writerow([time.time(),alt_lat[0]])

        #IPCLI(net)
        time.sleep(300)
        start_time = time.time()
        print("%s: Started adding hosts" %(str(datetime.now())))
        def run_game_client_command(i):
            exec(f'net["gCl{i}"].cmd("python simpleGameClient.py -d 300 -c /home/ubuntu/gClient-control-logs/gCL{i}.csv &> /home/ubuntu/gcl-out/gCL{i}.log &")')

        #for i in range(1, 51):
        #    exec(f'net["gCl{i}"].cmd("python simpleGameClient.py -d 300 -c /home/ubuntu/gClient-control-logs/gCL{i}.csv &> /dev/null &")')
        #    net["Tp2ASr1"].cmd("/sbin/tc qdisc change dev Tp2ASr1-eth1 root netem delay {}ms".format(tp2_delay))
        #    net["Tp2ASr2"].cmd("/sbin/tc qdisc change dev Tp2ASr2-eth0 root netem delay {}ms".format(tp2_delay))
        #    t = threading.Thread(target=run_game_client_command, args=(i,))
        #    t.start()

        #file_handlers = []
        #for sock in parsocks:
        #    fifo = os.open(sock, os.O_WRONLY)
        #    file_handlers.append(fifo)

        rtr = "Tp1ASr3"

        hosts_to_run = 50
        hosts_run = 0
        i = 1
        net["gameServer"].cmd("source /home/ubuntu/gufo-ping-updated/bin/activate")
        net["gameServer"].cmd("/home/ubuntu/gufo-ping-updated/bin/python /home/ubuntu/gufoPingMsm.py &> /home/ubuntu/msmModule.log &")
        while hosts_run < hosts_to_run:
            for j in range(i):
                if hosts_run >= hosts_to_run:
                    break
                host_num = hosts_run + 1
                exec(f'net["gCl{host_num}"].cmd("python simpleGameClient.py -d 300 -c /home/ubuntu/gClient-control-logs/gCL{host_num:02}.csv &> /dev/null &")')
                with open('/home/ubuntu/clients.txt', 'a') as file:
                    file.write(f"2001:df{str(host_num).zfill(2)}::1\n")


                print(f'Started game client on host gCl{host_num} at {str(datetime.now())}')
                hosts_run += 1

                #msg = perfmsg.PerformanceMsg()
                #p1 = msg.node.add()
                #p1.name = "Tp1ASr2"
                #p1.address = "100::2"
                #p1.delay = int(tp2_delay)
                #p2 = msg.node.add()
                #p2.name = "Tp1ASr3"
                #p2.address = "100::3"
                #p2.delay = tp3_delay
                #msg_encoded = msg.SerializeToString()
                #msg = create_msg(msg_encoded)

                #for fifo in file_handlers:
                #    os.write(fifo, msg)
                #print("IPMininet sent link delay value to Overwatch at %s" %(str(datetime.now())))

            #net["Tp2ASr1"].cmd("/sbin/tc qdisc change dev Tp2ASr1-eth1 root netem delay {}ms".format(tp2_delay))
            #net["Tp2ASr2"].cmd("/sbin/tc qdisc change dev Tp2ASr2-eth0 root netem delay {}ms".format(tp2_delay))
            time.sleep(60)
            i *= 2 
        print("%s: All hosts added" %(str(datetime.now())))
        #net["gameServer"].cmd("source /home/ubuntu/gufo-ping/bin/activate")
        #net["gameServer"].cmd("/home/ubuntu/gufo-ping/bin/python /home/ubuntu/PingMsmModuleUpdated.py &> /home/ubuntu/msmModule.log &")
        #time.sleep(60)
        while (time.time() - start_time) < 1000:
            # Modify the good path and notify MSM module
            #alt = alt_lat.pop(0)
            #net["Tp3ASr1"].cmd("/sbin/tc qdisc change dev Tp3ASr1-eth1 root netem delay {}ms".format(alt))
            #net["Tp3ASr2"].cmd("/sbin/tc qdisc change dev Tp3ASr2-eth0 root netem delay {}ms".format(alt))
            #with open('path2_current_msm.csv', 'w') as f:
            #    writer = csv.writer(f, delimiter='|')
            #    writer.writerow([time.time(),alt])
            #print("Updated latency for best path and notified MSM module at %s" %(str(datetime.now())))
            time.sleep(60)
        print("%s: End Experiment" %(str(datetime.now())))
    finally:
        net.stop()


#if __name__ == '__main__':
#
#    loop = asyncio.get_event_loop()
#    loop.run_until_complete(run_experiment())
#    loop.close()
