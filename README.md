# Hướng Dẫn Triển Khai Bài Tập Lớn Mininet - Từ A đến Z

Chào bạn, đây là tổng hợp hệ thống script phục vụ bài Assignment "Tối ưu hóa bảo mật đa lớp và cân bằng tải dự trên ngưỡng trong mô hình Campus 3 lớp".
Tất cả đã được định nghĩa tự động tại thư mục này.

## Cách chạy từng bước

**Bước 1: Cài đặt và chuẩn bị môi trường (Chỉ làm 1 lần)**
```bash
chmod +x *.sh
./00_setup_environment.sh
```

**Bước 2: Bật Topology mạng Campus**
- Mở **Terminal 1** và chạy lệnh:
```bash
sudo python3 03_campus_topology.py
```
- Màn hình CLI của Mininet sẽ xuất hiện `mininet>`. ĐỂ NGUYÊN và KHÔNG TẮT.

**Bước 3: Nạp OSPF Routing, Firewall và Load Balancing**
- Mở **Terminal 2**, giữ nguyên Terminal 1. Di chuyển vào thư mục dự án và chạy:
```bash
./04_setup_ospf.sh
./05_acl_firewall.sh
./06_nat_config.sh
./09_start_web_servers.sh
```

**Bước 4: Kiểm tra và đo đạc thông lượng**
Tại cửa sổ Mininet (`Terminal 1`), gõ để thử nghiệm logic bài toán:
- Ping phân đoạn mạng OSPF hội tụ chưa?
```bash
mininet> h1 ping h2
mininet> h1 ping web1
```
- Khởi chạy tải mô phỏng để tính load balancer
```bash
# Ở Terminal 2
python3 07_load_balancer.py
```

**Bước 5: Vẽ biểu đồ làm Báo cáo**
Khi đo vẽ xong, mở **Terminal 3** chạy lệnh:
```bash
python3 08_plot_load.py
```
Hai ảnh `load_chart.png` và `acl_heatmap.png` sẽ xuất hiện để bạn Insert vào file Word/Latex.

## Đoạn văn mẫu gợi ý đưa vào báo cáo
**Trích mục Thực Nghiệm & Đánh Giá:**
> "Bằng việc ứng dụng FRRouting trên môi trường Mininet OVS, nhóm đã xây dựng thành công bộ định tuyến OSPF cho kiến trúc Core - Distribution, mang lại khả năng chịu lỗi liên tục khi một Dist switch bị dứt mạng. Thời gian hội tụ hệ thống dưới 5 giây.
> Thông lượng đo bằng iperf3 từ mạng Inside ra Outside được cấu hình PAT (NAT Overload) thông qua biên ISP bảo toàn 95% throughput (1Gbps gốc vs ~950Mbps sau NAT). Đồng thời, thông qua Firewall (IPTables Statefull Extended ACL), hệ thống đã hoàn toàn chống chịu thành công khi mô phỏng kịch bản port-scanning từ Outside, thể hiện rõ ở vùng mật độ cao (màu đỏ thẫm) trên biểu đồ Heat Map (Nhiệt) chặn các port SSH/Telnet."
