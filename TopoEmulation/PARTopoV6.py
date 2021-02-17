from ipmininet.iptopo import IPTopo
from ipmininet.cli import IPCLI
from ipmininet.ipnet import IPNet
from ipmininet.router.config.ospf import OSPFRedistributedRoute
from ipmininet.srv6 import enable_srv6
from ipmininet.router.config import BGP, ebgp_session, set_rr, AccessList, \
     AF_INET6, AF_INET, BorderRouterConfig, RouterConfig, OSPF, OSPF6, \
     bgp_peering, ExaBGPDaemon, STATIC, StaticRoute
from ipmininet.link import IPLink


class PARTopo(IPTopo):
    """The topology is composed of six ASes. Out of the six ASes, three are
    transit ASes while the rest are stubs. One of the transit ASes (AS3) is the
    provider for two of the three stub ASes and has p2p/p2c connection
    with the other two transit ASes. The two transit ASes (AS4 and AS5) are
    providers for  the third stub AS (AS6). The peering between AS3 and AS4
    and AS5 provides multiple paths to reach AS6. This topology is to represent
    and depict the default BGP state when PAR is not enabled on AS3 and which
    routes to AS6 is selected and advertised by AS3 to AS1 and AS2."""

    def build(self, *args, **kwargs):
        # Add all routers
        #as1r1  = self.bgp('as1r1')
        #as2r1  = self.bgp('as2r1')
        as1r1, as2r1, as4r1, as5r1, as6r1 = self.addRouters(
                "as1r1", "as2r1", "as4r1", "as5r1", "as6r1",
                config=RouterConfig)

        as1r1.addDaemon(BGP, address_families=(
            AF_INET(redistribute=('connected',)),
            AF_INET6(redistribute=('connected',))))
        #as1r1.addDaemon(OSPF, redistribute=[OSPFRedistributedRoute("bgp", 1, 15),])

        as2r1.addDaemon(BGP, address_families=(
            AF_INET(redistribute=('connected',)),
            AF_INET6(redistribute=('connected',))))
        #as2r1.addDaemon(OSPF, redistribute=[OSPFRedistributedRoute("bgp", 1, 15),])

        as4r1.addDaemon(BGP, address_families=(
            AF_INET(redistribute=('connected',)),
            AF_INET6(redistribute=('connected',))))

        as5r1.addDaemon(BGP, address_families=(
            AF_INET(redistribute=('connected',)),
            AF_INET6(redistribute=('connected',))))

        as6r1.addDaemon(BGP, address_families=(
            AF_INET(redistribute=('connected',)),
            AF_INET6(redistribute=('connected',))))
        #as6r1.addDaemon(OSPF, redistribute=[OSPFRedistributedRoute("bgp", 1, 15),])

        as3r1  = self.bgp('as3r1')
        as3r1.addDaemon(OSPF, redistribute=[OSPFRedistributedRoute("bgp", 2, 15),])
        as3r1.addDaemon(OSPF6, redistribute=[OSPFRedistributedRoute("bgp", 2, 15),])
        as3r2  = self.bgp('as3r2')
        as3r2.addDaemon(OSPF, redistribute=[OSPFRedistributedRoute("bgp", 2,15),])
        as3r2.addDaemon(OSPF6, redistribute=[OSPFRedistributedRoute("bgp", 2, 15),])

        as3r3  = self.ospf('as3r3')
        as3r4  = self.ospf('as3r4')
        as3r5  = self.ospf('as3r5')
        as3r6  = self.ospf('as3r6')
        as3r7  = self.ospf('as3r7')
        
        as3r8  = self.bgp('as3r8')
        as3r8.addDaemon(OSPF) # redistribute=[OSPFRedistributedRoute("bgp", 1,15),])
        as3r8.addDaemon(OSPF6)

        as3r9  = self.bgp('as3r9')
        as3r9.addDaemon(OSPF, redistribute=[OSPFRedistributedRoute("bgp", 2,15),])
        as3r9.addDaemon(OSPF6, redistribute=[OSPFRedistributedRoute("bgp", 2, 15),])

        as3r10 = self.bgp('as3r10')
        as3r10.addDaemon(OSPF) # redistribute=[OSPFRedistributedRoute("bgp", 1,15),])
        as3r10.addDaemon(OSPF6)

        as3sw1 = self.addSwitch('as3sw1') 

        #as4r1  = self.bgp('as4r1')
        #as5r1  = self.bgp('as5r1')
        #as6r1  = self.bgp('as6r1')
        # Add hosts
        as6h1 = self.addHost('as6h1')
        as6h2 = self.addHost('as6h2')
        as4h1 = self.addHost('as4h1')

        # Add links
        as1as3 = self.addLink(as1r1, as3r1)
        
        as2as3 = self.addLink(as2r1, as3r2)
        as2as3[as2r1].addParams(ip=("2001:df8::1/48",)) 
        as2as3[as3r2].addParams(ip=("2001:df8::2/48",))

        # AS3R3 and AS3R4 links
        as3r1sw = self.addLink(as3r1, as3sw1)
        as3r1sw[as3r1].addParams(ip=("2001:df40::3/48",))

        as3r3sw = self.addLink(as3r3, as3sw1)
        as3r3sw[as3r3].addParams(ip=("2001:df40::11/48",)) 

        as3r2sw = self.addLink(as3r2, as3sw1)
        as3r2sw[as3r2].addParams(ip=("2001:df40::2/48",))

        as3r4sw = self.addLink(as3r4, as3sw1)
        as3r4sw[as3r4].addParams(ip=("2001:df40::9/48",))

        # Add Controller and ExaBGP node 
        as3c1 = self.addRouter("as3c1", config=RouterConfig)
        as3c1sw = self.addLink(as3c1, as3sw1)
        as3c1sw[as3c1].addParams(ip=("2001:df40::1/48",))
        as3c1.addDaemon(ExaBGPDaemon, env = { 'api' : {'cli':'true', 'encoder':'json',
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

        as3c1.addDaemon(OSPF) #redistribute=[OSPFRedistributedRoute("bgp", 2,15),])
        as3c1.addDaemon(OSPF6)# redistribute=[OSPFRedistributedRoute("bgp", 2,15),]) 
        
        # Add node to redistribute BGP into OSPF
        #as3dis = self.addRouter("as3dis", config=RouterConfig)
        #as3dissw = self.addLink(as3dis, as3sw1)
        #as3dissw[as3dis].addParams(ip=("2001:df40::20/48",))
        #as3dissw[as3dis].addParams(igp_passive=True)
        #as3dis.addDaemon(BGP)
        #as3dis.addDaemon(OSPF, redistribute=[OSPFRedistributedRoute("bgp",2,15),])
        #as3dis.addDaemon(OSPF6, redistribute=[OSPFRedistributedRoute("bgp",2,15),])
        ## Add link between AS3Dis and AS3R6
        #as3disr6 = self.addLink(as3dis,as3r6)
        #as3disr6[as3dis].addParams(ip=("2001:df39::1/48",))
        #as3disr6[as3r6].addParams(ip=("2001:df39::2/48",))


        #as3c1.addDaemon(STATIC,
        #        static_routes=[StaticRoute("::/0", "2001:df40::9"),])



        as3r3r4 = self.addLink(as3r3, as3r4)
        as3r3r4[as3r3].addParams(ip=("2001:df38::1/48",))
        as3r3r4[as3r4].addParams(ip=("2001:df38::2/48",))

        #All AS3R5, AS3R6, AS3R7 links 
        as3r7r10 = self.addLink(as3r7, as3r10)
        as3r7r10[as3r7].addParams(ip=("2001:df35::5/48",))
        as3r7r10[as3r10].addParams(ip=("2001:df35::36/48",))

        as3r7r4 = self.addLink(as3r7, as3r4)
        as3r7r4[as3r4].addParams(ip=("2001:df37::2/48",))
        as3r7r4[as3r7].addParams(ip=("2001:df37::5/48",))
        
        as3r6r9 = self.addLink(as3r6, as3r9)
        as3r6r9[as3r6].addParams(ip=("2001:df36::4/48",))
        as3r6r9[as3r9].addParams(ip=("2001:df36::34/48",))

        as3r6r7 = self.addLink(as3r6, as3r7)
        as3r6r7[as3r6].addParams(ip=("2001:df33::4/48",))
        as3r6r7[as3r7].addParams(ip=("2001:df33::5/48",))

        as3r6r4 = self.addLink(as3r6, as3r4)
        as3r6r4[as3r4].addParams(ip=("2001:df34::2/48",))
        as3r6r4[as3r6].addParams(ip=("2001:df34::4/48",))

        as3r6r3 = self.addLink(as3r6, as3r3)
        as3r6r3[as3r3].addParams(ip=("2001:df32::1/48",))
        as3r6r3[as3r6].addParams(ip=("2001:df32::4/48",))
        
        as3r5r3 = self.addLink(as3r5, as3r3)
        as3r5r3[as3r5].addParams(ip=("2001:df30::3/48",))
        as3r5r3[as3r3].addParams(ip=("2001:df30::1/48",))

        as3r5r6 = self.addLink(as3r5, as3r6)
        as3r5r6[as3r5].addParams(ip=("2001:df31::3/48",))
        as3r5r6[as3r6].addParams(ip=("2001:df31::4/48",))

        as3r5r8 = self.addLink(as3r5, as3r8)
        as3r5r8[as3r5].addParams(ip=("2001:df23::13/48",))
        as3r5r8[as3r8].addParams(ip=("2001:df23::32/48",))

        # AS3R8, AS3R9, AS3R10 links (Lower end border routers to external)
        as3r8as4 = self.addLink(as3r8, as4r1)
        as3r8as4[as3r8].addParams(ip=("2001:1664:4::98/124", "16.64.4.98/29"))
        as3r8as4[as4r1].addParams(ip=("2001:1664:4::97/124", "16.64.4.97/29"))
        
        as3r9as5 = self.addLink(as3r9, as5r1)
        as3r9as5[as3r9].addParams(ip=("2001:1764:4::97/124", "17.64.4.97/30"))
        as3r9as5[as5r1].addParams(ip=("2001:1764:4::98/124", "17.64.4.98/30"))

        as3r10as5 = self.addLink(as3r10, as5r1)
        as3r10as5[as3r10].addParams(ip=("2001:1864:4::97/124", "18.64.4.97/30"))
        as3r10as5[as5r1].addParams(ip=("2001:1864:4::98/124", "18.64.4.98/30"))

        # AS4, AS5 and AS6 links and addresses
        as4r1h1 = self.addLink(as4r1, as4h1)
        as4r1h1[as4r1].addParams(ip=("2001:1001:1::1/48", "100.1.1.1/24"))
        as4r1h1[as4h1].addParams(ip=("2001:1001:1::2/48", "100.1.1.2/24"))
        
        as4as6 = self.addLink(as4r1, as6r1)
        as4as6[as4r1].addParams(ip=("2001:1464:4::97/124", "14.64.4.97/30"))
        as4as6[as6r1].addParams(ip=("2001:1464:4::98/124", "14.64.4.98/30"))

        as5as6 = self.addLink(as5r1, as6r1)
        as5as6[as5r1].addParams(ip=("2001:1564:4::98/124", "15.64.4.98/30"))
        as5as6[as6r1].addParams(ip=("2001:1564:4::97/124", "15.64.4.97/30"))
        
        as6r1h1 = self.addLink(as6r1, as6h1)
        as6r1h1[as6r1].addParams(ip=("2001:4521::1/48", "45.2.1.1/24"))
        as6r1h1[as6h1].addParams(ip=("2001:4521::2/48", "45.2.1.2/24"))

        as6r1h2 = self.addLink(as6r1, as6h2)
        as6r1h2[as6r1].addParams(ip=("2001:3320::1/48", "33.2.0.1/24"))
        as6r1h2[as6h2].addParams(ip=("2001:3320::2/48", "33.2.0.2/24"))

        self.addAS(1, (as1r1,))
        self.addAS(2, (as2r1,))
        self.addAS(4, (as4r1,))
        self.addAS(5, (as5r1,))
        self.addAS(6, (as6r1,))
        self.addAS(3, (as3r1, as3r2, as3r3, as3r4, as3r5,
                   as3r6, as3r7, as3r8, as3r9, as3r10, as3c1))
        
        # controller peering
        bgp_peering(self, as3r2, as3c1)
        bgp_peering(self, as3r8, as3c1)
        bgp_peering(self, as3r10, as3c1)
        bgp_peering(self, as3r1, as3c1) 
        bgp_peering(self, as3r9, as3c1)

        # Add eBGP peering
        ebgp_session(self, as1r1, as3r1)
        ebgp_session(self, as2r1, as3r2)
        ebgp_session(self, as3r8, as4r1)
        ebgp_session(self, as3r9, as5r1)
        ebgp_session(self, as3r10, as5r1)
        ebgp_session(self, as4r1, as6r1)
        ebgp_session(self, as5r1, as6r1)


        # Build
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

    def ospf(self, name):
        r = self.addRouter(name, config=RouterConfig)
        r.addDaemon(OSPF)
        r.addDaemon(OSPF6)
        return r


if __name__ == '__main__':
    net = IPNet(topo=PARTopo(), use_v4=False)
    # Add a separate routing for PAR on the PAR-enabled nodes, if not added
    net["as3r2"].cmd("grep  -qxF '201 par.out' /etc/iproute2/rt_tables || echo '201 par.out' >> /etc/iproute2/rt_tables")
    net["as3r2"].cmd("ip -6 rule add fwmark 2 table par.out")

    try:
        net.start()
        #links = net.links 
        linksbet = net.linksBetween(net["as2r1"], net["as3r2"])
        
        for link in linksbet:
            print(link.status())
            linkName = link.__str__()
            intfNames = linkName.split("<->")
            for intfName in intfNames:
                if "as3r2" in intfName:
                    net["as3r2"].cmd("ip6tables -t mangle -A PREROUTING -i "+intfName+" -p tcp --dport 465 -j MARK --set-mark 2")

        net["as3r2"].cmd("source /home/ubuntu/PAR-EMULATOR/bin/activate")
        net["as3r2"].cmd("/home/ubuntu/PAR-EMULATOR/bin/python  /home/ubuntu/git-repos/srv6-controller/grpc/dataplane_grpc_server.py -a 2001:df40::2 -i as3r2-eth1 &> dataplane-as3r2.log &")

        net["as3r1"].cmd("source /home/ubuntu/PAR-EMULATOR/bin/activate")
        net["as3r1"].cmd("/home/ubuntu/PAR-EMULATOR/bin/python  /home/ubuntu/git-repos/srv6-controller/grpc/dataplane_grpc_server.py -a 2001:df40::3 -i as3r1-eth1 &> dataplane-as3r1.log &")


        net["as3r8"].cmd("source /home/ubuntu/PAR-EMULATOR/bin/activate")
        net["as3r8"].cmd("/home/ubuntu/PAR-EMULATOR/bin/python  /home/ubuntu/git-repos/srv6-controller/grpc/dataplane_grpc_server.py -a 2001:df23::32 -i as3r8-eth0 &> dataplane-as3r8.log &")

        net["as3r9"].cmd("source /home/ubuntu/PAR-EMULATOR/bin/activate")
        net["as3r9"].cmd("/home/ubuntu/PAR-EMULATOR/bin/python  /home/ubuntu/git-repos/srv6-controller/grpc/dataplane_grpc_server.py -a 2001:df36::34 -i as3r9-eth0 &> dataplane-as3r9.log &")

        net["as3r10"].cmd("source /home/ubuntu/PAR-EMULATOR/bin/activate")
        net["as3r10"].cmd("/home/ubuntu/PAR-EMULATOR/bin/python  /home/ubuntu/git-repos/srv6-controller/grpc/dataplane_grpc_server.py -a 2001:df35::36 -i as3r10-eth0 &> dataplane-as3r10.log &")

        net["as3c1"].cmd("source /home/ubuntu/PAR-EMULATOR/bin/activate")
        net["as3c1"].cmd("/home/ubuntu/PAR-EMULATOR/bin/python /home/ubuntu/git-repos/overwatch/bgpcontroller/Controller.py /home/ubuntu/config-as3-new.yaml &> controller.log &")
        IPCLI(net)
    finally:
        net.stop()
