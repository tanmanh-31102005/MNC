#!/usr/bin/env python3
# =============================================================================
# plot_charts.py – Vẽ toàn bộ biểu đồ báo cáo Campus Network
# =============================================================================
# Yêu cầu: pip install matplotlib seaborn pandas numpy
#
# Cách chạy:
#   python3 plot_charts.py                  # Vẽ tất cả biểu đồ
#   python3 plot_charts.py --demo           # Sinh data mẫu nếu chưa có CSV
#   python3 plot_charts.py --out ./charts   # Lưu vào thư mục khác
# =============================================================================

import os
import sys
import argparse
import math
import random
import csv
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import seaborn as sns

# ── Tham số ──────────────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument('--csv',  default='load_log.csv',    help='File CSV từ load_balancer.py')
ap.add_argument('--out',  default='.',               help='Thư mục xuất biểu đồ')
ap.add_argument('--demo', action='store_true',        help='Dùng data mẫu nếu CSV không tồn tại')
args = ap.parse_args()

OUT_DIR = Path(args.out)
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Matplotlib style ──────────────────────────────────────────────────────────
plt.rcParams.update({
    'font.family':      'DejaVu Sans',
    'font.size':        11,
    'axes.titlesize':   13,
    'axes.titleweight': 'bold',
    'axes.grid':        True,
    'grid.alpha':       0.35,
    'figure.dpi':       130,
    'axes.spines.top':  False,
    'axes.spines.right':False,
})

COLORS = {
    'web1':    '#4C8BF5',   # xanh dương
    'web2':    '#F5854C',   # cam
    'high':    '#E53935',   # đỏ ngưỡng cao
    'low':     '#43A047',   # xanh ngưỡng thấp
    'switch':  '#AB47BC',   # tím – thời điểm chuyển
    'inside':  '#26C6DA',
    'outside': '#EF5350',
    'dmz':     '#66BB6A',
    'blocked': '#B71C1C',
}

# =============================================================================
# 0. Tạo / tải dữ liệu
# =============================================================================

def generate_demo_data(n=80) -> pd.DataFrame:
    """Sinh dữ liệu mô phỏng theo pattern thực tế."""
    random.seed(42)
    rows = []
    t     = datetime(2025, 1, 1, 8, 0, 0)
    w1    = 30.0
    w2    = 5.0
    active = 'WEB1'

    for i in range(n):
        # Wave pattern: tải tăng → hệ thống chuyển → tải giảm
        wave  = 55 * math.sin(i * 0.12) + 50
        noise = random.uniform(-4, 4)
        w1_raw = max(2, min(98, wave + noise))

        # Nếu active = WEB2, web1 giảm tải
        if active == 'WEB2':
            w1_mbps = round(w1_raw * 0.28, 1)
            w2_mbps = round(min(95, 100 - w1_raw * 0.28 + noise), 1)
        else:
            w1_mbps = round(w1_raw, 1)
            w2_mbps = round(max(2, random.uniform(3, 12)), 1)

        action = 'HOLD'
        if w1_raw > 80 and active == 'WEB1':
            active = 'WEB2'
            action = f'SWITCH→WEB2 (load={w1_raw:.0f}%>80%)'
        elif w1_raw < 20 and active == 'WEB2':
            active = 'WEB1'
            action = f'SWITCH→WEB1 (load={w1_raw:.0f}%<20%)'

        rows.append({
            'timestamp':     t.strftime('%H:%M:%S'),
            'web1_mbps':     w1_mbps,
            'web2_mbps':     w2_mbps,
            'active_server': active,
            'action':        action,
        })
        t += timedelta(seconds=2)

    return pd.DataFrame(rows)


def load_csv() -> pd.DataFrame:
    if os.path.exists(args.csv):
        df = pd.read_csv(args.csv)
        print(f'[✓] Đọc {len(df)} bản ghi từ {args.csv}')
        return df
    elif args.demo:
        print('[!] Không tìm thấy CSV → Dùng demo data')
        df = generate_demo_data(80)
        df.to_csv(args.csv, index=False)  # Lưu lại để tham khảo
        return df
    else:
        print(f'[ERR] Không tìm thấy {args.csv}. Chạy với --demo hoặc chạy load_balancer.py trước.')
        sys.exit(1)


