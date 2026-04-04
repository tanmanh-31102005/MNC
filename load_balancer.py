#!/usr/bin/env python3
# =============================================================================
# load_balancer.py – Giám sát tải và điều hướng lưu lượng theo ngưỡng
# =============================================================================
# Cách chạy (trên Ubuntu/WSL khi Mininet đang chạy):
#
#   # Terminal 1: chạy topology
#   sudo python3 topology.py
#
#   # Terminal 2: sinh traffic từ h1 → web1 (bên trong Mininet)
#   sudo mn -c   # (nếu cần reset)
#
#   # Trong Mininet CLI (Terminal 1):
#   h1 iperf3 -s &
#   web1 iperf3 -c 172.16.10.10 -t 60 -b 90M &   # tải cao → trigger switch
#
#   # Terminal 2: chạy giám sát
#   sudo python3 load_balancer.py --node r_out --iface rout-eth2
#
# =============================================================================

import os
import sys
import time
import subprocess
import csv
import argparse
import signal
import random
from datetime import datetime

# ─── Tham số cấu hình ────────────────────────────────────────────────────────
WEB1_IP        = '10.10.10.11'
WEB2_IP        = '10.10.10.12'
PUBLIC_VIP     = '203.0.113.10'   # Virtual IP của Load Balancer (Static NAT)
THRESHOLD_HIGH = 80               # (%) hoặc Mbps – chuyển sang web2 khi vượt
THRESHOLD_LOW  = 20               # (%) hoặc Mbps – chuyển về web1 khi giảm
LOG_FILE       = 'load_log.csv'
INTERVAL_SEC   = 2                # Chu kỳ polling (giây)

# ─── Trạng thái toàn cục ─────────────────────────────────────────────────────
CURRENT_ACTIVE = 'WEB1'
LB_PROCESS_PID = None            # PID node r_out trong Mininet (nsenter)

# ─── Đối số dòng lệnh ────────────────────────────────────────────────────────
ap = argparse.ArgumentParser(description='Load Balancer Monitor')
ap.add_argument('--node',   default='r_out',    help='Tên Mininet node làm gateway NAT')
ap.add_argument('--iface',  default='rout-eth2', help='Interface hướng Internet của node')
ap.add_argument('--pid',    default='',         help='PID của node (để dùng nsenter)')
ap.add_argument('--demo',   action='store_true', help='Chế độ demo: dùng random load thay vì đọc thực')
ap.add_argument('--maxbw',  type=float, default=100.0, help='Băng thông tối đa ước tính (Mbps)')
args = ap.parse_args()


# =============================================================================
# 1. Đọc băng thông thực từ /sys (nếu trong namespace Mininet)
# =============================================================================

_last_rx_bytes: dict = {}
_last_time: dict     = {}

def read_iface_bytes(pid: str, iface: str) -> int:
    """
    Đọc tổng RX bytes của interface từ namespace của node Mininet.
    Nếu pid='', đọc trực tiếp từ host (fallback).
    """
    stat_path = f'/proc/{pid}/net/dev' if pid else '/proc/net/dev'
    try:
        if pid:
            out = subprocess.check_output(
                ['nsenter', '-t', pid, '-n', '--', 'cat', f'/sys/class/net/{iface}/statistics/rx_bytes'],
                stderr=subprocess.DEVNULL, text=True
            ).strip()
        else:
            # Đọc trực tiếp (chạy bên ngoài Mininet)
            path = f'/sys/class/net/{iface}/statistics/rx_bytes'
            with open(path) as f:
                out = f.read().strip()
        return int(out)
    except Exception:
        return -1


def get_throughput_mbps(pid: str, iface: str) -> float:
    """
    Tính throughput (Mbps) dựa trên delta bytes trong khoảng INTERVAL_SEC.
    Trả về -1 nếu không đọc được.
    """
    key = f'{pid}_{iface}'
    now = time.time()
    cur_bytes = read_iface_bytes(pid, iface)

    if cur_bytes < 0:
        return -1.0

    if key in _last_rx_bytes:
        delta_bytes = cur_bytes - _last_rx_bytes[key]
        delta_time  = now - _last_time[key]
        mbps = (delta_bytes * 8) / (delta_time * 1_000_000) if delta_time > 0 else 0.0
        _last_rx_bytes[key] = cur_bytes
        _last_time[key]     = now
        return max(0.0, mbps)
    else:
        _last_rx_bytes[key] = cur_bytes
        _last_time[key]     = now
        return 0.0


