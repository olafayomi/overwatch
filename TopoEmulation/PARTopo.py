from ipmininet.iptopo import IPTopo
from ipmininet.cli import IPCLI
from ipmininet.ipnet import IPNet
from ipmininet.router.config.ospf import OSPFRedistributedRoute
from ipmininet.srv6 import enable_srv6
from ipmininet.router.config import BGP, ebgp_session, set_rr, AccessList, \
     AF_INET6, AF_INET, BorderRouterConfig, RouterConfig, OSPF, OSPF6, \
     bgp_peering



class PARTopoDisabled(IPTopo):
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
        as3r1.addDaemon(OSPF, redistribute=[OSPFRedistributedRoute("bgp", 1, 15),])
        as3r1.addDaemon(OSPF6, redistribute=[OSPFRedistributedRoute("bgp", 1, 15),])
        as3r2  = self.bgp('as3r2')
        as3r2.addDaemon(OSPF, redistribute=[OSPFRedistributedRoute("bgp", 1,15),])
        as3r2.addDaemon(OSPF6, redistribute=[OSPFRedistributedRoute("bgp", 1, 15),])
        as3r3  = self.ospf('as3r3')
        as3r4  = self.ospf('as3r4')
        as3r5  = self.ospf('as3r5')
        as3r6  = self.ospf('as3r6')
        as3r7  = self.ospf('as3r7')
        as3r8  = self.bgp('as3r8')
        as3r8.addDaemon(OSPF) # redistribute=[OSPFRedistributedRoute("bgp", 1,15),])
        as3r8.addDaemon(OSPF6)
        as3r9  = self.bgp('as3r9')
        as3r9.addDaemon(OSPF, redistribute=[OSPFRedistributedRoute("bgp", 1,15),])
        as3r9.addDaemon(OSPF6, redistribute=[OSPFRedistributedRoute("bgp", 1, 15),])
        as3r10 = self.bgp('as3r10')
        as3r10.addDaemon(OSPF) # redistribute=[OSPFRedistributedRoute("bgp", 1,15),])
        as3r10.addDaemon(OSPF6)
        #as4r1  = self.bgp('as4r1')
        #as5r1  = self.bgp('as5r1')
        #as6r1  = self.bgp('as6r1')

        # Add hosts
        as6h1 = self.addHost('as6h1')
        as4h1 = self.addHost('as4h1')

        # Add links
        self.addLink(as1r1, as3r1)
        self.addLink(as2r1, as3r2)
        self.addLinks((as3r1, as3r3), (as3r2, as3r4), (as3r3, as3r4),
                      (as3r3, as3r5), (as3r3, as3r6), (as3r4, as3r6),
                      (as3r4, as3r7), (as3r5, as3r6), (as3r5, as3r8),
                      (as3r6, as3r7), (as3r6, as3r9), (as3r7, as3r10))
        self.addLink(as3r8, as4r1)
        self.addLink(as3r9, as5r1)
        self.addLink(as3r10, as5r1)
        self.addLink(as4r1, as4h1)
        self.addLink(as4r1, as6r1)
        self.addLink(as5r1, as6r1)
        self.addLink(as6r1, as6h1)
        self.addAS(1, (as1r1,))
        self.addAS(2, (as2r1,))
        self.addAS(4, (as4r1,))
        self.addAS(5, (as5r1,))
        self.addAS(6, (as6r1,))
        self.addAS(3, (as3r1, as3r2, as3r3, as3r4, as3r5,
                   as3r6, as3r7, as3r8, as3r9, as3r10))
        # Add iBGP peering
        bgp_peering(self, as3r2, as3r10)
        bgp_peering(self, as3r2, as3r8)
        bgp_peering(self, as3r1, as3r8)
        bgp_peering(self, as3r1, as3r9)

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
    net = IPNet(topo=PARTopoDisabled(), use_v4=False)
    try:
        net.start()
        IPCLI(net)
    finally:
        net.stop()
