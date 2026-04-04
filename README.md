# BÀI TẬP 3 – Tối ưu hóa bảo mật đa lớp và cân bằng tải
## Campus Network 3 Lớp: Core – Distribution – Access + DMZ

---

## 📁 Cấu trúc File

```
campus_network_project/
│
├── topology.py          ← ⭐ Script chính – khởi động topology Mininet
├── acl.sh               ← Áp dụng ACL đa lớp (Standard + Extended + Firewall)
├── dropacl.sh           ← Bãi bỏ toàn bộ ACL
├── setup_ospf.sh        ← Triển khai FRR/OSPF trên các router
├── nat_config.sh        ← Cấu hình PAT + Static NAT
├── load_balancer.py     ← Giám sát tải và điều hướng tự động theo ngưỡng
├── plot_charts.py       ← Vẽ 7 biểu đồ báo cáo (Matplotlib + Seaborn)
├── collect_data.sh      ← Thu thập số liệu thực nghiệm (CSV)
│
├── frr_core.conf        ← OSPF config router Core
├── frr_dist1.conf       ← OSPF config router Distribution 1
├── frr_dist2.conf       ← OSPF config router Distribution 2
├── frr_dmz.conf         ← OSPF config router DMZ
├── frr_rout.conf        ← OSPF config router ISP/Outside
│
└── results/             ← [Tự tạo] CSV số liệu thực nghiệm
    ├── latency_*.csv
    ├── throughput_*.csv
    ├── nat_log_*.txt
    └── acl_log_*.txt
```

---

## 🗺 Sơ đồ IP và Topology

| Lớp | Node | Interface | IP |
|-----|------|-----------|-----|
| Core | `core` | core-eth1 | 192.168.1.1/30 |
| Core | `core` | core-eth2 | 192.168.1.5/30 |
| Core | `core` | core-eth3 | 192.168.1.9/30 |
| Core | `core` | core-eth4 | 192.168.100.1/30 |
| Distribution | `dist1` | dist1-eth1 | 192.168.1.2/30 |
| Distribution | `dist1` | dist1-eth2 (GW) | 172.16.10.1/24 |
| Distribution | `dist2` | dist2-eth1 | 192.168.1.6/30 |
| Distribution | `dist2` | dist2-eth2 (GW) | 172.16.20.1/24 |
| DMZ Router | `dmz_r` | dmz-eth1 | 192.168.1.10/30 |
| DMZ Router | `dmz_r` | dmz-eth2 (GW) | 10.10.10.1/24 |
| ISP/Outside | `r_out` | rout-eth1 | 192.168.100.2/30 |
| ISP/Outside | `r_out` | rout-eth2 (GW) | 203.0.113.1/24 |
| **Host** | `h1` | — | 172.16.10.10/24 |
| **Host** | `printer1` | — | 172.16.10.30/24 |
| **Host** | `h2` | — | 172.16.20.10/24 |
| **Host** | `phone1` | — | 172.16.20.20/24 |
| **DMZ Server** | `web1` | — | 10.10.10.11/24 |
| **DMZ Server** | `web2` | — | 10.10.10.12/24 |
| **Outside** | `h_out` | — | 203.0.113.100/24 |

### Bảng Static NAT
| IP Public (Outside) | IP Private (DMZ) | Dịch vụ |
|--------------------|-----------------|---------|
| 203.0.113.10 | 10.10.10.11 (web1) | HTTP/HTTPS |
| 203.0.113.11 | 10.10.10.12 (web2) | HTTP/HTTPS |

---

## 🚀 Hướng dẫn chạy từng bước

### Bước 0: Cài đặt môi trường

```bash
# Cài Mininet
sudo apt update
sudo apt install -y mininet python3-pip

# Cài FRRouting (OSPF)
sudo apt install -y frr frr-pythontools

# Bật daemon OSPF trong FRR config
sudo sed -i 's/ospfd=no/ospfd=yes/' /etc/frr/daemons
sudo sed -i 's/zebra=no/zebra=yes/' /etc/frr/daemons

# Cài Python dependencies cho biểu đồ
pip3 install matplotlib seaborn pandas numpy

# Cài conntrack để xem bảng NAT
sudo apt install -y conntrack iperf3

# Cấp quyền thực thi cho scripts
chmod +x *.sh
```

---

### Bước 1: Khởi động Topology Mininet

