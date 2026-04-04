#!/usr/bin/env python3
# =============================================================================
# topology.py – Campus 3-Layer Network (Core / Distribution / Access + DMZ)
# Bài Tập 3: Tối ưu hóa bảo mật đa lớp và cân bằng tải
# =============================================================================
# Cách chạy:
#   sudo python3 topology.py [--acl] [--nat] [--lb]
#
#   --acl : Áp dụng ACL + Firewall khi mạng khởi động
#   --nat : Áp dụng NAT / PAT khi mạng khởi động
#   --lb  : Bật script giám sát tải (load_balancer) nền
# =============================================================================

import os
import sys
import time
import subprocess
import argparse
import signal
from mininet.topo  import Topo
from mininet.net   import Mininet
from mininet.node  import Node
from mininet.log   import setLogLevel, info, error
from mininet.cli   import CLI
from mininet.link  import TCLink

# ─────────────────────────────────────────────────────────────────────────────
# 0. Thiết lập tham số dòng lệnh
# ─────────────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description='Campus 3-Layer Topology')
parser.add_argument('--acl', action='store_true', help='Apply ACL+Firewall rules on startup')
parser.add_argument('--nat', action='store_true', help='Apply NAT/PAT rules on startup')
parser.add_argument('--lb',  action='store_true', help='Start load balancer monitor in background')
args, unknown = parser.parse_known_args()

# ─────────────────────────────────────────────────────────────────────────────
# 1. Định nghĩa Linux Router (forwarding enabled)
# ─────────────────────────────────────────────────────────────────────────────
class LinuxRouter(Node):
    """Node Mininet hoạt động như Linux router (ip_forward = 1)."""

    def config(self, **params):
        super().config(**params)
        self.cmd('sysctl -w net.ipv4.ip_forward=1')

    def terminate(self):
        self.cmd('sysctl -w net.ipv4.ip_forward=0')
        super().terminate()


# ─────────────────────────────────────────────────────────────────────────────
# 2. Topology Campus 3 Lớp
# ─────────────────────────────────────────────────────────────────────────────
#
#  ┌────────────────────────────────────────────────────────────────────────┐
#  │  OUTSIDE (ISP)                                                         │
#  │   r_out (203.0.113.0/30)  ──  h_out (203.0.113.100)                   │
#  └──────────────────────────────┬─────────────────────────────────────────┘
#                                 │ rout-eth1  ↔  core-eth4 (192.168.100.0/30)
#  ┌──────────────────────────────┴─────────────────────────────────────────┐
#  │  CORE LAYER                                                             │
#  │   core (loopback 10.255.0.1)                                           │
#  │   ├── core-eth1 ──► dist1   (192.168.1.0/30)                          │
#  │   ├── core-eth2 ──► dist2   (192.168.1.4/30)                          │
#  │   ├── core-eth3 ──► dmz_r  (192.168.1.8/30)                          │
#  │   └── core-eth4 ──► r_out  (192.168.100.0/30)                        │
#  └──────────────────────────────┬─────────────────────────────────────────┘
#            ┌────────────────────┤
#  ┌─────────┴──────────┐  ┌──────┴──────────┐  ┌──────────────────────────┐
#  │ DISTRIBUTION 1     │  │ DISTRIBUTION 2  │  │ DMZ ZONE                 │
#  │  dist1             │  │  dist2          │  │  dmz_r                   │
#  │  VLAN10:172.16.10  │  │  VLAN20:172.16.20│  │  10.10.10.0/24           │
#  └────────┬───────────┘  └───────┬─────────┘  │  web1: 10.10.10.11       │
#  ┌────────┴────────────────────┐ │             │  web2: 10.10.10.12       │
#  │ ACCESS 1         ACCESS 2  │ │             └──────────────────────────┘
#  │  acc1  ──h1      acc2──h2  │ │
#  └────────────────────────────┘─┘
#
# ─────────────────────────────────────────────────────────────────────────────

