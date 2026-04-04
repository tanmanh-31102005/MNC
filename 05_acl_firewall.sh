#!/bin/bash
# 05_acl_firewall.sh
# Bảo vệ đa lớp: Standard ACL tại Distribution layer và Extended tại DMZ/Core

echo "=== Đặt Standard ACL tại Dist1/Dist2 ==="
# Cấm một dải IP cụ thể trong VLAN10 (vd 172.16.10.50 không được rời mạng con)
# Mặc định mình chỉ mở các host có sẵn, kịch bản ta sẽ log lại các gói drop
sudo m dist1 iptables -A FORWARD -s 172.16.10.50 -j LOG --log-prefix "ACL_DROP_VLAN10: "
sudo m dist1 iptables -A FORWARD -s 172.16.10.50 -j DROP

echo "=== Đặt Extended ACL tại DMZ Router (Firewall vùng) ==="
# Cho phép các luồng đã được Establish/Related đi về
sudo m dmz_r iptables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT

# CHỈ CHO PHÉP cổng 80 (HTTP) và 443 (HTTPS) đi vào DMZ (từ bất kỳ đâu)
sudo m dmz_r iptables -A FORWARD -p tcp --dport 80 -d 10.10.10.0/24 -j ACCEPT
sudo m dmz_r iptables -A FORWARD -p tcp --dport 443 -d 10.10.10.0/24 -j ACCEPT

# CHỈ CHO PHÉP ICMP (Ping) cho mục đích debug, bạn có thể comment nếu muốn strict
sudo m dmz_r iptables -A FORWARD -p icmp -d 10.10.10.0/24 -j ACCEPT

# LOG tất cả các gói còn lại cố tình truy cập vào DMZ và DROP
sudo m dmz_r iptables -A FORWARD -d 10.10.10.0/24 -j LOG --log-prefix "FW_DROP_DMZ: "
sudo m dmz_r iptables -A FORWARD -d 10.10.10.0/24 -j DROP

echo "=== ACL và Firewall đã được thiết lập thành công! ==="
