#!/bin/bash

# ==============================================================================
#  E11 Device Flashing Script for Linux
# ==============================================================================
#  Author: Antigravity Code Assistant
#  Description: An interactive, robust bash script to flash the E11 device.
#               Supports SKU variants: MC6, PDC6, PEC6.
# ==============================================================================

# Exit on interrupt
trap 'echo -e "\n${RED}Flashing aborted by user.${NC}"; exit 1' INT

# ANSI Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Helper for print messages
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_err() { echo -e "${RED}[ERROR]${NC} $1"; }

# ------------------------------------------------------------------------------
# 0. ARGUMENT PARSING
# ------------------------------------------------------------------------------
sku=""
auto_yes=false
wipe_data=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        -m|--model)
            sku="${2:-}"
            shift 2
            ;;
        -y|--yes)
            auto_yes=true
            shift
            ;;
        --wipe)
            wipe_data=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Validate SKU if provided via -m
if [ -n "$sku" ]; then
    case "${sku^^}" in
        MC6|PDC6|PEC6)
            sku="${sku^^}"
            ;;
        *)
            log_err "Invalid SKU via -m: $sku. Must be MC6, PDC6, or PEC6."
            exit 1
            ;;
    esac
fi

# ------------------------------------------------------------------------------
# 1. ENVIRONMENT & TOOL CHECK
# ------------------------------------------------------------------------------
log_info "Verifying required tools..."

MISSING_TOOLS=0
for tool in adb fastboot; do
    if ! command -v $tool &> /dev/null; then
        log_err "$tool is not installed or not in your system PATH."
        MISSING_TOOLS=1
    else
        version=$($tool --version | head -n 1)
        log_success "Found $tool: $version"
    fi
done

if [ $MISSING_TOOLS -ne 0 ]; then
    log_err "Please install android-sdk-platform-tools (adb & fastboot) before running this script."
    log_err "On Debian/Ubuntu: sudo apt-get install android-tools-adb android-tools-fastboot"
    exit 1
fi

# ------------------------------------------------------------------------------
# 2. SKU VARIANT SELECTION
# ------------------------------------------------------------------------------
if [ -n "$sku" ]; then
    log_info "SKU set via argument: $sku"
else
    echo -e "\n${CYAN}========================================= ${NC}"
    echo -e "${CYAN}        E11 SKU VARIANT SELECTION        ${NC}"
    echo -e "${CYAN}========================================= ${NC}"
    echo -e "Please select your device SKU variant:"
    echo -e " 1) MC6"
    echo -e " 2) PDC6"
    echo -e " 3) PEC6"
    echo -n "Enter option (1-3): "
    read -r choice

    case $choice in
        1)
            sku="MC6"
            ;;
        2)
            sku="PDC6"
            ;;
        3)
            sku="PEC6"
            ;;
        *)
            log_err "Invalid selection. Exiting."
            exit 1
            ;;
    esac
fi

sku_lower="${sku,,}"
log_success "You selected SKU: $sku"

# ------------------------------------------------------------------------------
# 3. FIRMWARE FILE INTEGRITY VERIFICATION
# ------------------------------------------------------------------------------
log_info "Verifying firmware files for $sku..."

# Paths to common files
INIT_BOOT="init_boot.img"
PVMFW="pvmfw.img"
SYSTEM="system.img"
SYSTEM_EXT="system_ext-suletta.img"
SUPER_EMPTY=""   # not used — see partition prep section below
VBMETA_IMG="${VBMETA_IMG:-}"

# Resolve script directory unconditionally — used by all auto-detect below
SCRIPT_ABS="$(cd "$(dirname "$0")" && pwd)"

# Auto-detect vbmeta_verification_disabled.img (prefer) or vbmeta.img
# Lookup order:
#   1. Environment variable VBMETA_IMG (user override)
#   2. Deb-installed location: /usr/share/FlashTool/assets/e11/ (installed via .deb)
#   3. Script-adjacent directory (standalone / dev use)
#   4. Parent directory search (fallback)
if [ -z "$VBMETA_IMG" ]; then
    DEB_ASSET_DIR="/usr/share/FlashTool/assets/e11"
    for name in vbmeta_verification_disabled.img vbmeta.img; do
        [ -f "$DEB_ASSET_DIR/$name" ] && VBMETA_IMG="$DEB_ASSET_DIR/$name" && break
    done