class CampusTopo(Topo):
    """Topology mạng Campus 3 lớp: Core – Distribution – Access + DMZ + Outside."""

    def build(self):
        # ── Routers (LinuxRouter) ─────────────────────────────────────────
        # IP gán ở đây chỉ để tạo node; interface IP được gán lại trong run()
        core  = self.addNode('core',  cls=LinuxRouter, ip='192.168.1.1/30')
        dist1 = self.addNode('dist1', cls=LinuxRouter, ip='192.168.1.2/30')
        dist2 = self.addNode('dist2', cls=LinuxRouter, ip='192.168.1.6/30')
        dmz_r = self.addNode('dmz_r', cls=LinuxRouter, ip='192.168.1.10/30')
        r_out = self.addNode('r_out', cls=LinuxRouter, ip='192.168.100.2/30')

        # ── Access Switches (Layer 2) ─────────────────────────────────────
        acc1   = self.addSwitch('acc1',   dpid='0000000000000001', failMode='standalone')
        acc2   = self.addSwitch('acc2',   dpid='0000000000000002', failMode='standalone')
        sw_dmz = self.addSwitch('sw_dmz', dpid='0000000000000003', failMode='standalone')
        sw_out = self.addSwitch('sw_out', dpid='0000000000000004', failMode='standalone')

        # ── End Hosts ─────────────────────────────────────────────────────
        # Inside – VLAN 10 (phòng Kỹ thuật)
        h1 = self.addHost('h1', ip='172.16.10.10/24', defaultRoute='via 172.16.10.1')
        # Inside – VLAN 20 (phòng Kinh doanh)
        h2 = self.addHost('h2', ip='172.16.20.10/24', defaultRoute='via 172.16.20.1')
        # IP Phone (VLAN 20 – cùng phân đoạn Dist2, khác thiết bị)
        phone1 = self.addHost('phone1', ip='172.16.20.20/24', defaultRoute='via 172.16.20.1')
        # IP Printer (Access 1 – VLAN 10)
        printer1 = self.addHost('printer1', ip='172.16.10.30/24', defaultRoute='via 172.16.10.1')

        # DMZ Web Servers
        web1 = self.addHost('web1', ip='10.10.10.11/24', defaultRoute='via 10.10.10.1')
        web2 = self.addHost('web2', ip='10.10.10.12/24', defaultRoute='via 10.10.10.1')

        # Outside / Internet
        h_out = self.addHost('h_out', ip='203.0.113.100/24', defaultRoute='via 203.0.113.1')

        # ── Links – Core Backbone (Gb uplink) ─────────────────────────────
        # bw=1000 Mbps, delay 1 ms (mô phỏng Fast Ethernet nội bộ)
        self.addLink(
            core, dist1,
            intfName1='core-eth1', intfName2='dist1-eth1',
            params1={'ip': '192.168.1.1/30'}, params2={'ip': '192.168.1.2/30'},
            bw=1000, delay='1ms', use_htb=True)

        self.addLink(
            core, dist2,
            intfName1='core-eth2', intfName2='dist2-eth1',
            params1={'ip': '192.168.1.5/30'}, params2={'ip': '192.168.1.6/30'},
            bw=1000, delay='1ms', use_htb=True)

        self.addLink(
            core, dmz_r,
            intfName1='core-eth3', intfName2='dmz-eth1',
            params1={'ip': '192.168.1.9/30'}, params2={'ip': '192.168.1.10/30'},
            bw=1000, delay='1ms', use_htb=True)

        # WAN uplink – thấp hơn (500 Mbps, 10 ms mô phỏng ISP)
        self.addLink(
            core, r_out,
            intfName1='core-eth4', intfName2='rout-eth1',
            params1={'ip': '192.168.100.1/30'}, params2={'ip': '192.168.100.2/30'},
            bw=500, delay='10ms', use_htb=True)

        # ── Links – Distribution → Access ────────────────────────────────
        self.addLink(dist1, acc1,   intfName1='dist1-eth2', bw=100, delay='2ms', use_htb=True)
        self.addLink(dist2, acc2,   intfName1='dist2-eth2', bw=100, delay='2ms', use_htb=True)
        self.addLink(dmz_r, sw_dmz, intfName1='dmz-eth2',  bw=1000, delay='1ms', use_htb=True)
        self.addLink(r_out, sw_out, intfName1='rout-eth2', bw=500, delay='10ms', use_htb=True)

        # ── Links – Hosts → Access Switches ──────────────────────────────
        self.addLink(h1,       acc1,   bw=100, delay='2ms', use_htb=True)
        self.addLink(printer1, acc1,   bw=100, delay='2ms', use_htb=True)
        self.addLink(h2,       acc2,   bw=100, delay='2ms', use_htb=True)
        self.addLink(phone1,   acc2,   bw=100, delay='2ms', use_htb=True)
        self.addLink(web1,     sw_dmz, bw=1000, delay='1ms', use_htb=True)
        self.addLink(web2,     sw_dmz, bw=1000, delay='1ms', use_htb=True)
        self.addLink(h_out,    sw_out, bw=500, delay='10ms', use_htb=True)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Cấu hình IP Gateway và định tuyến tĩnh