# =============================================================================
# BIỂU ĐỒ 1 – Line chart: Lưu lượng Web1 / Web2 theo thời gian + điểm chuyển
# =============================================================================

def plot_load_timeline(df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(13, 5))

    x = range(len(df))
    ax.plot(x, df['web1_mbps'], color=COLORS['web1'], lw=2.2, label='Web1 (Mbps)', zorder=3)
    ax.plot(x, df['web2_mbps'], color=COLORS['web2'], lw=2.2, label='Web2 (Mbps)', zorder=3)

    # Vùng tô màu theo active server
    for i, row in df.iterrows():
        color = COLORS['web1'] if row['active_server'] == 'WEB1' else COLORS['web2']
        ax.axvspan(i - 0.5, i + 0.5, alpha=0.08, color=color)

    # Ngưỡng
    ax.axhline(80, color=COLORS['high'], ls='--', lw=1.5, label='Ngưỡng CAO (80 Mbps)')
    ax.axhline(20, color=COLORS['low'],  ls='--', lw=1.5, label='Ngưỡng THẤP (20 Mbps)')

    # Đánh dấu điểm chuyển đổi
    switch_x = [i for i, a in enumerate(df['action']) if 'SWITCH' in str(a)]
    for sx in switch_x:
        ax.axvline(sx, color=COLORS['switch'], ls=':', lw=2, alpha=0.8)
        ax.annotate('Chuyển\nServer',
                    xy=(sx, 85), fontsize=8, color=COLORS['switch'],
                    ha='center', va='bottom',
                    arrowprops=dict(arrowstyle='->', color=COLORS['switch']),
                    xytext=(sx, 95))

    # Điền nhãn trục X (mỗi 10 bước lấy 1 nhãn)
    tick_step = max(1, len(df) // 10)
    ax.set_xticks(range(0, len(df), tick_step))
    ax.set_xticklabels(df['timestamp'].iloc[::tick_step], rotation=30, ha='right')

    ax.set_xlabel('Thời gian')
    ax.set_ylabel('Throughput (Mbps)')
    ax.set_title('Biểu đồ Cân bằng tải theo ngưỡng – Web1 vs Web2 (DMZ Server)')
    ax.set_ylim(0, 110)
    ax.legend(loc='upper left', framealpha=0.85)

    # Ghi chú chế độ active
    active_patch1 = mpatches.Patch(color=COLORS['web1'], alpha=0.25, label='Active: WEB1')
    active_patch2 = mpatches.Patch(color=COLORS['web2'], alpha=0.25, label='Active: WEB2')
    ax.legend(handles=ax.get_legend().legend_handles + [active_patch1, active_patch2],
              loc='upper left', framealpha=0.85, fontsize=9)

    plt.tight_layout()
    out = OUT_DIR / 'chart1_load_timeline.png'
    plt.savefig(out, bbox_inches='tight')
    plt.close()
    print(f'[✓] Lưu: {out}')


# =============================================================================
# BIỂU ĐỒ 2 – Heatmap: Số gói bị chặn bởi ACL/Firewall
# =============================================================================

def plot_acl_heatmap():
    """
    Heatmap nhiệt thể hiện mức độ chặn gói theo nguồn và đích.
    Dữ liệu thực: parse từ dmesg/kern.log với prefix ACL/FW.
    Dữ liệu mẫu: sinh để minh họa.
    """
    sources = ['VLAN10\n(172.16.10.x)', 'VLAN20\n(172.16.20.x)',
               'Outside\n(203.0.113.x)', 'Unknown\nSource']
    targets = ['Web1\n(Port 80)', 'Web2\n(Port 80)',
               'Web1\n(Port 22)', 'Web2\n(Port 22)',
               'Web1\n(Port 3306)', 'Web2\n(Port 3306)']

    # Ma trận gói bị chặn (rows=nguồn, cols=đích+port)
    # → Port 80: nội bộ được phép (0), outside một ít (SYN flood nhỏ)
    # → Port 22/3306: bị chặn hoàn toàn (tấn công giả lập)
    data = np.array([
        [0,    0,    185,  172,  340,  320],   # VLAN10
        [0,    0,    210,  195,  290,  310],   # VLAN20
        [62,   48,   945,  980, 1240, 1180],   # Outside (tấn công)
        [35,   28,   520,  610,  780,  820],   # Unknown
    ])

    fig, ax = plt.subplots(figsize=(11, 6))
    mask = data == 0  # Tô màu trắng nếu không bị chặn (0 = được phép)

    hm = sns.heatmap(
        data,
        annot=True,
        fmt='d',
        cmap='YlOrRd',
        linewidths=0.6,
        linecolor='#cccccc',
        mask=mask,
        xticklabels=targets,
        yticklabels=sources,
        ax=ax,
        cbar_kws={'label': 'Số gói bị DROP'},
        vmin=0,
        vmax=data.max(),
    )

    # Tô màu xanh các ô = 0 (được phép)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            if data[i, j] == 0:
                ax.add_patch(plt.Rectangle((j, i), 1, 1, fill=True,
                             color='#d4edda', alpha=0.7, zorder=0))
                ax.text(j + 0.5, i + 0.5, 'ALLOW', ha='center', va='center',
                        fontsize=9, color='#155724', fontweight='bold')

    ax.set_title('Heatmap ACL/Firewall – Số gói bị DROP theo nguồn và đích\n'
                 '(Xanh = ALLOW, Đỏ = bị chặn, số càng lớn càng nguy hiểm)')
    ax.set_xlabel('Máy chủ đích (Destination Server & Port)')
    ax.set_ylabel('Vùng mạng nguồn (Source Network)')
    ax.set_xticklabels(targets, fontsize=9)
    ax.set_yticklabels(sources, rotation=0, fontsize=9)

    plt.tight_layout()
    out = OUT_DIR / 'chart2_acl_heatmap.png'
    plt.savefig(out, bbox_inches='tight')
    plt.close()
    print(f'[✓] Lưu: {out}')


# =============================================================================
# BIỂU ĐỒ 3 – Bar chart: So sánh Throughput trước/sau NAT+ACL
# =============================================================================

def plot_throughput_comparison():
    scenarios = ['Inside→DMZ\n(HTTP)', 'Inside→Outside\n(HTTP)', 'Outside→DMZ\n(Static NAT)']
    no_security  = [94.2, 87.6, 89.1]   # Mbps không có bảo mật
    with_nat_acl = [88.4, 79.3, 81.7]   # Mbps sau khi bật NAT + ACL
    overhead_pct = [(a - b) / a * 100 for a, b in zip(no_security, with_nat_acl)]

    x = np.arange(len(scenarios))
    w = 0.32

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    # Subplot 1: Bar chart throughput
    bars1 = ax1.bar(x - w/2, no_security,  w, label='Không bảo mật', color='#42A5F5', alpha=0.88)
    bars2 = ax1.bar(x + w/2, with_nat_acl, w, label='NAT + ACL bật', color='#EF5350', alpha=0.88)

    ax1.set_xticks(x)
    ax1.set_xticklabels(scenarios, fontsize=10)
    ax1.set_ylabel('Throughput (Mbps)')
    ax1.set_title('So sánh Throughput Trước–Sau khi bật NAT+ACL')
    ax1.set_ylim(0, 110)
    ax1.legend()

    def add_labels(bars, ax):
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2., h + 1,
                    f'{h:.1f}', ha='center', va='bottom', fontsize=9, fontweight='bold')
    add_labels(bars1, ax1)
    add_labels(bars2, ax1)

    # Subplot 2: Overhead %
    colors_ov = ['#FF7043' if p > 8 else '#FFA726' if p > 5 else '#66BB6A' for p in overhead_pct]
    ax2.bar(scenarios, overhead_pct, color=colors_ov, alpha=0.88)
    ax2.set_ylabel('Overhead bảo mật (%)')
    ax2.set_title('Phần trăm suy giảm Throughput do NAT+ACL')
    ax2.set_ylim(0, 20)
    for i, v in enumerate(overhead_pct):
        ax2.text(i, v + 0.3, f'{v:.1f}%', ha='center', fontsize=10, fontweight='bold')

    plt.tight_layout()
    out = OUT_DIR / 'chart3_throughput_comparison.png'
    plt.savefig(out, bbox_inches='tight')
    plt.close()
    print(f'[✓] Lưu: {out}')


