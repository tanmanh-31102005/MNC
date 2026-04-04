#!/bin/bash
# =============================================================================
# setup_ospf.sh – Khởi động FRRouting (OSPF) trên tất cả router Mininet
# =============================================================================
# Cách chạy (sau khi topology.py đang chạy):
#   sudo bash setup_ospf.sh
#
# Yêu cầu trước:
#   1. sudo python3 topology.py đang chạy trong Terminal 1
#   2. FRR đã cài: sudo apt install frr frr-pythontools
#
# Sau khi chạy, kiểm tra:
#   sudo mn -c || true   # chỉ nếu cần reset
#   sudo m core  vtysh -c "show ip ospf neighbor"
#   sudo m core  vtysh -c "show ip route ospf"
#   sudo m dist1 vtysh -c "show ip ospf database"
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Màu sắc in ra terminal ───────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET} $*"; }
success() { echo -e "${GREEN}[OK]${RESET}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET} $*"; }
error()   { echo -e "${RED}[ERR]${RESET}  $*"; }

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║      SETUP_OSPF.SH – Triển khai FRR/OSPF Campus Net     ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${RESET}"
echo ""

# =============================================================================
# BƯỚC 1: Kiểm tra FRR đã cài và Mininet đang chạy
# =============================================================================
info "Bước 1: Kiểm tra môi trường..."

if ! command -v zebra &>/dev/null && ! ls /usr/lib/frr/zebra &>/dev/null 2>&1; then
    error "FRR chưa cài. Chạy: sudo apt install frr frr-pythontools"
    exit 1
fi
FRR_ZEBRA=$(find /usr/lib/frr /usr/sbin -name "zebra"  2>/dev/null | head -1)
FRR_OSPFD=$(find /usr/lib/frr /usr/sbin -name "ospfd"  2>/dev/null | head -1)

if [ -z "$FRR_ZEBRA" ]; then
    error "Không tìm thấy binary zebra/ospfd."
    exit 1
fi
success "FRR tìm thấy: zebra=$FRR_ZEBRA, ospfd=$FRR_OSPFD"

# Kiểm tra Mininet node tồn tại (thử ping namespace)
if ! sudo m core echo "OK" &>/dev/null; then
    error "Mininet chưa chạy. Hãy chạy: sudo python3 topology.py trước."
    exit 1
fi
success "Mininet đang chạy (node 'core' phản hồi)."

# =============================================================================
# BƯỚC 2: Dọn dẹp FRR cũ
# =============================================================================
info "Bước 2: Dọn dẹp tiến trình FRR cũ..."

sudo killall -9 zebra ospfd 2>/dev/null || true
sudo rm -f /tmp/zebra-*.pid /tmp/ospfd-*.pid /tmp/zserv-*.api
sleep 1
success "Đã dọn dẹp."

# =============================================================================
# BƯỚC 3: Hàm khởi động FRR trên 1 node
# =============================================================================
# Cú pháp: start_frr_node <node_name> <conf_file> <api_suffix>
start_frr_node() {
    local NODE="$1"
    local CONF="$SCRIPT_DIR/$2"
    local SUFFIX="$3"
    local API="/tmp/zserv-${SUFFIX}.api"
    local ZPID="/tmp/zebra-${SUFFIX}.pid"
    local OPID="/tmp/ospfd-${SUFFIX}.pid"

    if [ ! -f "$CONF" ]; then
        warn "Không tìm thấy config: $CONF → Bỏ qua node $NODE"
        return 1
    fi

    info "  Khởi động FRR trên node: ${BOLD}${NODE}${RESET}"

    # Zebra (quản lý routing table kernel)
    sudo m "$NODE" "$FRR_ZEBRA" \
        -f "$CONF" -d \
        -z "$API" \
        -i "$ZPID" \
        --log-level debugging \
        2>>/tmp/frr-${SUFFIX}-zebra-err.log

    sleep 0.4

    # OSPFd (giao thức OSPF)
    sudo m "$NODE" "$FRR_OSPFD" \
        -f "$CONF" -d \
        -z "$API" \
        -i "$OPID" \
        --log-level debugging \
        2>>/tmp/frr-${SUFFIX}-ospfd-err.log

    sleep 0.3
    success "  ${NODE} → zebra + ospfd đã khởi động."
}

# =============================================================================
# BƯỚC 4: Khởi động lần lượt từng router
# =============================================================================
info "Bước 3: Khởi động FRR trên các router..."
echo ""

start_frr_node "core"  "frr_core.conf"  "core"
start_frr_node "dist1" "frr_dist1.conf" "dist1"
start_frr_node "dist2" "frr_dist2.conf" "dist2"
start_frr_node "dmz_r" "frr_dmz.conf"  "dmz"
start_frr_node "r_out" "frr_rout.conf" "rout"

# =============================================================================
# BƯỚC 5: Chờ OSPF hội tụ
# =============================================================================
echo ""
info "Bước 4: Chờ OSPF hội tụ (15 giây)..."
for i in $(seq 15 -1 1); do
    printf "\r  Còn lại: %2d giây...  " "$i"
    sleep 1
done
echo ""

# =============================================================================
# BƯỚC 6: Kiểm tra kết quả
# =============================================================================
info "Bước 5: Kiểm tra bảng OSPF trên Core..."
echo ""
echo -e "  ${BOLD}─── OSPF Neighbors (core) ───${RESET}"
sudo m core vtysh -c "show ip ospf neighbor" 2>/dev/null || \
    warn "vtysh chưa sẵn sàng. Thử lại sau 10s: sudo m core vtysh -c 'show ip ospf neighbor'"

echo ""
echo -e "  ${BOLD}─── IP Route bảng định tuyến (core) ───${RESET}"
sudo m core ip route

echo ""
echo -e "  ${BOLD}─── Ping test: dist1 → dmz web1 ───${RESET}"
sudo m dist1 ping -c 3 -W 1 10.10.10.11 2>/dev/null || warn "Ping thất bại – kiểm tra lại."

echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════${RESET}"
echo -e "${GREEN}  ✅ OSPF đã triển khai xong!${RESET}"
echo    "  Lệnh kiểm tra hữu ích:"
echo    "    sudo m core  vtysh -c 'show ip ospf neighbor'"
echo    "    sudo m core  vtysh -c 'show ip route ospf'"
echo    "    sudo m dist1 vtysh -c 'show ip ospf database'"
echo    "    sudo m dmz_r ping -c 3 172.16.10.10"
echo    ""
echo    "  Log FRR tại: /tmp/frr-*.log"
echo -e "${GREEN}════════════════════════════════════════════════════════${RESET}"
echo ""