fi
if [ -z "$VBMETA_IMG" ]; then
    for name in vbmeta_verification_disabled.img vbmeta.img; do
        [ -f "$SCRIPT_ABS/$name" ] && VBMETA_IMG="$SCRIPT_ABS/$name" && break
    done
fi
if [ -z "$VBMETA_IMG" ]; then
    found=$(find "$(dirname "$SCRIPT_ABS")" -maxdepth 3 \
        \( -name "vbmeta_verification_disabled.img" -o -name "vbmeta.img" \) \
        ! -path "$SCRIPT_ABS/*" 2>/dev/null | sort | head -1)
    [ -n "$found" ] && VBMETA_IMG="$found"
fi

# Print resolved asset paths so user can confirm detection
echo -e "\n${CYAN}========================================= ${NC}"
echo -e "${CYAN}          RESOLVED ASSET PATHS           ${NC}"
echo -e "${CYAN}========================================= ${NC}"
if [ -n "$VBMETA_IMG" ]; then
    log_success "vbmeta image  : $VBMETA_IMG"
else
    log_warn     "vbmeta image  : NOT FOUND — device may boot to fastboot after flash!"
    log_warn     "Fix: copy vbmeta_verification_disabled.img into $SCRIPT_ABS"
fi

# Paths to SKU specific files
PRODUCT="$sku/product-$sku_lower.img"
VBMETA_SYSTEM="$sku/vbmeta_system-$sku_lower.img"

MISSING_FILES=0
verify_file() {
    if [ ! -f "$1" ]; then
        log_err "Missing required file: $1"
        MISSING_FILES=1
    else
        log_success "Verified: $1"
    fi
}

verify_file "$INIT_BOOT"
verify_file "$PVMFW"
verify_file "$SYSTEM"
verify_file "$SYSTEM_EXT"
verify_file "$PRODUCT"
verify_file "$VBMETA_SYSTEM"

if [ $MISSING_FILES -ne 0 ]; then
    log_err "One or more required firmware files are missing for SKU $sku in the current directory."
    log_err "Please ensure you have downloaded and placed all parts correctly."
    exit 1
fi

# ------------------------------------------------------------------------------
# 4. AUTO CONFIGURATION
# ------------------------------------------------------------------------------
if [ "$wipe_data" = true ]; then
    log_warn "Flash mode: Clean Flash (--wipe passed — userdata WILL be erased)"
else
    log_info "Flash mode: Dirty Flash (user data preserved)"
fi

# ------------------------------------------------------------------------------
# 5. DEVICE CONNECTION AND STATE DETECTION
# ------------------------------------------------------------------------------
get_device_state() {
    # Returns: "none", "adb", "bootloader", "fastbootd"
    if adb devices 2>/dev/null | grep -q -E '\bdevice\b'; then
        echo "adb"
        return
    fi
    local userspace
    userspace=$(fastboot getvar is-userspace 2>&1)
    if echo "$userspace" | grep -q "is-userspace: yes"; then
        echo "fastbootd"
        return
    elif echo "$userspace" | grep -q "is-userspace:"; then
        echo "bootloader"
        return
    fi
    if fastboot devices 2>/dev/null | grep -q -E '\b(fastboot|device)\b'; then
        echo "bootloader"
        return
    fi
    echo "none"
}

wait_for_state() {
    local target=$1
    local msg=$2
    echo -n -e "${YELLOW}$msg${NC}"
    while true; do
        local state
        state=$(get_device_state)
        if [ "$state" = "$target" ]; then
            echo -e " ${GREEN}[CONNECTED]${NC}"
            break
        fi
        echo -n "."
        sleep 2
    done
}