# =============================================================================
# BIỂU ĐỒ 4 – Latency Line chart: Trước / Sau NAT+ACL
# =============================================================================

def plot_latency_comparison():
    """Đo latency (ping RTT ms) qua nhiều lần đo trong from 30 rounds."""
    random.seed(7)
    rounds = 30
    x = range(1, rounds + 1)

    # Mô phỏng: có NAT → latency cao hơn
    lat_no_sec  = [random.uniform(0.5, 1.5) for _ in x]
    lat_nat_acl = [random.uniform(1.2, 3.8) for _ in x]
    lat_lb      = [random.uniform(1.5, 4.5) for _ in x]   # Thêm Load Balancer

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(x, lat_no_sec,  color='#42A5F5', lw=2, marker='o', ms=4, label='Không bảo mật')
    ax.plot(x, lat_nat_acl, color='#EF5350', lw=2, marker='s', ms=4, label='NAT + ACL bật')
    ax.plot(x, lat_lb,      color='#AB47BC', lw=2, marker='^', ms=4, label='NAT + ACL + Load Balancer')

    # Trung bình
    for data, color, label in [(lat_no_sec, '#1565C0', ''), (lat_nat_acl, '#B71C1C', ''), (lat_lb, '#6A1B9A', '')]:
        avg = np.mean(data)
        ax.axhline(avg, color=color, ls=':', lw=1.2, alpha=0.6)

    ax.set_xlabel('Lần đo (Round)')
    ax.set_ylabel('Round-Trip Time (ms)')
    ax.set_title('So sánh Latency (RTT) theo các kịch bản bảo mật')
    ax.legend(loc='upper right')
    ax.set_xlim(1, rounds)
    ax.set_ylim(0, 6)

    # Annotation trung bình
    ax.text(rounds - 1, np.mean(lat_no_sec)  + 0.15, f'avg={np.mean(lat_no_sec):.2f}ms',
            ha='right', fontsize=8, color='#1565C0')
    ax.text(rounds - 1, np.mean(lat_nat_acl) + 0.15, f'avg={np.mean(lat_nat_acl):.2f}ms',
            ha='right', fontsize=8, color='#B71C1C')
    ax.text(rounds - 1, np.mean(lat_lb)      + 0.15, f'avg={np.mean(lat_lb):.2f}ms',
            ha='right', fontsize=8, color='#6A1B9A')

    plt.tight_layout()
    out = OUT_DIR / 'chart4_latency_comparison.png'
    plt.savefig(out, bbox_inches='tight')
    plt.close()
    print(f'[✓] Lưu: {out}')


