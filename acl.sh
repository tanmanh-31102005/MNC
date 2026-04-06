#!/bin/bash
# =============================================================================
# acl.sh – Áp dụng ACL đa lớp (Standard + Extended + Firewall)
#
# Cách dùng:
#   sudo bash acl.sh          ← chạy thủ công khi Mininet đang chạy
#   py apply_acl(net)         ← từ Mininet CLI
#
# Để bãi bỏ: sudo bash dropacl.sh
# =============================================================================
# NOTE: Dùng `sudo m NODE iptables ...` trực tiếp thay vì nsenter+PID
#       vì PID từ 'sudo m NODE bash -c echo $$' là process tạm thời → invalid
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

ok()   { echo -e "  ${GREEN}[OK]${RESET}   $*"; }
info() { echo -e "  ${CYAN}[INFO]${RESET} $*"; }
warn() { echo -e "  ${YELLOW}[WARN]${RESET} $*"; }
err()  { echo -e "  ${RED}[ERR]${RESET}  $*"; }

# =============================================================================
# Helper: chạy iptables trong namespace của Mininet node
# Dùng "sudo m NODE cmd" – đây là cách ĐÚNG và ĐƠN GIẢN nhất
# =============================================================================
ipt() {
    local NODE="$1"; shift
    sudo m "$NODE" iptables "$@" 2>/dev/null || \
        warn "[$NODE] iptables $* → lỗi (bỏ qua)"
}

# =============================================================================
# Kiểm tra Mininet đang chạy
# =============================================================================
echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║   ACL.SH – Thiết lập bảo mật đa lớp Campus Network  ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════╝${RESET}"
echo ""

info "Kiểm tra Mininet..."
if ! sudo m core hostname &>/dev/null; then
    err "Mininet chưa chạy! Hãy chạy: sudo python3 topology.py trước."
    exit 1
fi
ok "Mininet đang hoạt động."
echo ""

# =============================================================================
# LỚP 1: STANDARD ACL – Distribution Layer (dist1, dist2)
#   Lọc theo IP nguồn, đặt gần nguồn nhất
# =============================================================================
echo -e "${BOLD}▶ [LỚP 1] Standard ACL – Distribution Layer${RESET}"

# ── DIST1 (VLAN 10: 172.16.10.0/24) ─────────────────────────────────────────
ipt dist1 -F FORWARD
ipt dist1 -P FORWARD ACCEPT

# Chặn thiết bị "xấu" giả lập
ipt dist1 -A FORWARD -s 172.16.10.50 \
    -j LOG --log-prefix "STD_ACL_BLOCK_VLAN10: " --log-level 4
ipt dist1 -A FORWARD -s 172.16.10.50 -j DROP

# Cho phép VLAN10 còn lại
ipt dist1 -A FORWARD -s 172.16.10.0/24 -j ACCEPT
ipt dist1 -A FORWARD -d 172.16.10.0/24 -j ACCEPT

ok "dist1: chặn 172.16.10.50, cho phép /24 còn lại."

# ── DIST2 (VLAN 20: 172.16.20.0/24) ─────────────────────────────────────────
ipt dist2 -F FORWARD
ipt dist2 -P FORWARD ACCEPT

ipt dist2 -A FORWARD -s 172.16.20.50 \
    -j LOG --log-prefix "STD_ACL_BLOCK_VLAN20: " --log-level 4
ipt dist2 -A FORWARD -s 172.16.20.50 -j DROP

ipt dist2 -A FORWARD -s 172.16.20.0/24 -j ACCEPT
ipt dist2 -A FORWARD -d 172.16.20.0/24 -j ACCEPT

ok "dist2: chặn 172.16.20.50, cho phép /24 còn lại."

# =============================================================================
# LỚP 2: EXTENDED ACL – DMZ Router (dmz_r)
#   Lọc theo IP + port + protocol, gần đích nhất
# =============================================================================
echo ""
echo -e "${BOLD}▶ [LỚP 2] Extended ACL – DMZ Router Firewall${RESET}"

ipt dmz_r -F FORWARD
ipt dmz_r -P FORWARD DROP    # Default deny tại DMZ