# ------------------------------------------------------------------------------
# 6. FLASHING OPERATIONS
# ------------------------------------------------------------------------------
flash_partition() {
    local partition=$1
    local image=$2
    log_info "Flashing $partition using $image..."
    if ! fastboot flash "$partition" "$image"; then
        log_err "Failed to flash partition '$partition' with image '$image'."
        log_err "Please check your connection, bootloader unlock status, and try again."
        exit 1
    fi
    log_success "Successfully flashed $partition!"
}

# Flash a dynamic (logical) partition to slot_a.
# Handles two cases:
#   1. Partition exists   → fastbootd resizes it in-place
#   2. Partition missing  → recreate it from image size, then flash
# Slot_b is intentionally not flashed (inactive slot, and we need the space).
flash_dynamic_a() {
    local name="$1"   # e.g. "system"
    local image="$2"
    local partition="${name}_a"
    log_info "Flashing dynamic partition $partition using $image..."
    if fastboot flash "$partition" "$image" 2>/tmp/fastboot_err; then
        log_success "Successfully flashed $partition!"
        return 0
    fi
    # If partition was deleted in a previous failed run, recreate it
    if grep -q "No such file or directory\|does not exist" /tmp/fastboot_err 2>/dev/null; then
        local size
        size=$(stat -c%s "$image")
        log_warn "$partition not found in partition table. Recreating (size: $size bytes)..."
        fastboot create-logical-partition "$partition" "$size" || {
            log_err "Failed to create $partition"
            exit 1
        }
        fastboot flash "$partition" "$image" || {
            log_err "Failed to flash $partition after recreating it."
            exit 1
        }
        log_success "Successfully recreated and flashed $partition!"
    else
        cat /tmp/fastboot_err >&2
        log_err "Failed to flash $partition."
        exit 1
    fi
}

flash_vbmeta_partition() {
    local partition=$1
    local image=$2
    log_info "Flashing $partition with verification disabled using $image..."
    if ! fastboot flash --disable-verity --disable-verification "$partition" "$image"; then
        log_warn "Failed to flash with disabled verification. Attempting standard flash..."
        if ! fastboot flash "$partition" "$image"; then
            log_err "Failed to flash partition '$partition' with image '$image'."
            exit 1
        fi
    fi
    log_success "Successfully flashed $partition!"
}

# Check current state
state=$(get_device_state)
if [ "$state" = "none" ]; then
    log_warn "No connected device found."
    echo -e "Please ensure your device has ${YELLOW}USB Debugging enabled${NC} and is connected via USB,"
    echo -e "or manually reboot your device into ${YELLOW}Bootloader Mode${NC} (usually by holding Power + Volume Down)."
fi

# Wait for bootloader mode (or bootloader/fastbootd)
if [ "$state" = "adb" ]; then
    log_info "Device detected in ADB mode. Rebooting to Bootloader..."
    adb reboot bootloader
    wait_for_state "bootloader" "Waiting for Bootloader (fastboot) mode..."
elif [ "$state" = "fastbootd" ]; then
    log_info "Device detected in Fastbootd (userspace) mode. Rebooting to Bootloader..."
    fastboot reboot-bootloader
    wait_for_state "bootloader" "Waiting for Bootloader (fastboot) mode..."
elif [ "$state" = "bootloader" ]; then
    log_success "Device already connected in Bootloader mode."
else
    wait_for_state "bootloader" "Waiting for Bootloader (fastboot) mode (connect device now)..."
fi

# Safety check for Bootloader Lock status
log_info "Checking bootloader status..."
unlocked=$(fastboot getvar unlocked 2>&1)
if echo "$unlocked" | grep -q "unlocked: no"; then
    log_err "Your bootloader is LOCKED."
    log_err "You must unlock the bootloader before flashing custom images."
    log_err "Please refer to the README.pdf (p. 4) for unlock instructions."
    exit 1
else
    log_success "Bootloader is unlocked."
fi

# Flash Physical partitions in Bootloader Mode
echo -e "\n${CYAN}========================================= ${NC}"
echo -e "${CYAN}       FLASHING PHYSICAL PARTITIONS      ${NC}"
echo -e "${CYAN}========================================= ${NC}"

