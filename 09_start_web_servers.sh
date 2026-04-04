#!/bin/bash
# 09_start_web_servers.sh
# Mở HTTP Python Server trên DMZ Web1 và Web2 để test Load Balancing

echo "=== Khởi chạy Web Server giả lập cho DMZ ==="

# Tạo thư mục tạm phục vụ web
sudo m web1 mkdir -p /tmp/web1
sudo m web2 mkdir -p /tmp/web2

# Ghi file index HTML báo danh
sudo m web1 sh -c 'echo "<h1>Welcome to SITE DMZ - Served by WEB1 (10.10.10.11)</h1>" > /tmp/web1/index.html'
sudo m web2 sh -c 'echo "<h1>Welcome to SITE DMZ - Served by WEB2 (10.10.10.12)</h1>" > /tmp/web2/index.html'

# Khởi chạy Python HTTP server trên port 80 ở background
sudo m web1 bash -c 'cd /tmp/web1 && nohup python3 -m http.server 80 > /tmp/web1_http.log 2>&1 &'
sudo m web2 bash -c 'cd /tmp/web2 && nohup python3 -m http.server 80 > /tmp/web2_http.log 2>&1 &'

# Khởi chạy iperf3 server mode (để load balancer dùng đo băng thông traffic)
sudo m web1 bash -c 'nohup iperf3 -s -p 5201 > /tmp/web1_iperf.log 2>&1 &'
sudo m web2 bash -c 'nohup iperf3 -s -p 5201 > /tmp/web2_iperf.log 2>&1 &'

echo "Các Web Server và iperf3 daemon đã chạy ngầm trên DMZ."
echo "Hãy dùng h1 hoặc r_out chạy wget http://10.10.10.11 hoặc iperf3 -c để test."