# Stateful: cho phép kết nối đã thiết lập
ipt dmz_r -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT

# Cho phép Inside → DMZ: HTTP/HTTPS + ICMP
ipt dmz_r -A FORWARD -s 172.16.0.0/16 -d 10.10.10.0/24 -p tcp --dport 80  -j ACCEPT
ipt dmz_r -A FORWARD -s 172.16.0.0/16 -d 10.10.10.0/24 -p tcp --dport 443 -j ACCEPT
ipt dmz_r -A FORWARD -s 172.16.0.0/16 -d 10.10.10.0/24 -p icmp           -j ACCEPT

# Cho phép Outside → DMZ: HTTP/HTTPS (qua Static NAT)
ipt dmz_r -A FORWARD -s 203.0.113.0/24 -d 10.10.10.0/24 -p tcp --dport 80  -j ACCEPT
ipt dmz_r -A FORWARD -s 203.0.113.0/24 -d 10.10.10.0/24 -p tcp --dport 443 -j ACCEPT

# LOG + DROP phần còn lại vào DMZ
ipt dmz_r -A FORWARD -d 10.10.10.0/24 \
    -j LOG --log-prefix "EXT_ACL_DROP_DMZ: " --log-level 4
ipt dmz_r -A FORWARD -d 10.10.10.0/24 -j DROP

ok "dmz_r: HTTP/HTTPS từ Inside/Outside vào DMZ, DROP phần còn lại."

# =============================================================================
# LỚP 3: FIREWALL BIÊN – r_out (Inside↔DMZ↔Outside)
# =============================================================================
echo ""
echo -e "${BOLD}▶ [LỚP 3] Firewall biên – r_out (ISP side)${RESET}"

ipt r_out -F FORWARD
ipt r_out -P FORWARD DROP

# Stateful
ipt r_out -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT

# Inside → Outside: HTTP/HTTPS + DNS + ICMP
ipt r_out -A FORWARD -s 172.16.0.0/16 -o rout-eth2 -p tcp -m multiport --dports 80,443 -j ACCEPT
ipt r_out -A FORWARD -s 172.16.0.0/16 -o rout-eth2 -p udp --dport 53 -j ACCEPT
ipt r_out -A FORWARD -s 172.16.0.0/16 -o rout-eth2 -p icmp -j ACCEPT

# Outside → DMZ: HTTP/HTTPS (sau DNAT)
ipt r_out -A FORWARD -i rout-eth2 -d 10.10.10.0/24 -p tcp --dport 80  -j ACCEPT
ipt r_out -A FORWARD -i rout-eth2 -d 10.10.10.0/24 -p tcp --dport 443 -j ACCEPT

# Outside → Inside: CHẶN TUYỆT ĐỐI
ipt r_out -A FORWARD -i rout-eth2 -d 172.16.0.0/16 \
    -j LOG --log-prefix "FW_BORDER_DROP_OUTSIDE→INSIDE: " --log-level 4
ipt r_out -A FORWARD -i rout-eth2 -d 172.16.0.0/16 -j DROP

# LOG phần còn lại
ipt r_out -A FORWARD -j LOG --log-prefix "FW_BORDER_DROP_OTHER: " --log-level 4

ok "r_out: Inside→Outside OK, Outside→DMZ OK, Outside→Inside DROP."

# =============================================================================
# Kết quả
# =============================================================================
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════${RESET}"
echo -e "${GREEN}  ✅ ACL đa lớp đã được áp dụng thành công!${RESET}"
echo    ""
echo    "  Kiểm tra rules đã áp dụng:"
echo    "    sudo m dist1 iptables -L FORWARD -n --line-numbers"
echo    "    sudo m dmz_r iptables -L FORWARD -n --line-numbers"
echo    "    sudo m r_out iptables -L FORWARD -n --line-numbers"
echo    ""
echo    "  Xem log gói bị chặn:"
echo    "    sudo dmesg | grep -E 'ACL|EXT_ACL|FW_BORDER'"
echo    ""
echo    "  Để bãi bỏ ACL:"
echo    "    sudo bash dropacl.sh"
echo -e "${GREEN}════════════════════════════════════════════════════════${RESET}"
echo ""