def get_load_demo() -> tuple[float, float]:
    """Chế độ demo: sinh load ngẫu nhiên với pattern tăng/giảm tự nhiên."""
    if not hasattr(get_load_demo, '_t'):
        get_load_demo._t = 0
        get_load_demo._web1 = 30.0
        get_load_demo._web2 = 5.0

    get_load_demo._t += 1
    t = get_load_demo._t

    # Mô phỏng: load tăng dần rồi giảm (wave pattern)
    import math
    wave = 50 * math.sin(t * 0.15) + 50     # 0..100
    noise = random.uniform(-5, 5)

    w1 = max(0, min(100, wave + noise))

    # Khi web1 quá tải → web2 nhận thêm
    if CURRENT_ACTIVE == 'WEB2':
        w2 = max(0, min(100, 100 - wave + noise))
        w1 = max(0, min(100, wave * 0.3 + noise))  # web1 giảm tải
    else:
        w2 = max(0, min(100, random.uniform(2, 15)))

    get_load_demo._web1 = w1
    get_load_demo._web2 = w2
    return round(w1, 1), round(w2, 1)


# =============================================================================
# 2. Điều chỉnh NAT rule để chuyển luồng sang server khác
# =============================================================================

def _run_mn(node: str, *cmd_parts):
    """Chạy lệnh trên Mininet node qua `sudo mn` CLI helper."""
    try:
        subprocess.run(
            ['sudo', 'm', node, *cmd_parts],
            capture_output=True, timeout=5
        )
    except Exception as e:
        print(f'  [ERR] Lỗi khi chạy lệnh trên {node}: {e}')


def _run_ns(pid: str, *cmd_parts):
    """Chạy lệnh trực tiếp trong network namespace qua nsenter."""
    if not pid:
        return
    try:
        subprocess.run(
            ['nsenter', '-t', pid, '-n', '--', *cmd_parts],
            capture_output=True, timeout=5
        )
    except Exception as e:
        print(f'  [ERR] nsenter lỗi: {e}')


def switch_to(target: str, pid: str = ''):
    """
    Chuyển DNAT rule từ server hiện tại sang server mục tiêu.
    target = 'WEB1' | 'WEB2'
    """
    global CURRENT_ACTIVE
    if CURRENT_ACTIVE == target:
        return

    dest_ip = WEB1_IP if target == 'WEB1' else WEB2_IP
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'\n  ⚡ [{ts}] CHUYỂN ĐỔI: {CURRENT_ACTIVE} → {target}  (dest={dest_ip})')

    # Xoá rule cũ PREROUTING
    if pid:
        _run_ns(pid,
            'iptables', '-t', 'nat', '-D', 'PREROUTING',
            '-d', PUBLIC_VIP, '-p', 'tcp', '--dport', '80',
            '-j', 'DNAT', '--to-destination',
            f'{WEB1_IP if CURRENT_ACTIVE == "WEB1" else WEB2_IP}:80')

        # Thêm rule mới
        _run_ns(pid,
            'iptables', '-t', 'nat', '-I', 'PREROUTING', '1',
            '-d', PUBLIC_VIP, '-p', 'tcp', '--dport', '80',
            '-j', 'DNAT', '--to-destination', f'{dest_ip}:80')
    else:
        # Fallback: dùng `sudo m` (Mininet CLI helper)
        _run_mn(args.node,
            'iptables', '-t', 'nat', '-D', 'PREROUTING',
            '-d', PUBLIC_VIP, '-p', 'tcp', '--dport', '80',
            '-j', 'DNAT', '--to-destination',
            f'{WEB1_IP if CURRENT_ACTIVE == "WEB1" else WEB2_IP}:80')
        _run_mn(args.node,
            'iptables', '-t', 'nat', '-I', 'PREROUTING', '1',
            '-d', PUBLIC_VIP, '-p', 'tcp', '--dport', '80',
            '-j', 'DNAT', '--to-destination', f'{dest_ip}:80')

    CURRENT_ACTIVE = target