```bash
# Terminal 1 – Chạy topology (giữ cửa sổ này mở)
sudo python3 topology.py

# Kết quả mong đợi:
# *** Mạng đã khởi động
# *** [CONFIG] Gán IP gateway...
# *** [NAT]  Áp dụng PAT + Static NAT...
# *** [WEB]  Khởi động HTTP server...
# *** [TEST] Kiểm tra kết nối cơ bản...
#     h1 → web1 (10.10.10.11): ✓ OK
#     h1 → h_out (...): ✓ OK
# mininet>                    ← CLI đang chờ
```

---

### Bước 2: Triển khai OSPF (Terminal mới)

```bash
# Terminal 2
sudo bash setup_ospf.sh

# Kiểm tra OSPF đã hội tụ:
sudo m core vtysh -c "show ip ospf neighbor"
# Kết quả mong đợi: thấy dist1, dist2, dmz_r, r_out ở state FULL

sudo m core vtysh -c "show ip route ospf"
# Thấy các route O (OSPF) đến tất cả subnet
```

---

### Bước 3: Áp dụng ACL + Firewall

```bash
# Cách 1: Từ Terminal 2
sudo bash acl.sh   # Cần set env vars DIST1_PID, DIST2_PID, DMZ_R_PID, R_OUT_PID

# Cách 2 (khuyến nghị): Từ Mininet CLI (Terminal 1)
# mininet> py apply_acl(net)

# Kiểm tra ACL đang hoạt động:
# mininet> h1 curl http://10.10.10.11     → thành công (HTTP port 80 được phép)
# mininet> h1 ssh 10.10.10.11             → bị chặn (SSH port 22 bị DROP)

# Xem log gói bị chặn:
sudo dmesg | grep -E "EXT_ACL|FW_BORDER|STD_ACL" | tail -20

# Để BÃI BỎ ACL:
# mininet> py drop_acl(net)
# hoặc:
sudo bash dropacl.sh
```

---

### Bước 4: Kiểm tra NAT

```bash
# Kiểm tra PAT (Inside → Outside)
# mininet> h1 curl http://203.0.113.100   (cần h_out có web server)

# Kiểm tra Static NAT (Outside → DMZ)
# mininet> h_out curl http://203.0.113.10  → phải trả về "Server web1 OK"
# mininet> h_out curl http://203.0.113.11  → phải trả về "Server web2 OK"

# Xem bảng NAT conntrack (live)
# mininet> py show_nat_table(net)

# Hoặc chi tiết hơn từ terminal:
sudo m r_out conntrack -L
```

---

### Bước 5: Chạy Load Balancer (Terminal 3)

```bash
# Chế độ Demo (không cần Mininet đang chạy):
python3 load_balancer.py --demo --maxbw 100

# Chế độ thực tế (khi Mininet đang chạy):
# Lấy PID của node r_out:
R_OUT_PID=$(sudo m r_out echo $BASHPID | head -1)
python3 load_balancer.py --pid "$R_OUT_PID" --iface rout-eth2

# Quan sát chuyển đổi tự động khi tải vượt 80%:
# ⚡ [08:15:32] CHUYỂN ĐỔI: WEB1 → WEB2  (dest=10.10.10.12)
# ⚡ [08:16:10] CHUYỂN ĐỔI: WEB2 → WEB1  (dest=10.10.10.11)

# Sinh traffic cao từ Mininet CLI (test threshold):
# mininet> h1 iperf3 -c 10.10.10.11 -t 60 -b 95M &
```

---

### Bước 6: Thu thập số liệu

```bash
# Chạy trong khi Mininet đang chạy
sudo bash collect_data.sh

# Kết quả lưu vào ./results/:
# - latency_*.csv       → RTT giữa các cặp host
# - throughput_*.csv    → Throughput iperf3
# - nat_log_*.txt       → NAT events từ dmesg
# - acl_log_*.txt       → ACL drop events
```

---

### Bước 7: Vẽ biểu đồ

```bash
# Vẽ tất cả biểu đồ (dùng demo data nếu chưa có CSV):
python3 plot_charts.py --demo --out ./charts/

# Các biểu đồ tạo ra:
# chart0_topology_diagram.png   → Sơ đồ logic topology
# chart1_load_timeline.png      → Line chart Web1/Web2 theo thời gian
# chart2_acl_heatmap.png        → Heatmap gói bị chặn (đẹp nhất!)
# chart3_throughput_comparison.png → So sánh throughput trước/sau NAT+ACL
# chart4_latency_comparison.png → So sánh latency RTT
# chart5_stacked_load.png       → Stacked area tổng tải
# chart6_nat_table.png          → Bảng NAT Translation dạng ảnh
```