# ─────────────────────────────────────────────────────────────────────────────

def configure_interfaces(net):
    """Gán IP cho các cổng Access (gateway của từng VLAN)."""
    info('*** [CONFIG] Gán IP gateway cho các interface Access...\n')

    dist1 = net.get('dist1')
    dist1.cmd('ip addr add 172.16.10.1/24 dev dist1-eth2')

    dist2 = net.get('dist2')
    dist2.cmd('ip addr add 172.16.20.1/24 dev dist2-eth2')

    dmz_r = net.get('dmz_r')
    dmz_r.cmd('ip addr add 10.10.10.1/24 dev dmz-eth2')

    r_out = net.get('r_out')
    r_out.cmd('ip addr add 203.0.113.1/24 dev rout-eth2')


def configure_static_routes(net):
    """
    Cấu hình định tuyến tĩnh trong khi chờ OSPF hội tụ.
    Trong thực tế bạn sẽ thay bằng FRR/OSPF; đây là fallback
    giúp bài demo vẫn ping được ngay sau khi khởi động.
    """
    info('*** [CONFIG] Cấu hình định tuyến tĩnh (static routes)...\n')

    core  = net.get('core')
    dist1 = net.get('dist1')
    dist2 = net.get('dist2')
    dmz_r = net.get('dmz_r')
    r_out = net.get('r_out')

    # Core biết tất cả mạng con
    core.cmd('ip route add 172.16.10.0/24 via 192.168.1.2')   # qua dist1
    core.cmd('ip route add 172.16.20.0/24 via 192.168.1.6')   # qua dist2
    core.cmd('ip route add 10.10.10.0/24  via 192.168.1.10')  # qua dmz_r
    core.cmd('ip route add 203.0.113.0/24 via 192.168.100.2') # qua r_out

    # Dist1 – biết default và mạng ngược lại
    dist1.cmd('ip route add default via 192.168.1.1')
    dist1.cmd('ip route add 172.16.20.0/24 via 192.168.1.1')
    dist1.cmd('ip route add 10.10.10.0/24  via 192.168.1.1')
    dist1.cmd('ip route add 203.0.113.0/24 via 192.168.1.1')

    # Dist2
    dist2.cmd('ip route add default via 192.168.1.5')
    dist2.cmd('ip route add 172.16.10.0/24 via 192.168.1.5')
    dist2.cmd('ip route add 10.10.10.0/24  via 192.168.1.5')
    dist2.cmd('ip route add 203.0.113.0/24 via 192.168.1.5')

    # DMZ Router
    dmz_r.cmd('ip route add default via 192.168.1.9')
    dmz_r.cmd('ip route add 172.16.10.0/24 via 192.168.1.9')
    dmz_r.cmd('ip route add 172.16.20.0/24 via 192.168.1.9')
    dmz_r.cmd('ip route add 203.0.113.0/24 via 192.168.1.9')

    # r_out (biên) – biết mạng nội bộ qua core
    r_out.cmd('ip route add 172.16.0.0/16  via 192.168.100.1')
    r_out.cmd('ip route add 10.10.10.0/24  via 192.168.100.1')
    r_out.cmd('ip route add 192.168.1.0/24 via 192.168.100.1')

    info('    [OK] Static routes đã cấu hình.\n')