# Flash vbmeta with verification disabled — MUST be done before fastbootd.
# Without this, AVB chain: vbmeta → vbmeta_system will fail (hash mismatch)
# because vbmeta_system content changed, causing device to boot into fastboot.
if [ -n "$VBMETA_IMG" ] && [ -f "$VBMETA_IMG" ]; then
    log_info "Flashing vbmeta with verification disabled using: $(basename "$VBMETA_IMG")"
    fastboot flash --disable-verity --disable-verification vbmeta_a "$VBMETA_IMG"
    fastboot flash --disable-verity --disable-verification vbmeta_b "$VBMETA_IMG"
    log_success "vbmeta flashed with verification disabled on both slots."
else
    log_warn "WARNING: vbmeta_verification_disabled.img not found!"
    log_warn "Device may boot into fastboot due to AVB chain verification failure."
    log_warn "Provide it via: VBMETA_IMG=/path/to/vbmeta_verification_disabled.img ./flash.sh"
fi

if [ "$flash_both" = true ]; then
    flash_partition "init_boot_a" "$INIT_BOOT"
    flash_partition "init_boot_b" "$INIT_BOOT"
    flash_partition "pvmfw_a" "$PVMFW"
    flash_partition "pvmfw_b" "$PVMFW"
else
    flash_partition "init_boot" "$INIT_BOOT"
    flash_partition "pvmfw" "$PVMFW"
fi

# Reboot into Fastbootd (Userspace Fastboot) Mode
echo -e "\n${CYAN}========================================= ${NC}"
echo -e "${CYAN}        REBOOTING TO FASTBOOTD MODE      ${NC}"
echo -e "${CYAN}========================================= ${NC}"
log_info "Logical partitions (system, system_ext, product) must be flashed in userspace fastbootd mode."
log_info "Rebooting to fastbootd..."
fastboot reboot fastboot
wait_for_state "fastbootd" "Waiting for Fastbootd mode..."

# Flash Logical partitions — slot_a only.
# First delete slot_b to free super space so slot_a can be resized.
# slot_b is inactive (device boots slot_a) so losing it is safe.
echo -e "\n${CYAN}========================================= ${NC}"
echo -e "${CYAN}        FLASHING LOGICAL PARTITIONS      ${NC}"
echo -e "${CYAN}========================================= ${NC}"
log_info "Freeing super space by removing inactive slot_b logical partitions..."
for part in system_b system_ext_b product_b; do
    fastboot delete-logical-partition "$part" 2>/dev/null && log_info "Deleted $part" || true
done
flash_dynamic_a "system"      "$SYSTEM"
flash_dynamic_a "system_ext"  "$SYSTEM_EXT"
flash_dynamic_a "product"     "$PRODUCT"

# Return to hardware bootloader — flash vbmeta_system (physical partition)
echo -e "\n${CYAN}========================================= ${NC}"
echo -e "${CYAN}   FLASHING vbmeta_system + SET SLOT A   ${NC}"
echo -e "${CYAN}========================================= ${NC}"
log_info "Rebooting back to hardware bootloader..."
fastboot reboot-bootloader
wait_for_state "bootloader" "Waiting for hardware bootloader..."

flash_partition "vbmeta_system_a" "$VBMETA_SYSTEM"

log_info "Setting active slot to A..."
fastboot --set-active=a
log_success "Active slot set to A."

# Wipe userdata if requested
if [ "$wipe_data" = true ]; then
    echo -e "\n${CYAN}========================================= ${NC}"
    echo -e "${CYAN}           WIPING USERDATA               ${NC}"
    echo -e "${CYAN}========================================= ${NC}"
    log_warn "Erasing userdata partition..."
    fastboot erase userdata || { log_err "Failed to erase userdata."; exit 1; }
    fastboot erase metadata 2>/dev/null || true
    log_success "Userdata wiped."
fi

# Complete Flashing Process
echo -e "\n${CYAN}========================================= ${NC}"
echo -e "${CYAN}            FLASHING COMPLETE!            ${NC}"
echo -e "${CYAN}========================================= ${NC}"
log_success "Flashing finished successfully!"
log_info "Rebooting device to system..."
fastboot reboot

echo -e "\n${GREEN}===== Complete! Device is now rebooting to system. =====${NC}\n"