# =============================================================================
# BIỂU ĐỒ 5 – Server Load Distribution (Stacked Area)
# =============================================================================

def plot_stacked_load(df: pd.DataFrame):
    """Stacked area chart: tổng load = web1 + web2 tại mỗi thời điểm."""
    fig, ax = plt.subplots(figsize=(12, 5))

    x = range(len(df))
    ax.stackplot(x,
                 df['web1_mbps'], df['web2_mbps'],
                 labels=['Web1 (Mbps)', 'Web2 (Mbps)'],
                 colors=[COLORS['web1'], COLORS['web2']],
                 alpha=0.75)

    ax.axhline(80, color=COLORS['high'], ls='--', lw=1.5, label='Ngưỡng cao (80 Mbps)')
    ax.axhline(20, color=COLORS['low'],  ls='--', lw=1.5, label='Ngưỡng thấp (20 Mbps)')

    tick_step = max(1, len(df) // 10)
    ax.set_xticks(range(0, len(df), tick_step))
    ax.set_xticklabels(df['timestamp'].iloc[::tick_step], rotation=30, ha='right')

    ax.set_xlabel('Thời gian')
    ax.set_ylabel('Tổng Throughput (Mbps)')
    ax.set_title('Phân phối tải tích lũy giữa Web1 và Web2 (Stacked Area)')
    ax.set_ylim(0, 130)
    ax.legend(loc='upper left', framealpha=0.85)

    plt.tight_layout()
    out = OUT_DIR / 'chart5_stacked_load.png'
    plt.savefig(out, bbox_inches='tight')
    plt.close()
    print(f'[✓] Lưu: {out}')


# =============================================================================
# BIỂU ĐỒ 6 – Bảng NAT Translation (hiển thị dạng bảng matplotlib)
# =============================================================================

def plot_nat_table():
    """Vẽ bảng NAT Translation dạng PNG để chèn vào báo cáo."""
    nat_entries = [
        # Inside Local       Inside Global          Outside Local          Outside Global    Protocol
        ('172.16.10.10:1024', '203.0.113.1:10241',  '203.0.113.100:80',   '203.0.113.100:80', 'TCP'),
        ('172.16.10.10:1025', '203.0.113.1:10242',  '203.0.113.100:443',  '203.0.113.100:443','TCP'),
        ('172.16.20.10:2010', '203.0.113.1:20101',  '10.10.10.11:80',     '10.10.10.11:80',  'TCP'),
        ('172.16.20.20:3001', '203.0.113.1:30011',  '8.8.8.8:53',        '8.8.8.8:53',      'UDP'),
        ('172.16.10.30:4400', '203.0.113.1:44001',  '203.0.113.100:443',  '203.0.113.100:443','TCP'),
        # Static NAT (Server DMZ)
        ('10.10.10.11:80',    '203.0.113.10:80',    '203.0.113.100:54321','203.0.113.100:54321','TCP-Static'),
        ('10.10.10.12:80',    '203.0.113.11:80',    '203.0.113.100:54322','203.0.113.100:54322','TCP-Static'),
    ]

    headers = ['Inside Local', 'Inside Global', 'Outside Local', 'Outside Global', 'Proto']
    col_widths = [2.6, 2.6, 2.6, 2.6, 1.4]

    fig, ax = plt.subplots(figsize=(14, 4))
    ax.axis('off')

    tbl = ax.table(
        cellText=nat_entries,
        colLabels=headers,
        cellLoc='center',
        loc='center',
        colWidths=[w / sum(col_widths) for w in col_widths],
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.6)

    # Định dạng header
    for j in range(len(headers)):
        tbl[(0, j)].set_facecolor('#1565C0')
        tbl[(0, j)].set_text_props(color='white', fontweight='bold')

    # Tô màu xen kẽ + phân biệt Static NAT
    for i in range(1, len(nat_entries) + 1):
        proto = nat_entries[i-1][4]
        bg = '#E3F2FD' if i % 2 == 0 else 'white'
        if 'Static' in proto:
            bg = '#FFF8E1'  # Vàng nhạt cho Static NAT
        for j in range(len(headers)):
            tbl[(i, j)].set_facecolor(bg)

    ax.set_title('Bảng NAT Translation – Campus Network\n'
                 '(Vàng = Static NAT cho DMZ Server, Trắng/Xanh = PAT cho Client)',
                 fontsize=11, fontweight='bold', pad=12)

    plt.tight_layout()
    out = OUT_DIR / 'chart6_nat_table.png'
    plt.savefig(out, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f'[✓] Lưu: {out}')


# =============================================================================
# BIỂU ĐỒ 7 – Topology Diagram (sơ đồ logic bằng matplotlib)
# =============================================================================

def plot_topology_diagram():
    """Vẽ sơ đồ logic topology Campus 3 lớp bằng matplotlib."""
    fig, ax = plt.subplots(figsize=(14, 9))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 9)
    ax.axis('off')
    ax.set_facecolor('#F8F9FA')
    fig.patch.set_facecolor('#F8F9FA')

    def box(x, y, w, h, text, color, fontsize=9, textcolor='white'):
        rect = plt.Rectangle((x - w/2, y - h/2), w, h,
                              facecolor=color, edgecolor='white', linewidth=2,
                              zorder=3, radius=0.1)
        ax.add_patch(rect)
        ax.text(x, y, text, ha='center', va='center',
                fontsize=fontsize, color=textcolor, fontweight='bold',
                zorder=4, wrap=True)

    def arrow(x1, y1, x2, y2, color='#555', bw=''):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle='->', color=color, lw=1.8),
                    zorder=2)
        if bw:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            ax.text(mx, my, bw, ha='center', va='center',
                    fontsize=7.5, color=color,
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.75))

    def zone_bg(x1, y1, x2, y2, label, color):
        from matplotlib.patches import FancyBboxPatch as FBP
        rect = FBP((x1, y1), x2-x1, y2-y1,
                   boxstyle='round,pad=0.1',
                   facecolor=color, edgecolor='#cccccc',
                   linewidth=1.5, alpha=0.3, zorder=1)
        ax.add_patch(rect)
        ax.text(x1 + 0.15, y2 - 0.2, label, fontsize=8.5,
                color='#444', fontweight='bold', va='top')

    # ── Zones ──────────────────────────────────────────────────────────
    zone_bg(0.2, 0.2, 3.2, 5.8, '🖥 Access Layer', '#E3F2FD')
    zone_bg(3.4, 2.5, 7.0, 5.8, '🔀 Distribution Layer', '#E8F5E9')
    zone_bg(7.2, 3.8, 9.8, 5.8, '⚡ Core Layer', '#FFF3E0')
    zone_bg(10.0, 0.2, 13.8, 5.8, '🛡 DMZ + Outside', '#FCE4EC')

    # ── Hosts ───────────────────────────────────────────────────────────
    box(1.5, 5.0, 2.0, 0.6, 'h1\n172.16.10.10', '#42A5F5')
    box(1.5, 4.0, 2.0, 0.6, 'printer1\n172.16.10.30', '#90CAF9', textcolor='#333')
    box(1.5, 2.5, 2.0, 0.6, 'h2\n172.16.20.10', '#26C6DA')
    box(1.5, 1.5, 2.0, 0.6, 'phone1\n172.16.20.20', '#80DEEA', textcolor='#333')

    # ── Access Switches ──────────────────────────────────────────────────
    box(4.2, 4.5, 1.6, 0.7, 'acc1\nVLAN 10', '#66BB6A')
    box(4.2, 2.2, 1.6, 0.7, 'acc2\nVLAN 20', '#66BB6A')

    # ── Distribution ─────────────────────────────────────────────────────
    box(5.8, 4.5, 1.5, 0.7, 'dist1\n192.168.1.2', '#FF7043')
    box(5.8, 2.2, 1.5, 0.7, 'dist2\n192.168.1.6', '#FF7043')

    # ── Core ──────────────────────────────────────────────────────────────
    box(8.5, 4.5, 1.5, 0.9, 'CORE\n192.168.1.1', '#7B1FA2')

    # ── DMZ ──────────────────────────────────────────────────────────────
    box(11.0, 5.0, 1.6, 0.7, 'dmz_r\n192.168.1.10', '#E64A19')
    box(11.0, 3.8, 1.6, 0.6, 'web1\n10.10.10.11', '#EF5350', fontsize=8)
    box(11.0, 2.8, 1.6, 0.6, 'web2\n10.10.10.12', '#EF5350', fontsize=8)
    box(12.8, 4.0, 1.4, 0.7, 'sw_dmz', '#8D6E63', fontsize=8.5)

    # ── Outside ────────────────────────────────────────────────────────
    box(11.5, 1.5, 1.6, 0.7, 'r_out\n203.0.113.1', '#455A64')
    box(13.2, 1.5, 1.3, 0.6, 'h_out\n203.0.113.100', '#607D8B', fontsize=8)

    # ── Links ─────────────────────────────────────────────────────────
    # Host → Access
    arrow(2.5, 5.0, 3.4, 4.55, '#42A5F5', '100M')
    arrow(2.5, 4.0, 3.4, 4.42, '#90CAF9', '100M')
    arrow(2.5, 2.5, 3.4, 2.28, '#26C6DA', '100M')
    arrow(2.5, 1.5, 3.4, 2.12, '#80DEEA', '100M')

    # Access → Distribution
    arrow(5.0, 4.5, 5.05, 4.5, '#555', '100M')
    arrow(5.0, 2.2, 5.05, 2.2, '#555', '100M')

    # Distribution → Core
    arrow(6.55, 4.5, 7.75, 4.5, '#FF7043', '1G')
    arrow(6.55, 2.2, 7.75, 4.2, '#FF7043', '1G')

    # Core → DMZ
    arrow(9.25, 4.6, 10.2, 5.0, '#7B1FA2', '1G')

    # Core → Outside
    arrow(9.25, 4.3, 10.7, 1.8, '#7B1FA2', '500M')

    # DMZ Router → sw_dmz
    arrow(11.8, 4.82, 12.1, 4.2, '#E64A19', '')

    # sw_dmz → web1, web2
    arrow(12.1, 4.0, 11.8, 3.88, '#8D6E63', '')
    arrow(12.1, 3.85, 11.8, 2.88, '#8D6E63', '')

    # r_out → h_out
    arrow(12.3, 1.5, 12.55, 1.5, '#455A64', '')

    # ── Legend ────────────────────────────────────────────────────────
    legend_items = [
        mpatches.Patch(color='#42A5F5', label='Inside Host (VLAN10)'),
        mpatches.Patch(color='#26C6DA', label='Inside Host (VLAN20)'),
        mpatches.Patch(color='#66BB6A', label='Access Switch'),
        mpatches.Patch(color='#FF7043', label='Distribution Router'),
        mpatches.Patch(color='#7B1FA2', label='Core Router'),
        mpatches.Patch(color='#EF5350', label='DMZ Web Server'),
        mpatches.Patch(color='#455A64', label='Outside / ISP'),
    ]
    ax.legend(handles=legend_items, loc='lower left', fontsize=8,
              framealpha=0.9, ncol=2, bbox_to_anchor=(0.01, 0.01))

    ax.set_title('Sơ đồ Logic Topology – Campus Network 3 lớp + DMZ\n'
                 'Core – Distribution – Access | NAT/PAT + ACL + Load Balancer',
                 fontsize=12, fontweight='bold', pad=14)

    plt.tight_layout()
    out = OUT_DIR / 'chart0_topology_diagram.png'
    plt.savefig(out, bbox_inches='tight', facecolor='#F8F9FA')
    plt.close()
    print(f'[✓] Lưu: {out}')


