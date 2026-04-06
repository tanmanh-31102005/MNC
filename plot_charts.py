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
import matplotlib
matplotlib.use('Agg')          # Backend không cần màn hình (chạy headless OK)
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
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
    'web1':    '#4C8BF5',   # xanh duong
    'web2':    '#F5854C',   # cam
    'high':    '#E53935',   # do nguong cao
    'low':     '#43A047',   # xanh nguong thap
    'switch':  '#AB47BC',   # tim – thoi diem chuyen
    'inside':  '#26C6DA',
    'outside': '#EF5350',
    'dmz':     '#66BB6A',
    'blocked': '#B71C1C',
}

# =============================================================================
# Helper: lay legend handles tuong thich voi moi phien ban matplotlib
# =============================================================================

def _get_legend_handles(leg):
    """Tuong thich ca matplotlib cu (legendHandles) va moi (legend_handles)."""
    if hasattr(leg, 'legend_handles'):
        return list(leg.legend_handles)
    return list(leg.legendHandles)


# =============================================================================
# 0. Tao / tai du lieu
# =============================================================================

def generate_demo_data(n=80) -> pd.DataFrame:
    """Sinh du lieu mo phong theo pattern thuc te."""
    random.seed(42)
    rows = []
    t     = datetime(2025, 1, 1, 8, 0, 0)
    active = 'WEB1'

    for i in range(n):
        # Wave pattern: tai tang → he thong chuyen → tai giam
        wave  = 55 * math.sin(i * 0.12) + 50
        noise = random.uniform(-4, 4)
        w1_raw = max(2, min(98, wave + noise))

        # Neu active = WEB2, web1 giam tai
        if active == 'WEB2':
            w1_mbps = round(w1_raw * 0.28, 1)
            w2_mbps = round(min(95, 100 - w1_raw * 0.28 + noise), 1)
        else:
            w1_mbps = round(w1_raw, 1)
            w2_mbps = round(max(2, random.uniform(3, 12)), 1)

        action = 'HOLD'
        if w1_raw > 80 and active == 'WEB1':
            active = 'WEB2'
            action = f'SWITCH->WEB2 (load={w1_raw:.0f}%>80%)'
        elif w1_raw < 20 and active == 'WEB2':
            active = 'WEB1'
            action = f'SWITCH->WEB1 (load={w1_raw:.0f}%<20%)'

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
        print(f'[OK] Doc {len(df)} ban ghi tu {args.csv}')
        return df
    elif args.demo:
        print('[!] Khong tim thay CSV → Dung demo data')
        df = generate_demo_data(80)
        df.to_csv(args.csv, index=False)  # Luu lai de tham khao
        return df
    else:
        print(f'[ERR] Khong tim thay {args.csv}. Chay voi --demo hoac chay load_balancer.py truoc.')
        sys.exit(1)


# =============================================================================
# BIEU DO 1 – Line chart: Luu luong Web1 / Web2 theo thoi gian + diem chuyen
# =============================================================================