# =============================================================================
# 3. Vòng lặp giám sát chính
# =============================================================================

def monitor_loop():
    global CURRENT_ACTIVE

    pid = args.pid

    print('╔══════════════════════════════════════════════════════════════════╗')
    print('║  LOAD BALANCER MONITOR – Campus 3-Layer Network                  ║')
    print(f'║  Node: {args.node:<10}  Interface: {args.iface:<15}  Demo: {str(args.demo):<5}  ║')
    print(f'║  Ngưỡng cao: {THRESHOLD_HIGH}%   Ngưỡng thấp: {THRESHOLD_LOW}%    Chu kỳ: {INTERVAL_SEC}s          ║')
    print('╚══════════════════════════════════════════════════════════════════╝')
    print(f'  {"Thời gian":<12} {"Web1 (Mbps)":<15} {"Web2 (Mbps)":<15} {"Active":<10} {"Action"}')
    print('  ' + '─' * 68)

    total_switches = 0

    with open(LOG_FILE, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=[
            'timestamp', 'web1_mbps', 'web2_mbps', 'active_server', 'action'
        ])
        writer.writeheader()

        step = 0
        while True:
            step += 1
            ts = datetime.now().strftime('%H:%M:%S')

            # ── Đọc tải ──────────────────────────────────────────────────
            if args.demo:
                web1_load, web2_load = get_load_demo()
                # Quy đổi % → Mbps theo maxbw
                web1_mbps = web1_load * args.maxbw / 100
                web2_mbps = web2_load * args.maxbw / 100
            else:
                web1_mbps = get_throughput_mbps(pid, args.iface)
                # web2 đo trên cùng interface (giả lập từ log)
                web2_mbps = max(0, args.maxbw - web1_mbps) if web1_mbps >= 0 else 0.0
                if web1_mbps < 0:
                    web1_mbps = 0.0

            # Tính % tải theo maxbw
            load_pct = (web1_mbps / args.maxbw * 100) if args.maxbw > 0 else 0

            # ── Quyết định chuyển đổi ────────────────────────────────────
            action = 'HOLD'
            if load_pct > THRESHOLD_HIGH and CURRENT_ACTIVE == 'WEB1':
                switch_to('WEB2', pid)
                action = f'SWITCH→WEB2 (load={load_pct:.0f}%>{THRESHOLD_HIGH}%)'
                total_switches += 1
            elif load_pct < THRESHOLD_LOW and CURRENT_ACTIVE == 'WEB2':
                switch_to('WEB1', pid)
                action = f'SWITCH→WEB1 (load={load_pct:.0f}%<{THRESHOLD_LOW}%)'
                total_switches += 1

            # ── In trạng thái ─────────────────────────────────────────────
            bar_len = int(load_pct / 5)  # Thanh tiến trình 20 ký tự
            bar = ('█' * bar_len + '░' * (20 - bar_len))[:20]
            active_marker = '⚡WEB1' if CURRENT_ACTIVE == 'WEB1' else '⚡WEB2'

            print(f'  {ts:<12} {web1_mbps:<15.1f} {web2_mbps:<15.1f} {active_marker:<10} [{bar}] {load_pct:.0f}%')

            # ── Ghi log CSV ───────────────────────────────────────────────
            writer.writerow({
                'timestamp':    ts,
                'web1_mbps':    round(web1_mbps, 2),
                'web2_mbps':    round(web2_mbps, 2),
                'active_server': CURRENT_ACTIVE,
                'action':       action,
            })
            csvfile.flush()

            time.sleep(INTERVAL_SEC)


# =============================================================================
# 4. Signal handler để thoát gracefully
# =============================================================================

def _sigint_handler(sig, frame):
    print(f'\n\n  [✓] Giám sát dừng. Log đã lưu tại: {LOG_FILE}')
    print(f'  [✓] Tổng số lần chuyển đổi server: {0}')
    print('  Hãy chạy python3 plot_charts.py để vẽ biểu đồ.\n')
    sys.exit(0)

signal.signal(signal.SIGINT, _sigint_handler)


if __name__ == '__main__':
    monitor_loop()
