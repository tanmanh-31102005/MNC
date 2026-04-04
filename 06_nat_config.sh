#!/bin/bash
# 06_nat_config.sh
# Cấu hình PAT (NAT Overload) cho mạng Inside và Static NAT cho DMZ Server ra Internet qua Router ISP (r_out) hoặc Router Core

echo "=== Cấu hình PAT (Source NAT / Masquerade) trên Core_R / DMZ_R ==="
# Để giả lập giống thực tế, chúng ta sẽ làm PAT tại r_out (ISP side) hoặc core (Gateway ra Internet)
# Giả sử r_out là biên, ta NAT tất cả traffic từ 172.16.x.x ra cổng rout-eth2 mang IP 203.0.113.1
sudo m r_out iptables -t nat -A POSTROUTING -s 172.16.0.0/16 -o rout-eth2 -j MASQUERADE
# NAT cả dải nội bộ khác nếu cần
sudo m r_out iptables -t nat -A POSTROUTING -s 192.168.1.0/24 -o rout-eth2 -j MASQUERADE
sudo m r_out iptables -t nat -A POSTROUTING -s 10.10.10.0/24  -o rout-eth2 -j MASQUERADE

echo "=== Cấu hình Static NAT (Destination NAT) cho máy chủ DMZ tại Biên ==="
# Máy từ Outside (203.0.113.100) truy cập IP Public ảo (203.0.113.10) sẽ được NAT vào DMZ (10.10.10.11)
sudo m r_out ip addr add 203.0.113.10/24 dev rout-eth2
sudo m r_out iptables -t nat -A PREROUTING -d 203.0.113.10 -p tcp --dport 80 -j DNAT --to-destination 10.10.10.11:80

# Cấu hình cho Server 2 (web2)
sudo m r_out ip addr add 203.0.113.11/24 dev rout-eth2
sudo m r_out iptables -t nat -A PREROUTING -d 203.0.113.11 -p tcp --dport 80 -j DNAT --to-destination 10.10.10.12:80

echo "Lưu ý log NAT để sau này parse kết quả:"
sudo m r_out iptables -t nat -A POSTROUTING -j LOG --log-prefix "NAT_EVENT: "

echo "=== Quá trình nạp NAT hoàn tất. ==="