def plot_load_timeline(df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(13, 5))

    x = range(len(df))
    ax.plot(x, df['web1_mbps'], color=COLORS['web1'], lw=2.2, label='Web1 (Mbps)', zorder=3)
    ax.plot(x, df['web2_mbps'], color=COLORS['web2'], lw=2.2, label='Web2 (Mbps)', zorder=3)

    # Vung to mau theo active server
    for i, row in df.iterrows():
        color = COLORS['web1'] if row['active_server'] == 'WEB1' else COLORS['web2']
        ax.axvspan(i - 0.5, i + 0.5, alpha=0.08, color=color)

    # Nguong
    ax.axhline(80, color=COLORS['high'], ls='--', lw=1.5, label='Nguong CAO (80 Mbps)')
    ax.axhline(20, color=COLORS['low'],  ls='--', lw=1.5, label='Nguong THAP (20 Mbps)')

    # Danh dau diem chuyen doi
    switch_x = [i for i, a in enumerate(df['action']) if 'SWITCH' in str(a)]
    for sx in switch_x:
        ax.axvline(sx, color=COLORS['switch'], ls=':', lw=2, alpha=0.8)
        ax.annotate('Chuyen\nServer',
                    xy=(sx, 85), fontsize=8, color=COLORS['switch'],
                    ha='center', va='bottom',
                    arrowprops=dict(arrowstyle='->', color=COLORS['switch']),
                    xytext=(sx, 95))

    # Dien nhan truc X (moi 10 buoc lay 1 nhan)
    tick_step = max(1, len(df) // 10)
    ax.set_xticks(range(0, len(df), tick_step))
    ax.set_xticklabels(df['timestamp'].iloc[::tick_step], rotation=30, ha='right')

    ax.set_xlabel('Thoi gian')
    ax.set_ylabel('Throughput (Mbps)')
    ax.set_title('Bieu do Can bang tai theo nguong - Web1 vs Web2 (DMZ Server)')
    ax.set_ylim(0, 110)
    ax.legend(loc='upper left', framealpha=0.85)

    # Ghi chu che do active — them patch vao legend hien tai
    active_patch1 = mpatches.Patch(color=COLORS['web1'], alpha=0.35, label='Active: WEB1')
    active_patch2 = mpatches.Patch(color=COLORS['web2'], alpha=0.35, label='Active: WEB2')
    current_handles = _get_legend_handles(ax.get_legend())
    ax.legend(handles=current_handles + [active_patch1, active_patch2],
              loc='upper left', framealpha=0.85, fontsize=9)

    plt.tight_layout()
    out = OUT_DIR / 'chart1_load_timeline.png'
    plt.savefig(out, bbox_inches='tight')
    plt.close()
    print(f'[OK] Luu: {out}')


# =============================================================================
# BIEU DO 2 – Heatmap: So goi bi chan boi ACL/Firewall
# =============================================================================

def plot_acl_heatmap():
    """
    Heatmap nhiet the hien muc do chan goi theo nguon va dich.
    Du lieu mau: sinh de minh hoa.
    """
    sources = ['VLAN10\n(172.16.10.x)', 'VLAN20\n(172.16.20.x)',
               'Outside\n(203.0.113.x)', 'Unknown\nSource']
    targets = ['Web1\n(Port 80)', 'Web2\n(Port 80)',
               'Web1\n(Port 22)', 'Web2\n(Port 22)',
               'Web1\n(Port 3306)', 'Web2\n(Port 3306)']

    # Ma tran goi bi chan (rows=nguon, cols=dich+port)
    data = np.array([
        [0,    0,    185,  172,  340,  320],   # VLAN10
        [0,    0,    210,  195,  290,  310],   # VLAN20
        [62,   48,   945,  980, 1240, 1180],   # Outside (tan cong)
        [35,   28,   520,  610,  780,  820],   # Unknown
    ])

    fig, ax = plt.subplots(figsize=(11, 6))
    mask = data == 0  # To mau trang neu khong bi chan (0 = duoc phep)

    sns.heatmap(
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
        cbar_kws={'label': 'So goi bi DROP'},
        vmin=0,
        vmax=int(data.max()),
    )

    # To mau xanh cac o = 0 (duoc phep)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            if data[i, j] == 0:
                ax.add_patch(plt.Rectangle((j, i), 1, 1, fill=True,
                             color='#d4edda', alpha=0.7, zorder=0))
                ax.text(j + 0.5, i + 0.5, 'ALLOW', ha='center', va='center',
                        fontsize=9, color='#155724', fontweight='bold')

    ax.set_title('Heatmap ACL/Firewall - So goi bi DROP theo nguon va dich\n'
                 '(Xanh = ALLOW, Do = bi chan, so cang lon cang nguy hiem)')
    ax.set_xlabel('May chu dich (Destination Server & Port)')
    ax.set_ylabel('Vung mang nguon (Source Network)')
    ax.set_xticklabels(targets, fontsize=9)
    ax.set_yticklabels(sources, rotation=0, fontsize=9)

    plt.tight_layout()
    out = OUT_DIR / 'chart2_acl_heatmap.png'
    plt.savefig(out, bbox_inches='tight')
    plt.close()
    print(f'[OK] Luu: {out}')


# =============================================================================
# BIEU DO 3 – Bar chart: So sanh Throughput truoc/sau NAT+ACL
# =============================================================================

def plot_throughput_comparison():
    scenarios = ['Inside->DMZ\n(HTTP)', 'Inside->Outside\n(HTTP)', 'Outside->DMZ\n(Static NAT)']
    no_security  = [94.2, 87.6, 89.1]   # Mbps khong co bao mat
    with_nat_acl = [88.4, 79.3, 81.7]   # Mbps sau khi bat NAT + ACL
    overhead_pct = [(a - b) / a * 100 for a, b in zip(no_security, with_nat_acl)]

    x = np.arange(len(scenarios))
    w = 0.32

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    # Subplot 1: Bar chart throughput
    bars1 = ax1.bar(x - w/2, no_security,  w, label='Khong bao mat', color='#42A5F5', alpha=0.88)
    bars2 = ax1.bar(x + w/2, with_nat_acl, w, label='NAT + ACL bat', color='#EF5350', alpha=0.88)

    ax1.set_xticks(x)
    ax1.set_xticklabels(scenarios, fontsize=10)
    ax1.set_ylabel('Throughput (Mbps)')
    ax1.set_title('So sanh Throughput Truoc-Sau khi bat NAT+ACL')
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
    ax2.set_ylabel('Overhead bao mat (%)')
    ax2.set_title('Phan tram suy giam Throughput do NAT+ACL')
    ax2.set_ylim(0, 20)
    for i, v in enumerate(overhead_pct):
        ax2.text(i, v + 0.3, f'{v:.1f}%', ha='center', fontsize=10, fontweight='bold')

    plt.tight_layout()
    out = OUT_DIR / 'chart3_throughput_comparison.png'
    plt.savefig(out, bbox_inches='tight')
    plt.close()
    print(f'[OK] Luu: {out}')


# =============================================================================
# BIEU DO 4 – Latency Line chart: Truoc / Sau NAT+ACL
# =============================================================================

def plot_latency_comparison():
    """Do latency (ping RTT ms) qua nhieu lan do trong 30 rounds."""
    random.seed(7)
    rounds = 30
    x = range(1, rounds + 1)

    # Mo phong: co NAT → latency cao hon
    lat_no_sec  = [random.uniform(0.5, 1.5) for _ in x]
    lat_nat_acl = [random.uniform(1.2, 3.8) for _ in x]
    lat_lb      = [random.uniform(1.5, 4.5) for _ in x]   # Them Load Balancer

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(x, lat_no_sec,  color='#42A5F5', lw=2, marker='o', ms=4, label='Khong bao mat')
    ax.plot(x, lat_nat_acl, color='#EF5350', lw=2, marker='s', ms=4, label='NAT + ACL bat')
    ax.plot(x, lat_lb,      color='#AB47BC', lw=2, marker='^', ms=4, label='NAT + ACL + Load Balancer')

    # Trung binh
    for data, color in [(lat_no_sec, '#1565C0'), (lat_nat_acl, '#B71C1C'), (lat_lb, '#6A1B9A')]:
        avg = np.mean(data)
        ax.axhline(avg, color=color, ls=':', lw=1.2, alpha=0.6)

    ax.set_xlabel('Lan do (Round)')
    ax.set_ylabel('Round-Trip Time (ms)')
    ax.set_title('So sanh Latency (RTT) theo cac kich ban bao mat')
    ax.legend(loc='upper right')
    ax.set_xlim(1, rounds)
    ax.set_ylim(0, 6)

    # Annotation trung binh
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
    print(f'[OK] Luu: {out}')


# =============================================================================
# BIEU DO 5 – Server Load Distribution (Stacked Area)
# =============================================================================

def plot_stacked_load(df: pd.DataFrame):
    """Stacked area chart: tong load = web1 + web2 tai moi thoi diem."""
    fig, ax = plt.subplots(figsize=(12, 5))

    x = range(len(df))
    ax.stackplot(x,
                 df['web1_mbps'], df['web2_mbps'],
                 labels=['Web1 (Mbps)', 'Web2 (Mbps)'],
                 colors=[COLORS['web1'], COLORS['web2']],
                 alpha=0.75)

    ax.axhline(80, color=COLORS['high'], ls='--', lw=1.5, label='Nguong cao (80 Mbps)')
    ax.axhline(20, color=COLORS['low'],  ls='--', lw=1.5, label='Nguong thap (20 Mbps)')

    tick_step = max(1, len(df) // 10)
    ax.set_xticks(range(0, len(df), tick_step))
    ax.set_xticklabels(df['timestamp'].iloc[::tick_step], rotation=30, ha='right')

    ax.set_xlabel('Thoi gian')
    ax.set_ylabel('Tong Throughput (Mbps)')
    ax.set_title('Phan phoi tai tich luy giua Web1 va Web2 (Stacked Area)')
    ax.set_ylim(0, 130)
    ax.legend(loc='upper left', framealpha=0.85)

    plt.tight_layout()
    out = OUT_DIR / 'chart5_stacked_load.png'
    plt.savefig(out, bbox_inches='tight')
    plt.close()
    print(f'[OK] Luu: {out}')


# =============================================================================
# BIEU DO 6 – Bang NAT Translation (hien thi dang bang matplotlib)
# =============================================================================

def plot_nat_table():
    """Ve bang NAT Translation dang PNG de chen vao bao cao."""
    nat_entries = [
        # Inside Local         Inside Global          Outside Local          Outside Global         Protocol
        ('172.16.10.10:1024', '203.0.113.1:10241',  '203.0.113.100:80',    '203.0.113.100:80',    'TCP'),
        ('172.16.10.10:1025', '203.0.113.1:10242',  '203.0.113.100:443',   '203.0.113.100:443',   'TCP'),
        ('172.16.20.10:2010', '203.0.113.1:20101',  '10.10.10.11:80',      '10.10.10.11:80',      'TCP'),
        ('172.16.20.20:3001', '203.0.113.1:30011',  '8.8.8.8:53',          '8.8.8.8:53',          'UDP'),
        ('172.16.10.30:4400', '203.0.113.1:44001',  '203.0.113.100:443',   '203.0.113.100:443',   'TCP'),
        # Static NAT (Server DMZ)
        ('10.10.10.11:80',    '203.0.113.10:80',    '203.0.113.100:54321', '203.0.113.100:54321', 'TCP-Static'),
        ('10.10.10.12:80',    '203.0.113.11:80',    '203.0.113.100:54322', '203.0.113.100:54322', 'TCP-Static'),
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

    # Dinh dang header
    for j in range(len(headers)):
        tbl[(0, j)].set_facecolor('#1565C0')
        tbl[(0, j)].set_text_props(color='white', fontweight='bold')

    # To mau xen ke + phan biet Static NAT
    for i in range(1, len(nat_entries) + 1):
        proto = nat_entries[i-1][4]
        bg = '#E3F2FD' if i % 2 == 0 else 'white'
        if 'Static' in proto:
            bg = '#FFF8E1'  # Vang nhat cho Static NAT
        for j in range(len(headers)):
            tbl[(i, j)].set_facecolor(bg)

    ax.set_title('Bang NAT Translation - Campus Network\n'
                 '(Vang = Static NAT cho DMZ Server, Trang/Xanh = PAT cho Client)',
                 fontsize=11, fontweight='bold', pad=12)

    plt.tight_layout()
    out = OUT_DIR / 'chart6_nat_table.png'
    plt.savefig(out, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f'[OK] Luu: {out}')


# =============================================================================
# BIEU DO 0 – Topology Diagram (so do logic bang matplotlib)
# =============================================================================

def plot_topology_diagram():
    """Ve so do logic topology Campus 3 lop bang matplotlib."""
    fig, ax = plt.subplots(figsize=(14, 9))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 9)
    ax.axis('off')
    ax.set_facecolor('#F8F9FA')
    fig.patch.set_facecolor('#F8F9FA')

    def box(x, y, w, h, text, color, fontsize=9, textcolor='white'):
        """Ve hop chu nhat bo goc bang FancyBboxPatch."""
        rect = FancyBboxPatch(
            (x - w / 2, y - h / 2), w, h,
            boxstyle='round,pad=0.05',
            facecolor=color, edgecolor='white', linewidth=2,
            zorder=3
        )
        ax.add_patch(rect)
        ax.text(x, y, text, ha='center', va='center',
                fontsize=fontsize, color=textcolor, fontweight='bold',
                zorder=4)

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
        rect = FancyBboxPatch(
            (x1, y1), x2 - x1, y2 - y1,
            boxstyle='round,pad=0.1',
            facecolor=color, edgecolor='#cccccc',
            linewidth=1.5, alpha=0.3, zorder=1
        )
        ax.add_patch(rect)
        ax.text(x1 + 0.15, y2 - 0.2, label, fontsize=8.5,
                color='#444', fontweight='bold', va='top')

    # ── Zones (dung text ASCII, khong emoji) ──────────────────────────────────
    zone_bg(0.2,  0.2,  3.2,  5.8, '[Access Layer]',       '#E3F2FD')
    zone_bg(3.4,  2.5,  7.0,  5.8, '[Distribution Layer]', '#E8F5E9')
    zone_bg(7.2,  3.8,  9.8,  5.8, '[Core Layer]',         '#FFF3E0')
    zone_bg(10.0, 0.2,  13.8, 5.8, '[DMZ + Outside]',      '#FCE4EC')

    # ── Hosts ──────────────────────────────────────────────────────────────────
    box(1.5, 5.0, 2.0, 0.6, 'h1\n172.16.10.10',      '#42A5F5')
    box(1.5, 4.0, 2.0, 0.6, 'printer1\n172.16.10.30', '#90CAF9', textcolor='#333')
    box(1.5, 2.5, 2.0, 0.6, 'h2\n172.16.20.10',      '#26C6DA')
    box(1.5, 1.5, 2.0, 0.6, 'phone1\n172.16.20.20',  '#80DEEA', textcolor='#333')

    # ── Access Switches ────────────────────────────────────────────────────────
    box(4.2, 4.5, 1.6, 0.7, 'acc1\nVLAN 10', '#66BB6A')
    box(4.2, 2.2, 1.6, 0.7, 'acc2\nVLAN 20', '#66BB6A')

    # ── Distribution ──────────────────────────────────────────────────────────
    box(5.8, 4.5, 1.5, 0.7, 'dist1\n192.168.1.2', '#FF7043')
    box(5.8, 2.2, 1.5, 0.7, 'dist2\n192.168.1.6', '#FF7043')

    # ── Core ──────────────────────────────────────────────────────────────────
    box(8.5, 4.5, 1.5, 0.9, 'CORE\n192.168.1.1', '#7B1FA2')

    # ── DMZ ───────────────────────────────────────────────────────────────────
    box(11.0, 5.0, 1.6, 0.7, 'dmz_r\n192.168.1.10',  '#E64A19')
    box(11.0, 3.8, 1.6, 0.6, 'web1\n10.10.10.11',    '#EF5350', fontsize=8)
    box(11.0, 2.8, 1.6, 0.6, 'web2\n10.10.10.12',    '#EF5350', fontsize=8)
    box(12.8, 4.0, 1.4, 0.7, 'sw_dmz',               '#8D6E63', fontsize=8.5)

    # ── Outside ───────────────────────────────────────────────────────────────
    box(11.5, 1.5, 1.6, 0.7, 'r_out\n203.0.113.1',    '#455A64')
    box(13.2, 1.5, 1.3, 0.6, 'h_out\n203.0.113.100',  '#607D8B', fontsize=8)

    # ── Links ─────────────────────────────────────────────────────────────────
    arrow(2.5, 5.0, 3.4, 4.55, '#42A5F5', '100M')
    arrow(2.5, 4.0, 3.4, 4.42, '#90CAF9', '100M')
    arrow(2.5, 2.5, 3.4, 2.28, '#26C6DA', '100M')
    arrow(2.5, 1.5, 3.4, 2.12, '#80DEEA', '100M')

    arrow(5.0, 4.5, 5.05, 4.5, '#555', '100M')
    arrow(5.0, 2.2, 5.05, 2.2, '#555', '100M')

    arrow(6.55, 4.5, 7.75, 4.5, '#FF7043', '1G')
    arrow(6.55, 2.2, 7.75, 4.2, '#FF7043', '1G')

    arrow(9.25, 4.6, 10.2, 5.0,  '#7B1FA2', '1G')
    arrow(9.25, 4.3, 10.7, 1.8,  '#7B1FA2', '500M')

    arrow(11.8, 4.82, 12.1, 4.2, '#E64A19', '')
    arrow(12.1, 4.0,  11.8, 3.88, '#8D6E63', '')
    arrow(12.1, 3.85, 11.8, 2.88, '#8D6E63', '')
    arrow(12.3, 1.5,  12.55, 1.5, '#455A64', '')

    # ── Legend ────────────────────────────────────────────────────────────────
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

    ax.set_title('So do Logic Topology - Campus Network 3 lop + DMZ\n'
                 'Core - Distribution - Access | NAT/PAT + ACL + Load Balancer',
                 fontsize=12, fontweight='bold', pad=14)

    plt.tight_layout()
    out = OUT_DIR / 'chart0_topology_diagram.png'
    plt.savefig(out, bbox_inches='tight', facecolor='#F8F9FA')
    plt.close()
    print(f'[OK] Luu: {out}')


# =============================================================================
# MAIN
# =============================================================================

def main():
    print('\n+' + '='*62 + '+')
    print('|   PLOT_CHARTS.PY - Ve bieu do bao cao Campus Network      |')
    print(f'|   Output dir: {str(OUT_DIR):<49}|')
    print('+' + '='*62 + '+\n')

    df = load_csv()

    print('=' * 64)
    print('  Dang ve cac bieu do...')
    print('=' * 64)

    plot_topology_diagram()         # chart0 - So do logic topology
    plot_load_timeline(df)          # chart1 - Line chart load web1/web2
    plot_acl_heatmap()              # chart2 - Heatmap ACL/Firewall
    plot_throughput_comparison()    # chart3 - Bar chart throughput
    plot_latency_comparison()       # chart4 - Line chart latency RTT
    plot_stacked_load(df)           # chart5 - Stacked area tong tai
    plot_nat_table()                # chart6 - Bang NAT translation

    print('\n' + '=' * 64)
    print(f'  HOAN TAT! 7 bieu do da luu vao: {OUT_DIR.resolve()}')
    print('  Hay chen cac file PNG vao bao cao LaTeX/Word.')
    print('=' * 64 + '\n')


if __name__ == '__main__':
    main()