---

## 🔍 Lệnh Debug thường dùng

```bash
# ── Kiểm tra routing ────────────────────────────────────────
sudo m core  ip route                          # Bảng routing core
sudo m dist1 ip route                          # Bảng routing dist1
sudo m h1    ip route                          # Default gateway của host

# ── OSPF ────────────────────────────────────────────────────
sudo m core vtysh -c "show ip ospf neighbor"   # OSPF neighbors
sudo m core vtysh -c "show ip ospf database"   # LSDB

# ── NAT ─────────────────────────────────────────────────────
sudo m r_out iptables -t nat -L -n -v          # Bảng NAT đầy đủ
sudo m r_out conntrack -L                      # Bảng conntrack thời gian thực
sudo dmesg | grep NAT_                         # NAT log events

# ── ACL/Firewall ─────────────────────────────────────────────
sudo m dmz_r iptables -L FORWARD -n -v         # ACL tại DMZ
sudo m dist1 iptables -L FORWARD -n -v         # ACL tại Distribution
sudo dmesg | grep -E "ACL|FW_"                 # Log gói bị chặn

# ── Connectivity test ────────────────────────────────────────
sudo m h1    ping -c 3 10.10.10.11             # Inside → DMZ
sudo m h_out wget -qO- http://203.0.113.10     # Outside → DMZ (Static NAT)
sudo m h1    iperf3 -c 10.10.10.11 -t 10       # Throughput test
```

---

## 📋 Bảng Quản lý Sự cố

| Lỗi | Triệu chứng | Nguyên nhân | Cách khắc phục |
|-----|-------------|-------------|----------------|
| NAT không hoạt động | h_out curl 203.0.113.10 timeout | DNAT chưa set hoặc rule sai | `sudo m r_out iptables -t nat -L PREROUTING -n` kiểm tra |
| ACL chặn nhầm | h1 không vào được web1 port 80 | Extended ACL thiếu rule ACCEPT | Kiểm tra `sudo m dmz_r iptables -L` |
| OSPF không hội tụ | `show ospf neighbor` không thấy | Sai network statement | Kiểm tra FRR log `/tmp/frr-*.log` |
| Load balancer không chuyển | Tải > 80% nhưng không switch | `sudo m` không tìm thấy node | Dùng `--pid` thay vì `sudo m` |
| Ping from h_out → DMZ thất bại | 100% loss | Thiếu static route ngược về | `sudo m r_out ip route add 10.10.10.0/24 via 192.168.100.1` |

---

## 📊 Gợi ý nội dung từng chương báo cáo

### Chương 1 – Tổng quan & Thiết kế Topology
- Mô tả mô hình 3 lớp, giải thích vai trò từng lớp
- **Hình:** `chart0_topology_diagram.png`
- **Bảng:** Bảng IP địa chỉ (ở trên)
- Giải thích tại sao DMZ tách biệt với Inside/Outside

### Chương 2 – OSPF và NAT/PAT
- Config OSPF từ `frr_core.conf` đến `frr_rout.conf`
- Output `show ip ospf neighbor` (chụp màn hình)
- **Bảng:** Bảng Static NAT Translation – `chart6_nat_table.png`
- Config NAT trong `nat_config.sh`

### Chương 3 – Bảo mật đa lớp (ACL + Firewall)
- Giải thích 3 lớp bảo mật trong `acl.sh`
- **Hình:** `chart2_acl_heatmap.png` ← ĐẸP NHẤT, trực quan nhất
- Kịch bản test: port nào allowed/blocked
- Log chặn gói: `dmesg | grep EXT_ACL`

### Chương 4 – Cân bằng tải theo ngưỡng
- Thuật toán trong `load_balancer.py`
- **Hình:** `chart1_load_timeline.png` (thấy điểm SWITCH rõ ràng)
- **Hình:** `chart5_stacked_load.png` (tổng tải)
- Log chuyển đổi server (từ `load_log.csv`)

### Chương 5 – Phân tích kết quả
- **Hình:** `chart3_throughput_comparison.png`
- **Hình:** `chart4_latency_comparison.png`
- Nhận xét: NAT gây overhead ~7-10%, ACL thêm ~3-5% latency
- Bảng sự cố (ở trên)
- Kết luận và hướng phát triển

---

*Bài tập 3 – Môn Mạng Máy Tính Nâng Cao*
