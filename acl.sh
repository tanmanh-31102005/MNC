#!/bin/bash
# =============================================================================
# acl.sh – Áp dụng ACL đa lớp (Standard + Extended + Firewall)
# Vị trí: cùng thư mục với topology.py
#
# Cách dùng:
#   (Tự động) Từ topology.py khi bật --acl → script được gọi với env vars:
#       DIST1_PID, DIST2_PID, DMZ_R_PID, R_OUT_PID
#
#   (Thủ công sau khi Mininet đang chạy):
#       sudo bash acl.sh
#
# Để bãi bỏ: sudo bash dropacl.sh
# =============================================================================
set -euo pipefail

# ── Helper: chạy lệnh trong namespace của node Mininet ──────────────────────
# Nếu chạy thủ công, dùng `sudo m <node> <cmd>` (Mininet CLI helper)
# Nếu gọi từ topology.py, dùng nsenter với PID

run_in_ns() {
    local PID="$1"; shift
    if [ -n "${PID}" ] && [ "${PID}" != "0" ]; then
        nsenter -t "${PID}" -n -- "$@"
    else
        echo "[WARN] PID không hợp lệ cho node, bỏ qua lệnh: $*"
    fi
}

# Lấy PID từ env (truyền bởi topology.py) hoặc từ file pid nếu chạy thủ công
DIST1_PID="${DIST1_PID:-0}"
DIST2_PID="${DIST2_PID:-0}"
DMZ_R_PID="${DMZ_R_PID:-0}"
R_OUT_PID="${R_OUT_PID:-0}"

# Nếu không có PID env, thử đọc từ Mininet process list
if [ "$DIST1_PID" = "0" ]; then
    # Fallback: dùng `sudo mn -c` style – thử tìm PID bằng tên process namespace
    echo "[INFO] Không có PID từ env. Hãy chắc Mininet đang chạy và set env vars."
    echo "       Hoặc dùng lệnh: py apply_acl(net) trong Mininet CLI."
    exit 1
fi

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   ACL.SH – Thiết lập bảo mật đa lớp Campus Network  ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# =============================================================================
# LỚP 1: STANDARD ACL tại Distribution Layer (dist1, dist2)
#   → Lọc theo địa chỉ IP nguồn, đặt gần nguồn nhất
# =============================================================================
echo "▶ [LAYER 1] Standard ACL – Distribution Layer..."

# ── DIST1 (VLAN 10: 172.16.10.0/24) ──────────────────────────────────────
# Chặn host "xấu" giả lập (vd: máy bị nhiễm / vi phạm policy)
run_in_ns "$DIST1_PID" iptables -F FORWARD 2>/dev/null || true
run_in_ns "$DIST1_PID" iptables -P FORWARD ACCEPT

# Standard ACL: chặn 172.16.10.50 (thiết bị không được phép)
run_in_ns "$DIST1_PID" iptables -A FORWARD \
    -s 172.16.10.50 \
    -j LOG --log-prefix "STD_ACL_BLOCK_VLAN10: " --log-level 4
run_in_ns "$DIST1_PID" iptables -A FORWARD -s 172.16.10.50 -j DROP

# Standard ACL: Cho phép toàn bộ VLAN10 còn lại đi qua
run_in_ns "$DIST1_PID" iptables -A FORWARD -s 172.16.10.0/24 -j ACCEPT
run_in_ns "$DIST1_PID" iptables -A FORWARD -d 172.16.10.0/24 -j ACCEPT

echo "  [OK] DIST1 Standard ACL: chặn 172.16.10.50, cho phép /24 còn lại."

# ── DIST2 (VLAN 20: 172.16.20.0/24) ──────────────────────────────────────
run_in_ns "$DIST2_PID" iptables -F FORWARD 2>/dev/null || true
run_in_ns "$DIST2_PID" iptables -P FORWARD ACCEPT

# Chặn dải "suspicious" trong VLAN20
run_in_ns "$DIST2_PID" iptables -A FORWARD \
    -s 172.16.20.50 \
    -j LOG --log-prefix "STD_ACL_BLOCK_VLAN20: " --log-level 4
run_in_ns "$DIST2_PID" iptables -A FORWARD -s 172.16.20.50 -j DROP

run_in_ns "$DIST2_PID" iptables -A FORWARD -s 172.16.20.0/24 -j ACCEPT
run_in_ns "$DIST2_PID" iptables -A FORWARD -d 172.16.20.0/24 -j ACCEPT

echo "  [OK] DIST2 Standard ACL: chặn 172.16.20.50, cho phép /24 còn lại."

# =============================================================================
# LỚP 2: EXTENDED ACL tại DMZ Router (dmz_r)
#   → Lọc theo IP nguồn + port đích + protocol (gần đích)
# =============================================================================
echo ""
echo "▶ [LAYER 2] Extended ACL – DMZ Router Firewall..."

run_in_ns "$DMZ_R_PID" iptables -F FORWARD 2>/dev/null || true
run_in_ns "$DMZ_R_PID" iptables -P FORWARD DROP    # Default deny tại DMZ