# ─────────────────────────────────────────────────────────────────────────────
# 4. NAT / PAT
# ─────────────────────────────────────────────────────────────────────────────

def apply_nat(net):
    """
    PAT (MASQUERADE) cho Inside → Outside
    Static NAT (DNAT) cho Outside → DMZ Server
    """
    info('*** [NAT] Áp dụng PAT + Static NAT...\n')
    r_out = net.get('r_out')

    # ── Cho phép forward iptables ────────────────────────────────────────
    r_out.cmd('iptables -P FORWARD ACCEPT')

    # ── PAT: tất cả mạng nội bộ ra Internet ────────────────────────────
    r_out.cmd('iptables -t nat -A POSTROUTING -s 172.16.0.0/16 -o rout-eth2 -j MASQUERADE')
    r_out.cmd('iptables -t nat -A POSTROUTING -s 10.10.10.0/24 -o rout-eth2 -j MASQUERADE')
    r_out.cmd('iptables -t nat -A POSTROUTING -s 192.168.0.0/16 -o rout-eth2 -j MASQUERADE')

    # ── Static NAT: thêm IP Public ảo lên rout-eth2 ────────────────────
    r_out.cmd('ip addr add 203.0.113.10/24 dev rout-eth2 2>/dev/null || true')
    r_out.cmd('ip addr add 203.0.113.11/24 dev rout-eth2 2>/dev/null || true')

    # DNAT: 203.0.113.10 → web1 (10.10.10.11)
    r_out.cmd('iptables -t nat -A PREROUTING -d 203.0.113.10 -p tcp --dport 80  -j DNAT --to-destination 10.10.10.11:80')
    r_out.cmd('iptables -t nat -A PREROUTING -d 203.0.113.10 -p tcp --dport 443 -j DNAT --to-destination 10.10.10.11:443')

    # DNAT: 203.0.113.11 → web2 (10.10.10.12)
    r_out.cmd('iptables -t nat -A PREROUTING -d 203.0.113.11 -p tcp --dport 80  -j DNAT --to-destination 10.10.10.12:80')
    r_out.cmd('iptables -t nat -A PREROUTING -d 203.0.113.11 -p tcp --dport 443 -j DNAT --to-destination 10.10.10.12:443')

    # LOG NAT events (dùng để parse bảng thống kê sau)
    r_out.cmd('iptables -t nat -A POSTROUTING -j LOG --log-prefix "NAT_EVENT: " --log-level 4')

    info('    [OK] NAT/PAT đã áp dụng.\n')


def show_nat_table(net):
    """In bảng NAT (conntrack) dưới dạng text ra stdout."""
    r_out = net.get('r_out')
    info('\n*** [NAT TABLE] Bảng conntrack hiện tại trên r_out:\n')
    out = r_out.cmd('conntrack -L -n 2>/dev/null || echo "conntrack chưa cài, dùng: apt install conntrack"')
    print(out)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Tích hợp acl.sh / dropacl.sh
# ─────────────────────────────────────────────────────────────────────────────

def apply_acl(net):
    """
    Gọi acl.sh (nằm cùng thư mục với topology.py) để áp ACL.
    acl.sh dùng 'ip netns exec <pid>' hoặc được gọi sau khi Mininet
    đã khởi động nên dùng subprocess tới các namespace.
    """
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'acl.sh')
    if not os.path.exists(script):
        error(f'[ACL] Không tìm thấy {script}!\n')
        return

    info('*** [ACL] Áp dụng ACL + Firewall từ acl.sh...\n')
    # Truyền PID của các router để acl.sh dùng nsenter
    pids = {
        'DIST1_PID': str(net.get('dist1').pid),
        'DIST2_PID': str(net.get('dist2').pid),
        'DMZ_R_PID': str(net.get('dmz_r').pid),
        'R_OUT_PID': str(net.get('r_out').pid),
    }
    env = {**os.environ, **pids}
    result = subprocess.run(['bash', script], env=env, capture_output=True, text=True)
    if result.returncode == 0:
        info('    [OK] ACL áp dụng thành công.\n')
    else:
        error(f'    [ERR] acl.sh lỗi:\n{result.stderr}\n')

