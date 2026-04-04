#!/bin/bash
# 04_setup_ospf.sh
# Script khởi chạy FRRouting daemons trên các node của Mininet

echo "=== Khởi động tiến trình Zebra (Routing Manager) và OSPFd trên từng Node ==="

# Chạy Zebra và OSPF trên Core
sudo m core /usr/lib/frr/zebra -f $(pwd)/04_frr_core.conf -d -z /tmp/zserv-core.api -i /tmp/zebra-core.pid
sudo m core /usr/lib/frr/ospfd -f $(pwd)/04_frr_core.conf -d -z /tmp/zserv-core.api -i /tmp/ospfd-core.pid

# Chạy Zebra và OSPF trên Dist1
sudo m dist1 /usr/lib/frr/zebra -f $(pwd)/04_frr_dist1.conf -d -z /tmp/zserv-dist1.api -i /tmp/zebra-dist1.pid
sudo m dist1 /usr/lib/frr/ospfd -f $(pwd)/04_frr_dist1.conf -d -z /tmp/zserv-dist1.api -i /tmp/ospfd-dist1.pid

# Chạy Zebra và OSPF trên Dist2
sudo m dist2 /usr/lib/frr/zebra -f $(pwd)/04_frr_dist2.conf -d -z /tmp/zserv-dist2.api -i /tmp/zebra-dist2.pid
sudo m dist2 /usr/lib/frr/ospfd -f $(pwd)/04_frr_dist2.conf -d -z /tmp/zserv-dist2.api -i /tmp/ospfd-dist2.pid

# Chạy Zebra và OSPF trên DMZ Router
sudo m dmz_r /usr/lib/frr/zebra -f $(pwd)/04_frr_dmz.conf -d -z /tmp/zserv-dmz.api -i /tmp/zebra-dmz.pid
sudo m dmz_r /usr/lib/frr/ospfd -f $(pwd)/04_frr_dmz.conf -d -z /tmp/zserv-dmz.api -i /tmp/ospfd-dmz.pid

# Chạy Zebra và OSPF trên ISP / Outside
sudo m r_out /usr/lib/frr/zebra -f $(pwd)/04_frr_r_out.conf -d -z /tmp/zserv-rout.api -i /tmp/zebra-rout.pid
sudo m r_out /usr/lib/frr/ospfd -f $(pwd)/04_frr_r_out.conf -d -z /tmp/zserv-rout.api -i /tmp/ospfd-rout.pid

echo "Vui lòng chờ 5-10 giây để OSPF Hello hội tụ..."
sleep 5

echo "Bạn có thể kiểm tra bảng định tuyến tại node core bằng lệnh:"
echo "sudo m core ip route"
echo "hoặc kiểm tra OSPF neighbor:"
echo "sudo m core vtysh -c 'show ip ospf neighbor'"
