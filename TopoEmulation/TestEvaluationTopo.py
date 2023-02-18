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

        Tp1ASr1Sw1 = self.addLink(Tp1ASr1, Sw1Tp1)
        Tp1ASr1Sw1[Tp1ASr1].addParams(ip=("100::1/48",))
        Tp1ASr2Sw1 = self.addLink(Tp1ASr2, Sw1Tp1)
        Tp1ASr2Sw1[Tp1ASr2].addParams(ip=("100::2/48",))
        Tp1ASr3Sw1 = self.addLink(Tp1ASr3, Sw1Tp1)
        Tp1ASr3Sw1[Tp1ASr3].addParams(ip=("100::3/48",))

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
        GsRtrLink = self.addLink(gameServer, GsASr1)
        GsRtrLink[gameServer].addParams(ip=("55::1/48",))
        GsRtrLink[GsASr1].addParams(ip=("55::2/48",))

        # Add game client hosts to user network, one host per networt!!!

        for i in range(1, 51):
            exec(f"gCl{i} = self.addHost('gCl{i}')")
            exec(f"gClink{i} = self.addLink(AS{i}R1, gCl{i})")
            ip = f"2001:df{str(i).zfill(2)}::2/48"
            exec(f"gClink{i}[AS{i}R1].addParams(ip=('{ip}',))")
            ip = f"2001:df{str(i).zfill(2)}::1/48"
            exec(f"gClink{i}[gCl{i}].addParams(ip=('{ip}',))")

        self.addLinks((GsASr1, Tp1ASr1), (Tp2ASr2, Tp4ASr1),
                      (Tp3ASr2, Tp4ASr1))

        link_delay = 8.0

        for i in range(1, 51):
            link = self.addLink(Tp4ASr1, eval("AS{}R1".format(i)),
                                delay="{}ms".format(link_delay/2))
            link_delay += 0.1

        self.addAS(55, (GsASr1,))
        self.addAS(100, (Tp1ASr1, Tp1ASr2, Tp1ASr3))
        self.addAS(200, (Tp2ASr1, Tp2ASr2))
        self.addAS(300, (Tp3ASr1, Tp3ASr2))
        self.addAS(400, (Tp4ASr1,))

        for i in range(1, 51):
            exec(f"self.addAS(i, (AS{i}R1,))")

        bgp_peering(self, Tp1ASr1, Tp1ASr2)
        bgp_peering(self, Tp1ASr1, Tp1ASr3)

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

        ebgp_session(self, Tp1ASr2, Tp2ASr1)
        ebgp_session(self, Tp1ASr3, Tp3ASr1)

        # Prefer return path from clients via Tp3 or Tp2
        Tp4ASr1.get_config(BGP).set_local_pref(200, from_peer=Tp2ASr2,
                                               matching=(acl4,acl))
        Tp4ASr1.get_config(BGP).set_local_pref(100, from_peer=Tp3ASr2,
                                               matching=(acl4,acl))
        ebgp_session(self, Tp4ASr1, Tp2ASr2) #, link_type=CLIENT_PROVIDER)
        ebgp_session(self, Tp4ASr1, Tp3ASr2) #, link_type=CLIENT_PROVIDER)


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
        tp2_delay = (min(tp2_rtt))/2
        # set tp3 delay to 5ms (to make  10ms rtt) to catch any odd behaviour
        tp3_delay = 5
        #tp3_delay = (min(tp3_rtt))/2
        net.modifyLink(net["Tp2ASr1"], net["Tp2ASr2"],
                       params1={"delay": "{}ms".format(tp2_delay)},
                       params2={"delay": "{}ms".format(tp2_delay)})
        net.modifyLink(net["Tp3ASr1"], net["Tp3ASr2"],
                       params1={"delay": "{}ms".format(tp3_delay)},
                       params2={"delay": "{}ms".format(tp3_delay)})
        print(f'Delay set on Tp2 link is {tp2_delay}ms and RTT should be above {min(tp2_rtt)}ms')
        print(f'Delay set on Tp3 link is {tp3_delay}ms and RTT should be less than {min(tp3_rtt)}ms')
        #def run_game_server():
        #    exec(f'net["gameServer"].cmd("python gameServer.py &> /home/ubuntu/gcl-out/gServer.log &")')
        #game_server_thread = threading.Thread(target=run_game_server)
        #game_server_thread.start()
        #net["gameServer"].cmd("python gameServer.py &> /home/ubuntu/gcl-out/gServer.log &")
        #IPCLI(net)
        net["gameServer"].cmd("python gameServer.py &> /dev/null &")
        time.sleep(260)
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

        hosts_to_run = 50
        hosts_run = 0
        i = 1
        while hosts_run < hosts_to_run:
            for j in range(i):
                if hosts_run >= hosts_to_run:
                    break
                host_num = hosts_run + 1
                exec(f'net["gCl{host_num}"].cmd("python simpleGameClient.py -d 300 -c /home/ubuntu/gClient-control-logs/gCL{host_num:02}.csv &> /dev/null &")')
                print(f'Started game client on host gCl{host_num}')
                hosts_run += 1
            #net["Tp2ASr1"].cmd("/sbin/tc qdisc change dev Tp2ASr1-eth1 root netem delay {}ms".format(tp2_delay))
            #net["Tp2ASr2"].cmd("/sbin/tc qdisc change dev Tp2ASr2-eth0 root netem delay {}ms".format(tp2_delay))
            time.sleep(60)
            i *= 2 


        print("%s: All hosts added" %(str(datetime.now())))
        while (time.time() - start_time) < 1200:
            time.sleep(60)
        print("%s: End Experiment" %(str(datetime.now())))
    finally:
        net.stop()


#if __name__ == '__main__':
#
#    loop = asyncio.get_event_loop()
#    loop.run_until_complete(run_experiment())
#    loop.close()