def drop_acl(net):
    """Gọi dropacl.sh để bãi bỏ toàn bộ ACL."""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dropacl.sh')
    if not os.path.exists(script):
        error(f'[ACL] Không tìm thấy {script}!\n')
        return
    info('*** [ACL] Bãi bỏ ACL từ dropacl.sh...\n')
    pids = {
        'DIST1_PID': str(net.get('dist1').pid),
        'DIST2_PID': str(net.get('dist2').pid),
        'DMZ_R_PID': str(net.get('dmz_r').pid),
        'R_OUT_PID': str(net.get('r_out').pid),
    }
    env = {**os.environ, **pids}
    subprocess.run(['bash', script], env=env)
    info('    [OK] ACL đã bãi bỏ.\n')


# ─────────────────────────────────────────────────────────────────────────────
# 6. Khởi động Web Server giả lập trên DMZ
# ─────────────────────────────────────────────────────────────────────────────

def start_web_servers(net):
    info('*** [WEB] Khởi động HTTP server giả lập trên web1, web2...\n')
    web1 = net.get('web1')
    web2 = net.get('web2')
    web1.cmd('echo "Server web1 OK" > /tmp/index.html')
    web2.cmd('echo "Server web2 OK" > /tmp/index.html')
    web1.cmd('python3 -m http.server 80 --directory /tmp &> /tmp/web1.log &')
    web2.cmd('python3 -m http.server 80 --directory /tmp &> /tmp/web2.log &')
    time.sleep(1)
    info('    web1 listening on 10.10.10.11:80\n')
    info('    web2 listening on 10.10.10.12:80\n')


# ─────────────────────────────────────────────────────────────────────────────
# 7. Kiểm tra kết nối ban đầu (quick-start test)
# ─────────────────────────────────────────────────────────────────────────────

def run_connectivity_test(net):
    info('\n*** [TEST] Kiểm tra kết nối cơ bản...\n')
    pairs = [
        ('h1', 'h2'),
        ('h1', 'web1'),
        ('h1', 'web2'),
        ('h_out', 'web1'),
    ]
    for src_name, dst_name in pairs:
        src = net.get(src_name)
        dst = net.get(dst_name)
        result = src.cmd(f'ping -c 2 -W 1 {dst.IP()} 2>&1 | tail -1')
        ok = '0% packet loss' in src.cmd(f'ping -c 2 -W 1 {dst.IP()}')
        status = '✓ OK' if ok else '✗ FAIL'
        info(f'    {src_name} → {dst_name} ({dst.IP()}): {status}\n')


# ─────────────────────────────────────────────────────────────────────────────
# 8. Hàm main
# ─────────────────────────────────────────────────────────────────────────────

def run():
    topo = CampusTopo()
    net  = Mininet(topo=topo, link=TCLink, controller=None)

    # Gán IP gateway trước khi start
    # (interface chưa có trong net nên gán sau khi start)
    net.start()

    configure_interfaces(net)
    configure_static_routes(net)
    start_web_servers(net)

    if args.nat or True:       # Mặc định luôn bật NAT để test được
        apply_nat(net)

    if args.acl:
        apply_acl(net)

    run_connectivity_test(net)

    info('\n')
    info('╔══════════════════════════════════════════════════════════════╗\n')
    info('║          CAMPUS 3-LAYER NETWORK – MININET CLI               ║\n')
    info('╠══════════════════════════════════════════════════════════════╣\n')
    info('║  Lệnh hữu ích:                                              ║\n')
    info('║   py apply_acl(net)   – Áp dụng ACL/Firewall               ║\n')
    info('║   py drop_acl(net)    – Bãi bỏ ACL                         ║\n')
    info('║   py show_nat_table(net) – Xem bảng NAT hiện tại           ║\n')
    info('║   h1 ping web1        – Test ping Inside → DMZ             ║\n')
    info('║   h_out curl 203.0.113.10 – Test Static NAT                ║\n')
    info('║   h1 iperf3 -c web1 -t 10 – Test throughput               ║\n')
    info('╚══════════════════════════════════════════════════════════════╝\n')

    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
