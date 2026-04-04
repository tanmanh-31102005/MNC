#!/usr/bin/env python3
# 03_campus_topology.py

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Node
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from mininet.link import TCLink

class LinuxRouter(Node):
    "A Node with IP forwarding enabled."
    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        self.cmd('sysctl net.ipv4.ip_forward=1')

    def terminate(self):
        self.cmd('sysctl net.ipv4.ip_forward=0')
        super(LinuxRouter, self).terminate()

class CampusTopo(Topo):
    "Topology mạng Campus 3 Layer với Core, Dist, Access và DMZ"
    
    def build(self):
        # 1. Tạo các Router lõi & phân phối (FRR sẽ chạy trên các node này)
        # Bảng IP P2P giữa các router:
        # Core <-> Dist1: 192.168.1.0/30 (Core: .1, Dist1: .2)
        # Core <-> Dist2: 192.168.1.4/30 (Core: .5, Dist2: .6)
        # Core <-> DMZ: 192.168.1.8/30   (Core: .9, DMZ: .10)
        # Core <-> ISP: 192.168.100.0/30 (Core: .1, ISP: .2)

        core = self.addNode('core', cls=LinuxRouter, ip='192.168.1.1/30')
        dist1 = self.addNode('dist1', cls=LinuxRouter, ip='192.168.1.2/30')
        dist2 = self.addNode('dist2', cls=LinuxRouter, ip='192.168.1.6/30')
        dmz_r = self.addNode('dmz_r', cls=LinuxRouter, ip='192.168.1.10/30')
        r_out = self.addNode('r_out', cls=LinuxRouter, ip='192.168.100.2/30')

        # 2. Tạo các Switch Access (Layer 2)
        acc1 = self.addSwitch('acc1')
        acc2 = self.addSwitch('acc2')
        sw_dmz = self.addSwitch('sw_dmz') # Switch dummy cho mạng DMZ
        sw_out = self.addSwitch('sw_out') # Switch dummy cho mạng Internet

        # 3. Tạo các thiết bị End Host
        # Inside Hosts
        h1 = self.addHost('h1', ip='172.16.10.10/24', defaultRoute='via 172.16.10.1')
        h2 = self.addHost('h2', ip='172.16.20.10/24', defaultRoute='via 172.16.20.1')
        
        # DMZ Web Servers
        web1 = self.addHost('web1', ip='10.10.10.11/24', defaultRoute='via 10.10.10.1')
        web2 = self.addHost('web2', ip='10.10.10.12/24', defaultRoute='via 10.10.10.1')
        
        # Outside Host (Internet PC)
        h_out = self.addHost('h_out', ip='203.0.113.100/24', defaultRoute='via 203.0.113.1')

        # ==========================================
        # 4. KẾT NỐI TOPOLOGY VÀ GÁN IP CHO CÁC CỔNG
        # ==========================================
        
        # Core links (Tốc độ cao 1000Mbps, độ trễ thấp)
        self.addLink(core, dist1, intfName1='core-eth1', intfName2='dist1-eth1', params1={'ip': '192.168.1.1/30'}, params2={'ip': '192.168.1.2/30'}, bw=1000, delay='1ms')
        self.addLink(core, dist2, intfName1='core-eth2', intfName2='dist2-eth1', params1={'ip': '192.168.1.5/30'}, params2={'ip': '192.168.1.6/30'}, bw=1000, delay='1ms')
        self.addLink(core, dmz_r, intfName1='core-eth3', intfName2='dmz-eth1', params1={'ip': '192.168.1.9/30'}, params2={'ip': '192.168.1.10/30'}, bw=1000, delay='1ms')
        self.addLink(core, r_out, intfName1='core-eth4', intfName2='rout-eth1', params1={'ip': '192.168.100.1/30'}, params2={'ip': '192.168.100.2/30'}, bw=500, delay='10ms')

        # Distribution -> Access
        self.addLink(dist1, acc1, intfName1='dist1-eth2')
        self.addLink(dist2, acc2, intfName1='dist2-eth2')

        # DMZ Router -> VLAN DMZ / Outside -> ISP switch
        self.addLink(dmz_r, sw_dmz, intfName1='dmz-eth2')
        self.addLink(r_out, sw_out, intfName1='rout-eth2')

        # Hosts -> Access Switches
        self.addLink(h1, acc1)
        self.addLink(h2, acc2)
        
        # Servers -> DMZ Switch
        self.addLink(web1, sw_dmz)
        self.addLink(web2, sw_dmz)

        # Host ISP -> Switch OUT
        self.addLink(h_out, sw_out)

def run():
    topo = CampusTopo()
    # Sử dụng TCLink để hỗ trợ giới hạn băng thông và độ trễ
    net = Mininet(topo=topo, link=TCLink, controller=None)
    
    # Ở đây chúng ta gán IP trực tiếp cho các cổng của Dist và DMZ gắn vào mạng local
    info('*** Cấu hình IP Gateway cho các phòng ban...\n')
    dist1 = net.get('dist1')
    dist1.cmd('ifconfig dist1-eth2 172.16.10.1 netmask 255.255.255.0')
    
    dist2 = net.get('dist2')
    dist2.cmd('ifconfig dist2-eth2 172.16.20.1 netmask 255.255.255.0')
    
    dmz_r = net.get('dmz_r')
    dmz_r.cmd('ifconfig dmz-eth2 10.10.10.1 netmask 255.255.255.0')

    r_out = net.get('r_out')
    r_out.cmd('ifconfig rout-eth2 203.0.113.1 netmask 255.255.255.0')

    net.start()
    info('*** Mạng đã khởi động. Hãy chạy file 04_setup_ospf.sh trên terminal khác để nạp routing.\n')
    info('*** Sau đó chạy 05_acl.sh và 06_nat_config.sh nhé!\n')
    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run()
