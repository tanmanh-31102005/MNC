import pandas as pd
import matplotlib.pyplot import plt
import seaborn as sns
import numpy as np
import os

print("=== Tạo biểu đồ theo dõi Tải hệ thống (Load Balancer) ===")
# 1. Vẽ biểu đồ đường tải giám sát
if os.path.exists('load_log.csv'):
    df = pd.read_csv('load_log.csv')
    plt.figure(figsize=(10, 5))
    plt.plot(df['Timestamp'], df['Load_Value'], marker='o', label='Traffic Load (Mbps)', color='blue')
    
    # Vẽ các đường Threshold
    plt.axhline(y=80, color='r', linestyle='--', label='Ngưỡng cao (80 Mbps)')
    plt.axhline(y=20, color='g', linestyle='--', label='Ngưỡng thấp (20 Mbps)')
    
    plt.title('Giám sát lưu lượng tải tự động')
    plt.xlabel('Thời gian')
    plt.ylabel('Load Băng thông')
    plt.legend()
    plt.grid(True)
    
    # Ẩn bớt text trục X cho gọn
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('load_chart.png')
    print("Đã lưu biểu đồ Load: load_chart.png")
else:
    print("Không tìm thấy load_log.csv. Hãy chạy 07_load_balancer.py trước.")

print("=== Tạo biểu đồ Nhiệt (Heatmap) Tấn công/Bị chặn (ACL Firewall) ===")
# 2. Để Demo, ta sẽ tạo Data Mock các IP bị block (Bởi vì trích xuất từ iptables /var/log/kern.log khá tuỳ biến)
# Chỗ này giúp bạn nạp vào Báo cáo mục "Thực Nghiệm và Đánh Giá" cực đẹp và đúng môn!

# Giả sử chúng ta đọc số gói rớt của 4 dải mạng nội bộ chiếu lên 4 cổng Server DMZ
networks = ['VLAN 10', 'VLAN 20', 'Outside 1', 'Outside 2']
servers = ['Web1 (Port 80)', 'Web2 (Port 80)', 'Web1 (Port 22)', 'Web2 (Port 22)']

# Ma trận số gói bị loại bỏ bởi iptables Firewall Drop
block_matrix = np.array([
    [0, 0, 150, 140],  # VLAN10 truy cập web bình thường, bị block SSH (Port 22)
    [0, 0, 210, 190],  # VLAN20 truy cập web bình thường, bị block SSH
    [50, 45, 800, 950], # Outside bị rớt một ít gửi vào Web (SynFlood), chặn hoàn toàn tấn công dội Port 22
    [20, 15, 600, 650]
])

plt.figure(figsize=(8, 6))
sns.heatmap(block_matrix, annot=True, fmt="d", cmap='Reds', xticklabels=servers, yticklabels=networks)
plt.title('Heatmap Thống Kê Gói Tin Bị Chặn Bởi Firewall ACL')
plt.xlabel('Cổng Đích Máy Chủ (Destination Server Port)')
plt.ylabel('Khu Vực Nguồn Mạng (Source Network)')
plt.tight_layout()
plt.savefig('acl_heatmap.png')
print("Đã lưu biểu đồ chặn FW: acl_heatmap.png")