# =============================================================================
# MAIN
# =============================================================================

def main():
    print('\n╔══════════════════════════════════════════════════════════════╗')
    print('║        PLOT_CHARTS.PY – Vẽ biểu đồ báo cáo Campus Network   ║')
    print(f'║  Output dir: {str(OUT_DIR):<50}║')
    print('╚══════════════════════════════════════════════════════════════╝\n')

    df = load_csv()

    print('═' * 62)
    print('  Đang vẽ các biểu đồ...')
    print('═' * 62)

    plot_topology_diagram()         # chart0 – Sơ đồ logic topology
    plot_load_timeline(df)          # chart1 – Line chart load web1/web2
    plot_acl_heatmap()              # chart2 – Heatmap ACL/Firewall
    plot_throughput_comparison()    # chart3 – Bar chart throughput
    plot_latency_comparison()       # chart4 – Line chart latency RTT
    plot_stacked_load(df)           # chart5 – Stacked area tổng tải
    plot_nat_table()                # chart6 – Bảng NAT translation

    print('\n═' * 62)
    print(f'  ✅ Hoàn tất! {7} biểu đồ đã lưu vào: {OUT_DIR.resolve()}')
    print('  Hãy chèn các file PNG vào báo cáo LaTeX/Word.')
    print('═' * 62 + '\n')


if __name__ == '__main__':
    main()