# Cho phép kết nối đã được thiết lập (stateful – RELATED/ESTABLISHED)
run_in_ns "$DMZ_R_PID" iptables -A FORWARD \
    -m state --state ESTABLISHED,RELATED -j ACCEPT

# Extended ACL: chỉ cho mạng nội bộ truy cập HTTP/HTTPS vào DMZ
run_in_ns "$DMZ_R_PID" iptables -A FORWARD \
    -s 172.16.0.0/16 -d 10.10.10.0/24 -p tcp --dport 80  -j ACCEPT
run_in_ns "$DMZ_R_PID" iptables -A FORWARD \
    -s 172.16.0.0/16 -d 10.10.10.0/24 -p tcp --dport 443 -j ACCEPT

# Cho phép ICMP từ Inside vào DMZ (debug/giám sát)
run_in_ns "$DMZ_R_PID" iptables -A FORWARD \
    -s 172.16.0.0/16 -d 10.10.10.0/24 -p icmp -j ACCEPT

# Cho phép Outside truy cập HTTP vào DMZ (qua Static NAT)
run_in_ns "$DMZ_R_PID" iptables -A FORWARD \
    -s 203.0.113.0/24 -d 10.10.10.0/24 -p tcp --dport 80 -j ACCEPT
run_in_ns "$DMZ_R_PID" iptables -A FORWARD \
    -s 203.0.113.0/24 -d 10.10.10.0/24 -p tcp --dport 443 -j ACCEPT

# LOG + DROP tất cả gói còn lại tới DMZ (mọi port khác, SSH, v.v.)
run_in_ns "$DMZ_R_PID" iptables -A FORWARD \
    -d 10.10.10.0/24 \
    -j LOG --log-prefix "EXT_ACL_DROP_DMZ: " --log-level 4
run_in_ns "$DMZ_R_PID" iptables -A FORWARD -d 10.10.10.0/24 -j DROP

echo "  [OK] DMZ Extended ACL: chỉ cho HTTP/HTTPS từ Inside/Outside vào DMZ."

# =============================================================================
# LỚP 3: FIREWALL TẦNG BIÊN – Router r_out (Inside↔DMZ↔Outside)
# =============================================================================
echo ""
echo "▶ [LAYER 3] Firewall tầng biên – r_out (ISP side)..."

run_in_ns "$R_OUT_PID" iptables -F FORWARD  2>/dev/null || true
run_in_ns "$R_OUT_PID" iptables -P FORWARD DROP

# Stateful – cho phép kết nối đã thiết lập
run_in_ns "$R_OUT_PID" iptables -A FORWARD \
    -m state --state ESTABLISHED,RELATED -j ACCEPT

# Inside →→ Outside: cho phép HTTP/HTTPS và DNS
run_in_ns "$R_OUT_PID" iptables -A FORWARD \
    -s 172.16.0.0/16 -o rout-eth2 -p tcp -m multiport --dports 80,443 -j ACCEPT
run_in_ns "$R_OUT_PID" iptables -A FORWARD \
    -s 172.16.0.0/16 -o rout-eth2 -p udp --dport 53 -j ACCEPT
run_in_ns "$R_OUT_PID" iptables -A FORWARD \
    -s 172.16.0.0/16 -o rout-eth2 -p icmp -j ACCEPT

# Outside →→ DMZ: chỉ HTTP/HTTPS (Static NAT đã DNAT trước đó)
run_in_ns "$R_OUT_PID" iptables -A FORWARD \
    -i rout-eth2 -d 10.10.10.0/24 -p tcp --dport 80  -j ACCEPT
run_in_ns "$R_OUT_PID" iptables -A FORWARD \
    -i rout-eth2 -d 10.10.10.0/24 -p tcp --dport 443 -j ACCEPT

# Chặn Outside →→ Inside (tuyệt đối ngăn tấn công trực tiếp)
run_in_ns "$R_OUT_PID" iptables -A FORWARD \
    -i rout-eth2 -d 172.16.0.0/16 \
    -j LOG --log-prefix "FW_BORDER_DROP_OUTSIDE→INSIDE: " --log-level 4
run_in_ns "$R_OUT_PID" iptables -A FORWARD \
    -i rout-eth2 -d 172.16.0.0/16 -j DROP

# LOG tất cả gói bị DROP qua r_out
run_in_ns "$R_OUT_PID" iptables -A FORWARD \
    -j LOG --log-prefix "FW_BORDER_DROP_OTHER: " --log-level 4

echo "  [OK] Firewall biên: Inside→Outside (HTTP/HTTPS/DNS), Outside→DMZ (HTTP/HTTPS), Inside←Outside (DROP)."

echo ""
echo "════════════════════════════════════════════════════════"
echo "  ✅ ACL đa lớp đã được áp dụng thành công!"
echo "  Để kiểm tra log chặn gói:"
echo "    sudo dmesg | grep -E 'ACL|EXT_ACL|FW_'"
echo "  Để bãi bỏ ACL: sudo bash dropacl.sh"
echo "════════════════════════════════════════════════════════"
