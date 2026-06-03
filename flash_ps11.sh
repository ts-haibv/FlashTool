#!/usr/bin/env bash
# ==============================================================================
# Flash Script for Sharp Aquos KIRA (PS11) - Android 16 / A4100
# ==============================================================================
# Firmware: BIN_SECBOOT_KIRA_16_A4100_2026
# Device:   PS11 (Sharp Aquos KIRA)
# SoC:      Qualcomm Snapdragon (A/B slot, UFS 4.1)
# Android:  16 (API 36) - userdebug
# Build:    A4100_2026
# ==============================================================================
#
# Usage:
#   ./flash_ps11.sh [OPTIONS]
#
# Options:
#   -v, --variant VARIANT   Device variant: kira|mn4|pdn4|pen4 (default: kira)
#   -s, --slot SLOT         Target slot: a|b (default: a)
#   -d, --disable-avb       Use vbmeta with verification disabled
#   -w, --wipe              Wipe userdata (factory reset)
#   -b, --bootloader-only   Flash bootloader/firmware partitions only
#   -p, --system-only       Flash dynamic (super) partitions only
#   -n, --dry-run           Show commands without executing
#   -y, --yes               Skip all confirmations
#   -S, --serial SERIAL     Specify device serial number
#   -h, --help              Show this help message
#
# ==============================================================================

set -uo pipefail

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "${FLASH_FIRMWARE_DIR:-$(dirname "${BASH_SOURCE[0]}")}" && pwd)"
KIRA_DIR="${SCRIPT_DIR}/Kira"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m' # No Color

# Defaults
VARIANT="kira"
SLOT="a"
DISABLE_AVB=false
WIPE_USERDATA=false
BOOTLOADER_ONLY=false
SYSTEM_ONLY=false
DRY_RUN=false
AUTO_YES=false
DEVICE_SERIAL=""
FASTBOOT="fastboot"
USE_SUDO=false
FLASH_TIMEOUT=120
SKIPPED=0

# ROM type detection
# Official: full firmware with boot.img, bootloader, etc.
# Jenkins: partial ROM (system/system_ext/product + pvmfw only)
ROM_TYPE=""  # "official" | "jenkins" | "" (auto-detect from boot.img)

# Counters
STEP=0
TOTAL_STEPS=0
ERRORS=0

# ──────────────────────────────────────────────────────────────────────────────
# Utility Functions
# ──────────────────────────────────────────────────────────────────────────────

log_header() {
    echo -e "\n${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${CYAN}  $1${NC}"
    echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

log_phase() {
    echo -e "\n${BOLD}${MAGENTA}◆ PHASE: $1${NC}"
    echo -e "${DIM}──────────────────────────────────────────────────────────────${NC}"
}

log_step() {
    STEP=$((STEP + 1))
    echo -e "${BOLD}${BLUE}  [${STEP}/${TOTAL_STEPS}]${NC} $1"
}

log_info() {
    echo -e "${CYAN}  ℹ ${NC}$1"
}

log_success() {
    echo -e "${GREEN}  ✓ ${NC}$1"
}

log_warn() {
    echo -e "${YELLOW}  ⚠ ${NC}$1"
}

log_error() {
    echo -e "${RED}  ✗ ${NC}$1"
    ERRORS=$((ERRORS + 1))
}

log_fatal() {
    echo -e "\n${RED}${BOLD}  ✗ FATAL: $1${NC}\n"
    exit 1
}

# ROM type auto-detection
detect_rom_type() {
    if [[ -n "$ROM_TYPE" ]]; then
        return 0
    fi
    if [[ -f "${SCRIPT_DIR}/boot.img" ]]; then
        ROM_TYPE="official"
    else
        ROM_TYPE="jenkins"
    fi
}

# Find bundled vbmeta_verification_disabled.img for Jenkins mode.
# Looks in: deb-installed assets dir → SCRIPT_DIR.
find_bundled_vbmeta() {
    local deb_dir="/usr/share/FlashTool/assets/ps11"
    for dir in "$deb_dir" "$SCRIPT_DIR"; do
        for name in vbmeta_verification_disabled.img vbmeta.img; do
            if [[ -f "$dir/$name" ]]; then
                echo "$dir/$name" && return 0
            fi
        done
    done
    echo ""
}

# Like flash_partition but runs in bootloader mode (no preflight/wait_for_device overhead).
# Used inside main_jenkins() bootloader phase.
fb_flash_slot() {
    local partition="$1"
    local image="$2"
    local image_path=""

    if [[ -f "${SCRIPT_DIR}/${image}" ]]; then
        image_path="${SCRIPT_DIR}/${image}"
    elif [[ -f "${KIRA_DIR}/${image}" ]]; then
        image_path="${KIRA_DIR}/${image}"
    else
        return 0
    fi

    local size_mb
    size_mb=$(du -m "${image_path}" 2>/dev/null | awk '{print $1}')

    log_step "Flashing ${BOLD}${partition}${NC} ← ${image} (${size_mb}MB)"
    if fb_exec flash "${partition}" "${image_path}"; then
        log_success "${partition} OK"
    else
        log_warn "Skipped ${partition}"
        SKIPPED=$((SKIPPED + 1))
    fi
}

# Auto-detect if sudo is needed for fastboot
detect_sudo() {
    if [[ "${DRY_RUN}" == true ]]; then
        return
    fi

    # Try fastboot without sudo first
    local devices
    devices=$("${FASTBOOT}" devices 2>/dev/null || true)
    if [[ -n "${devices}" ]]; then
        USE_SUDO=false
        return
    fi

    # Try with sudo
    devices=$(sudo "${FASTBOOT}" devices 2>/dev/null || true)
    if [[ -n "${devices}" ]]; then
        USE_SUDO=true
        log_warn "fastboot requires sudo on this system"
        return
    fi
}

# Pre-flight check: query device state and detect potential issues
preflight_check() {
    if [[ "${DRY_RUN}" == true ]]; then
        echo -e "${DIM}    [DRY-RUN] Preflight check skipped${NC}"
        return
    fi

    # Build fastboot command
    local -a fb_cmd=()
    if [[ "${USE_SUDO}" == true ]]; then
        fb_cmd+=(sudo)
    fi
    fb_cmd+=("${FASTBOOT}")
    if [[ -n "${DEVICE_SERIAL}" ]]; then
        fb_cmd+=(-s "${DEVICE_SERIAL}")
    fi

    # Query device variables
    local getvar_output
    getvar_output=$(timeout 10 "${fb_cmd[@]}" getvar all 2>&1 || true)

    if [[ -z "${getvar_output}" ]]; then
        log_warn "Could not query device variables"
        return
    fi

    # Display key device info
    local product serial slot_count is_unlocked secure_state
    product=$(echo "${getvar_output}" | grep -i "product:" | head -1 | awk '{print $2}' || true)
    serial=$(echo "${getvar_output}" | grep -i "serialno:" | head -1 | awk '{print $2}' || true)
    slot_count=$(echo "${getvar_output}" | grep -i "slot-count:" | head -1 | awk '{print $2}' || true)
    is_unlocked=$(echo "${getvar_output}" | grep -i "unlocked:" | head -1 | awk '{print $2}' || true)
    secure_state=$(echo "${getvar_output}" | grep -i "secure:" | head -1 | awk '{print $2}' || true)

    [[ -n "${product}" ]]    && log_info "Device product:  ${BOLD}${product}${NC}"
    [[ -n "${serial}" ]]     && log_info "Device serial:   ${BOLD}${serial}${NC}"
    [[ -n "${slot_count}" ]] && log_info "Slot count:      ${BOLD}${slot_count}${NC}"
    [[ -n "${secure_state}" ]] && log_info "Secure boot:     ${BOLD}${secure_state}${NC}"

    # Check bootloader unlock state
    if [[ -n "${is_unlocked}" ]]; then
        if [[ "${is_unlocked}" == "yes" || "${is_unlocked}" == "true" ]]; then
            log_success "Bootloader:      ${BOLD}UNLOCKED${NC}"
        else
            log_warn "Bootloader:      ${BOLD}LOCKED${NC}"
            echo ""
            log_warn "═══════════════════════════════════════════════════════════"
            log_warn "Bootloader is LOCKED — fastboot flash will likely FAIL"
            log_warn "or TIMEOUT on all partitions."
            log_warn ""
            log_warn "Options:"
            log_warn "  1. Unlock bootloader: fastboot flashing unlock"
            log_warn "  2. Use QFIL (EDL mode) instead of fastboot"
            log_warn "  3. Continue anyway (partitions will timeout/skip)"
            log_warn "═══════════════════════════════════════════════════════════"
            echo ""
            if [[ "${AUTO_YES}" != true ]]; then
                read -rp "    Continue with locked bootloader? [y/N] " answer
                case "${answer}" in
                    [yY][eE][sS]|[yY]) ;;
                    *) log_fatal "Aborted. Unlock bootloader first." ;;
                esac
            fi
        fi
    fi

    # Quick capability test: use getvar to check if device responds (avoids double-flashing vbmeta)
    log_info "Testing flash capability (getvar ping test)..."
    local -a test_cmd=()
    if [[ "${USE_SUDO}" == true ]]; then test_cmd+=(sudo); fi
    test_cmd+=("${FASTBOOT}")
    if [[ -n "${DEVICE_SERIAL}" ]]; then test_cmd+=(-s "${DEVICE_SERIAL}"); fi

    local ping_exit=0
    timeout 10 "${test_cmd[@]}" getvar current-slot 2>&1 || ping_exit=$?

    if [[ ${ping_exit} -eq 124 ]]; then
        log_error "Device TIMEOUT on getvar — does not respond to fastboot"
        log_error "This device likely requires QFIL/EDL mode for flashing."
        log_fatal "Cannot continue with fastboot. Use QFIL to flash this device."
    elif [[ ${ping_exit} -ne 0 ]]; then
        log_warn "getvar returned non-zero (exit ${ping_exit}) — continuing anyway"
    else
        log_success "Device responds to fastboot — flash capability confirmed"
    fi
}

# Execute fastboot command (or dry-run print)
# Uses timeout to prevent hanging on unresponsive partitions
fb_exec() {
    local custom_timeout="${FLASH_TIMEOUT}"

    # Build command array for proper argument handling
    local -a cmd_args=()
    if [[ "${USE_SUDO}" == true ]]; then
        cmd_args+=(sudo)
    fi
    cmd_args+=(timeout "${custom_timeout}")
    cmd_args+=("${FASTBOOT}")
    if [[ -n "${DEVICE_SERIAL}" ]]; then
        cmd_args+=(-s "${DEVICE_SERIAL}")
    fi
    cmd_args+=("$@")

    if [[ "${DRY_RUN}" == true ]]; then
        # Show without timeout prefix for readability
        local display_cmd="fastboot"
        if [[ "${USE_SUDO}" == true ]]; then display_cmd="sudo fastboot"; fi
        echo -e "${DIM}    [DRY-RUN] ${display_cmd} $*${NC}"
        return 0
    fi

    echo -e "${DIM}    > fastboot $*${NC}"
    local exit_code=0
    "${cmd_args[@]}" || exit_code=$?

    if [[ ${exit_code} -eq 124 ]]; then
        log_warn "TIMEOUT after ${custom_timeout}s — partition may not be accessible via fastboot"
        return 1
    elif [[ ${exit_code} -ne 0 ]]; then
        log_error "Command failed (exit ${exit_code})"
        return 1
    fi
    return 0
}

# Flash a single partition
# Usage: flash_partition <partition> <image> [optional]
#   If 3rd arg is "optional", failure is logged but not counted as error
flash_partition() {
    local partition="$1"
    local image="$2"
    local is_optional="${3:-}"
    local image_path=""

    # Resolve image path - check multiple locations
    if [[ -f "${SCRIPT_DIR}/${image}" ]]; then
        image_path="${SCRIPT_DIR}/${image}"
    elif [[ -f "${KIRA_DIR}/${image}" ]]; then
        image_path="${KIRA_DIR}/${image}"
    elif [[ -f "${VARIANT_DIR}/${image}" ]]; then
        image_path="${VARIANT_DIR}/${image}"
    else
        log_warn "Image not found, skipping: ${image}"
        return 0
    fi

    local size_mb
    size_mb=$(du -m "${image_path}" 2>/dev/null | awk '{print $1}')

    # Adjust timeout for large images (>100MB = 180s, >500MB = 600s, >1GB = 900s)
    local saved_timeout="${FLASH_TIMEOUT}"
    if [[ ${size_mb} -gt 1000 ]]; then
        FLASH_TIMEOUT=900
    elif [[ ${size_mb} -gt 500 ]]; then
        FLASH_TIMEOUT=600
    elif [[ ${size_mb} -gt 100 ]]; then
        FLASH_TIMEOUT=180
    fi

    log_step "Flashing ${BOLD}${partition}${NC} ← ${image} (${size_mb}MB)"
    local saved_errors=${ERRORS}
    if ! fb_exec flash "${partition}" "${image_path}"; then
        if [[ "${is_optional}" == "optional" ]]; then
            log_warn "Skipped ${partition} (optional, may require QFIL/EDL)"
            SKIPPED=$((SKIPPED + 1))
            ERRORS=${saved_errors}  # Restore error count for optional
        fi
    else
        log_success "${partition} OK"
    fi

    FLASH_TIMEOUT="${saved_timeout}"
}

# Wait for device in a specific mode
wait_for_device() {
    local mode="$1"
    local timeout="${2:-60}"

    if [[ "${DRY_RUN}" == true ]]; then
        echo -e "${DIM}    [DRY-RUN] Waiting for device in ${mode} mode...${NC}"
        return 0
    fi

    local -a fb_cmd=()
    if [[ "${USE_SUDO}" == true ]]; then
        fb_cmd+=(sudo)
    fi
    fb_cmd+=("${FASTBOOT}")
    if [[ -n "${DEVICE_SERIAL}" ]]; then
        fb_cmd+=(-s "${DEVICE_SERIAL}")
    fi

    log_info "Waiting for device in ${BOLD}${mode}${NC} mode (timeout: ${timeout}s)..."

    local count=0
    while [[ ${count} -lt ${timeout} ]]; do
        local devices
        devices=$("${fb_cmd[@]}" devices 2>/dev/null || true)
        if [[ -n "${devices}" ]]; then
            log_success "Device detected"
            return 0
        fi
        sleep 1
        count=$((count + 1))
    done

    log_fatal "Timeout waiting for device in ${mode} mode. Check USB connection."
}

# Confirm action
confirm() {
    if [[ "${AUTO_YES}" == true ]]; then
        return 0
    fi

    local msg="$1"
    echo -e "\n${YELLOW}${BOLD}  ? ${msg}${NC}"
    read -rp "    Proceed? [y/N] " answer
    case "${answer}" in
        [yY][eE][sS]|[yY]) return 0 ;;
        *) log_fatal "Aborted by user." ;;
    esac
}

# ──────────────────────────────────────────────────────────────────────────────
# Parse Arguments
# ──────────────────────────────────────────────────────────────────────────────

show_help() {
    cat << 'EOF'

  ╔═══════════════════════════════════════════════════════════════╗
  ║     Sharp Aquos KIRA (PS11) - Flash ROM Script               ║
  ║     Firmware: A4100_2026 / Android 16                        ║
  ╚═══════════════════════════════════════════════════════════════╝

  USAGE:
      ./flash_ps11.sh [OPTIONS]

  OPTIONS:
      -v, --variant VARIANT   Device variant: kira|mn4|pdn4|pen4
                              (default: kira)
      -s, --slot SLOT         Target slot: a|b (default: a)
      -d, --disable-avb       Use vbmeta with verification disabled
      -w, --wipe              Wipe userdata (factory reset)
      -b, --bootloader-only   Flash bootloader/firmware only
      -p, --system-only       Flash dynamic (super) partitions only
      -n, --dry-run           Show commands without executing
      -y, --yes               Skip all confirmations
      -S, --serial SERIAL     Specify device serial number
      --rom-type TYPE         Override auto-detect: official | jenkins
      -h, --help              Show this help message

  EXAMPLES:
      # Full flash for Kira variant (default)
      ./flash_ps11.sh

      # Flash MN4 variant with AVB disabled, auto-confirm
      ./flash_ps11.sh -v mn4 -d -y

      # Dry-run to preview commands
      ./flash_ps11.sh -n

      # Flash bootloader only
      ./flash_ps11.sh -b

      # Flash system partitions + wipe userdata
      ./flash_ps11.sh -p -w

  PREREQUISITES:
      - fastboot (Android SDK platform-tools)
      - Device in fastboot mode (Vol-Down + Power)
      - USB cable connected
      - Bootloader unlocked (if applicable)

  PARTITION LAYOUT (A/B slots):
      LUN1: xbl, xbl_config, multiimgqti, multiimgoem
      LUN4: uefi, aop, tz, hyp, modem, bluetooth, abl, dsp,
            keymaster, boot, devcfg, qupfw, vbmeta, dtbo,
            uefisecapp, imagefv, shrm, cpucp, featenabler,
            vendor_boot, recovery, xbl_ramdump, vbmeta_system,
            version, sdl, ssfd, init_boot, cpucp_dtb, pvmfw,
            soccp_debug, soccp_dcd
      LUN0: persist, metadata, tombstones, durable, super,
            userdata, storsec
      SUPER (dynamic): system, system_dlkm, system_ext, vendor,
                       vendor_dlkm, odm, product

EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -v|--variant)
            VARIANT="${2,,}"  # lowercase
            shift 2
            ;;
        -s|--slot)
            SLOT="${2,,}"
            shift 2
            ;;
        -d|--disable-avb)
            DISABLE_AVB=true
            shift
            ;;
        -w|--wipe)
            WIPE_USERDATA=true
            shift
            ;;
        -b|--bootloader-only)
            BOOTLOADER_ONLY=true
            shift
            ;;
        -p|--system-only)
            SYSTEM_ONLY=true
            shift
            ;;
        -n|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -y|--yes)
            AUTO_YES=true
            shift
            ;;
        -S|--serial)
            DEVICE_SERIAL="$2"
            shift 2
            ;;
        --rom-type)
            ROM_TYPE="${2,,}"
            case "${ROM_TYPE}" in
                official|jenkins) ;;
                *) log_fatal "--rom-type must be 'official' or 'jenkins'" ;;
            esac
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            log_fatal "Unknown option: $1 (use -h for help)"
            ;;
    esac
done

# ──────────────────────────────────────────────────────────────────────────────
# Validate Environment
# ──────────────────────────────────────────────────────────────────────────────

validate_environment() {
    log_header "ENVIRONMENT VALIDATION"

    # Check fastboot
    if ! command -v fastboot &>/dev/null; then
        log_fatal "fastboot not found. Install Android SDK platform-tools first."
    fi
    log_success "fastboot found: $(which fastboot)"

    # Check variant
    case "${VARIANT}" in
        kira|mn4|pdn4|pen4) ;;
        *) log_fatal "Invalid variant: ${VARIANT}. Use: kira|mn4|pdn4|pen4" ;;
    esac

    # Set variant directories (both root-level and Kira-level)
    # Root-level: ${SCRIPT_DIR}/MN4/product-mn4.img
    # Kira-level: ${SCRIPT_DIR}/Kira/MN4/sku.img
    local root_variant_dir=""
    case "${VARIANT}" in
        kira) VARIANT_DIR="${SCRIPT_DIR}/Kira"
              root_variant_dir="${SCRIPT_DIR}/Kira" ;;
        mn4)  VARIANT_DIR="${SCRIPT_DIR}/MN4"
              root_variant_dir="${SCRIPT_DIR}/MN4" ;;
        pdn4) VARIANT_DIR="${SCRIPT_DIR}/PDN4"
              root_variant_dir="${SCRIPT_DIR}/PDN4" ;;
        pen4) VARIANT_DIR="${SCRIPT_DIR}/PEN4"
              root_variant_dir="${SCRIPT_DIR}/PEN4" ;;
    esac

    # Validate slot
    case "${SLOT}" in
        a|b) ;;
        *) log_fatal "Invalid slot: ${SLOT}. Use: a|b" ;;
    esac

    # Check critical image files
    log_info "Checking firmware images..."

    if [[ "${ROM_TYPE}" == "jenkins" ]]; then
        # Jenkins ROM: only system, system_ext, pvmfw, and variant files needed
        local jenkins_images=(
            "${SCRIPT_DIR}/system.img"
            "${SCRIPT_DIR}/system_ext-kira.img"
            "${SCRIPT_DIR}/pvmfw.img"
        )
        local missing=0
        for img in "${jenkins_images[@]}"; do
            if [[ ! -f "${img}" ]]; then
                log_warn "Missing: ${img}"
            fi
        done

        local product_img="product-${VARIANT}.img"
        local vbmeta_sys_img="vbmeta_system-${VARIANT}.img"

        if [[ -f "${VARIANT_DIR}/${product_img}" ]]; then
            log_success "Variant product image: ${product_img}"
        elif [[ -f "${SCRIPT_DIR}/${product_img}" ]]; then
            log_success "Variant product image: ${SCRIPT_DIR}/${product_img}"
        else
            log_error "Missing: ${product_img}"
            missing=$((missing + 1))
        fi

        if [[ -f "${VARIANT_DIR}/${vbmeta_sys_img}" ]]; then
            log_success "Variant vbmeta_system image: ${vbmeta_sys_img}"
        elif [[ -f "${SCRIPT_DIR}/${vbmeta_sys_img}" ]]; then
            log_success "Variant vbmeta_system image: ${SCRIPT_DIR}/${vbmeta_sys_img}"
        else
            log_error "Missing: ${vbmeta_sys_img}"
            missing=$((missing + 1))
        fi

        if [[ ${missing} -gt 0 ]]; then
            log_fatal "${missing} critical image(s) missing. Ensure Jenkins firmware package is complete."
        fi
    else
        # Official ROM: all critical images required
        local critical_images=(
            "${KIRA_DIR}/abl.elf"
            "${KIRA_DIR}/tz.mbn"
            "${KIRA_DIR}/aop.mbn"
            "${KIRA_DIR}/xbl_s.melf"
            "${SCRIPT_DIR}/boot.img"
            "${SCRIPT_DIR}/system.img"
            "${SCRIPT_DIR}/vendor.img"
        )

        local missing=0
        for img in "${critical_images[@]}"; do
            if [[ ! -f "${img}" ]]; then
                log_error "Missing: ${img}"
                missing=$((missing + 1))
            fi
        done

        if [[ ${missing} -gt 0 ]]; then
            log_fatal "${missing} critical image(s) missing. Ensure firmware package is complete."
        fi

        # Variant-specific images (for official only)
        local product_img="product-${VARIANT}.img"
        local vbmeta_sys_img="vbmeta_system-${VARIANT}.img"

        if [[ -f "${KIRA_DIR}/${product_img}" ]]; then
            log_success "Variant product image: ${product_img}"
        elif [[ -f "${root_variant_dir}/${product_img}" ]]; then
            log_success "Variant product image: ${root_variant_dir}/${product_img}"
        else
            log_warn "Variant product image not found: ${product_img}"
        fi

        if [[ -f "${KIRA_DIR}/${vbmeta_sys_img}" ]]; then
            log_success "Variant vbmeta_system image: ${vbmeta_sys_img}"
        elif [[ -f "${root_variant_dir}/${vbmeta_sys_img}" ]]; then
            log_success "Variant vbmeta_system image: ${root_variant_dir}/${vbmeta_sys_img}"
        else
            log_warn "Variant vbmeta_system image not found: ${vbmeta_sys_img}"
        fi
    fi

    # Print confirmation summary
    echo ""
    echo -e "${BOLD}  ┌─────────────────────────────────────────────┐${NC}"
    echo -e "${BOLD}  │         FLASH CONFIGURATION SUMMARY         │${NC}"
    echo -e "${BOLD}  ├─────────────────────────────────────────────┤${NC}"
    echo -e "${BOLD}  │${NC}  Device:       ${CYAN}PS11 (Sharp Aquos KIRA)${NC}      ${BOLD}│${NC}"
    echo -e "${BOLD}  │${NC}  Variant:      ${CYAN}${VARIANT^^}${NC}$(printf '%*s' $((24 - ${#VARIANT})) '')${BOLD}│${NC}"
    echo -e "${BOLD}  │${NC}  Target Slot:  ${CYAN}${SLOT^^}${NC}                        ${BOLD}│${NC}"
    local fw_label="${ROM_TYPE} ($(basename "${SCRIPT_DIR}"))"
    echo -e "${BOLD}  │${NC}  Package:      ${CYAN}${fw_label}${NC}$(printf '%*s' $((26 - ${#fw_label})) '')${BOLD}│${NC}"
    echo -e "${BOLD}  │${NC}  Android:      ${CYAN}16 (API 36)${NC}                ${BOLD}│${NC}"
    echo -e "${BOLD}  │${NC}  AVB Disabled: ${CYAN}${DISABLE_AVB}${NC}$(printf '%*s' $((22 - ${#DISABLE_AVB})) '')${BOLD}│${NC}"
    echo -e "${BOLD}  │${NC}  Wipe Data:    ${CYAN}${WIPE_USERDATA}${NC}$(printf '%*s' $((22 - ${#WIPE_USERDATA})) '')${BOLD}│${NC}"
    echo -e "${BOLD}  │${NC}  Dry Run:      ${CYAN}${DRY_RUN}${NC}$(printf '%*s' $((22 - ${#DRY_RUN})) '')${BOLD}│${NC}"
    if [[ -n "${DEVICE_SERIAL}" ]]; then
    echo -e "${BOLD}  │${NC}  Serial:       ${CYAN}${DEVICE_SERIAL}${NC}$(printf '%*s' $((22 - ${#DEVICE_SERIAL})) '')${BOLD}│${NC}"
    fi
    echo -e "${BOLD}  └─────────────────────────────────────────────┘${NC}"
}

# ──────────────────────────────────────────────────────────────────────────────
# Phase 1: Flash Bootloader & Firmware Partitions (fastboot mode)
# ──────────────────────────────────────────────────────────────────────────────

flash_bootloader_firmware() {
    log_phase "1 — BOOTLOADER & FIRMWARE (fastboot mode)"

    detect_sudo
    wait_for_device "fastboot"

    # ── Pre-flight diagnostics ──
    log_info "Running pre-flight device diagnostics..."
    preflight_check

    # Calculate total steps for this phase
    STEP=0
    TOTAL_STEPS=39  # 32 partition flashes + apdp + soccp + storsec + spu_service

    # ── LUN4: Boot Images (flash these FIRST — most likely to succeed) ──
    log_info "Flashing boot images (LUN4)..."
    flash_partition "boot_${SLOT}"          "boot.img"
    flash_partition "init_boot_${SLOT}"     "init_boot.img"
    flash_partition "vendor_boot_${SLOT}"   "vendor_boot.img"
    flash_partition "dtbo_${SLOT}"          "dtbo.img"
    flash_partition "recovery_${SLOT}"      "recovery.img"

    # ── LUN4: AVB / Version ──
    log_info "Flashing AVB & version..."
    if [[ "${DISABLE_AVB}" == true ]]; then
        log_warn "Using vbmeta with verification DISABLED"
        flash_partition "vbmeta_${SLOT}" "vbmeta_verification_disabled.img"
    else
        flash_partition "vbmeta_${SLOT}" "vbmeta.img"
    fi
    flash_partition "version_${SLOT}"       "version.img"
    flash_partition "pvmfw_${SLOT}"         "pvmfw.img"

    # ── LUN4: ABL + Core Firmware ──
    log_info "Flashing ABL & core firmware (LUN4)..."
    flash_partition "abl_${SLOT}"           "abl.elf"
    flash_partition "aop_${SLOT}"           "aop.mbn"
    flash_partition "aop_config_${SLOT}"    "aop_devcfg.mbn"
    flash_partition "devcfg_${SLOT}"        "devcfg.mbn"
    flash_partition "qupfw_${SLOT}"         "qupv3fw.elf"
    flash_partition "keymaster_${SLOT}"     "keymint.mbn"
    flash_partition "featenabler_${SLOT}"   "featenabler.mbn"
    flash_partition "cpucp_${SLOT}"         "cpucp.elf"
    flash_partition "cpucp_dtb_${SLOT}"     "cpucp_dtbs.elf"
    flash_partition "imagefv_${SLOT}"       "imagefv.elf"
    flash_partition "shrm_${SLOT}"          "shrm.elf"
    flash_partition "sdl_${SLOT}"           "shprloader.img"
    flash_partition "ssfd_${SLOT}"          "ssfd.img"

    # ── LUN4: Modem & Radio ──
    log_info "Flashing modem & radio firmware..."
    flash_partition "modem_${SLOT}"         "NON-HLOS.bin"
    flash_partition "bluetooth_${SLOT}"     "BTFM.bin"
    flash_partition "dsp_${SLOT}"           "dspso.bin"

    # ── LUN4: Secure firmware (may be locked on secure boot devices) ──
    log_info "Flashing TrustZone & Hypervisor (may require QFIL)..."
    flash_partition "tz_${SLOT}"            "tz.mbn"            optional
    flash_partition "hyp_${SLOT}"           "hypvm.mbn"         optional
    flash_partition "uefi_${SLOT}"          "uefi.elf"          optional
    flash_partition "uefisecapp_${SLOT}"    "uefi_sec.mbn"      optional
    flash_partition "soccp_debug_${SLOT}"   "sdi.mbn"           optional
    flash_partition "soccp_dcd_${SLOT}"     "dcd.mbn"           optional
    flash_partition "xbl_ramdump_${SLOT}"   "XblRamdump.elf"    optional

    # ── LUN1: XBL Partitions (different physical LUN — often locked) ──
    log_info "Flashing XBL partitions (LUN1 — often requires QFIL/EDL)..."
    flash_partition "xbl_${SLOT}"           "xbl_s.melf"        optional
    flash_partition "xbl_config_${SLOT}"    "xbl_config.elf"    optional
    flash_partition "multiimgqti_${SLOT}"   "multi_image_qti.mbn" optional
    flash_partition "multiimgoem_${SLOT}"   "multi_image.mbn"   optional

    # ── Additional firmware images ──
    log_info "Flashing additional firmware (apdp, soccp, spu_service, storsec)..."
    # apdp: ADSP protected data (root-level)
    if [[ -f "${SCRIPT_DIR}/apdp.mbn" ]]; then
        flash_partition "apdp_${SLOT}"          "apdp.mbn"          optional
    fi
    # soccp: System-on-Chip Coprocessor firmware
    flash_partition "soccp_${SLOT}"         "soccp.mbn"         optional
    # spu_service: Secure Processing Unit
    flash_partition "spu_service_${SLOT}"   "spu_service.mbn"   optional
    # storsec: Storage security (LUN0, non-slot but needed for UFS init)
    flash_partition "storsec"               "storsec.mbn"       optional

    if [[ ${SKIPPED} -gt 0 ]]; then
        log_warn "${SKIPPED} partition(s) skipped (LUN1/secure — use QFIL for these)"
    fi

    log_success "Phase 1 complete: Bootloader & firmware flashed"
}

# ──────────────────────────────────────────────────────────────────────────────
# Phase 2: Flash Non-Slot Partitions (fastboot mode)
# ──────────────────────────────────────────────────────────────────────────────

flash_non_slot_partitions() {
    log_phase "2 — NON-SLOT PARTITIONS (fastboot mode)"

    STEP=0
    TOTAL_STEPS=10

    log_info "Flashing non-slot partitions (LUN0)..."
    flash_partition "persist"         "persist.img"
    flash_partition "metadata"        "metadata.img"
    flash_partition "tombstones"      "tombstones.img"
    flash_partition "tombstones_sys"  "tombstones_sys.img"
    flash_partition "durable"         "durable.img"
    flash_partition "durable_sys"     "durable_sys.img"

    # erase misc to clear any stale boot commands
    log_step "Erasing misc (clear boot commands)"
    fb_exec erase misc

    # ── SKU partition (fixed partition, must be flashed in fastboot mode) ──
    # IMPORTANT: sku is NOT a dynamic partition — fastbootd cannot see it!
    local sku_path="${KIRA_DIR}/${VARIANT^}/sku.img"
    if [[ "${VARIANT}" == "kira" ]]; then
        sku_path="${KIRA_DIR}/Kira/sku.img"
    fi
    if [[ -f "${sku_path}" ]]; then
        local saved_errors_sku=${ERRORS}
        log_step "Flashing ${BOLD}sku${NC} ← ${sku_path##*/} (fastboot mode)"
        if ! fb_exec flash sku "${sku_path}"; then
            log_warn "sku flash failed — skipping (optional)"
            ERRORS=${saved_errors_sku}
            SKIPPED=$((SKIPPED + 1))
        else
            log_success "sku OK"
        fi
    fi

    # ── Kitting partition (fixed partition, must be flashed in fastboot mode) ──
    # IMPORTANT: kitting is NOT a dynamic partition — fastbootd cannot see it!
    local kitting_path="${KIRA_DIR}/${VARIANT^}/kitting.img"
    case "${VARIANT}" in
        kira) kitting_path="${KIRA_DIR}/Kira/kitting.img" ;;
        mn4)  kitting_path="${KIRA_DIR}/MN4/kitting.img" ;;
        pdn4) kitting_path="${KIRA_DIR}/PDN4/kitting.img" ;;
        pen4) kitting_path="${KIRA_DIR}/PEN4/kitting.img" ;;
    esac
    if [[ -f "${kitting_path}" ]]; then
        local saved_errors_kit=${ERRORS}
        log_step "Flashing ${BOLD}kitting${NC} ← ${kitting_path##*/} (fastboot mode)"
        if ! fb_exec flash kitting "${kitting_path}"; then
            log_warn "kitting flash failed — skipping (optional)"
            ERRORS=${saved_errors_kit}
            SKIPPED=$((SKIPPED + 1))
        else
            log_success "kitting OK"
        fi
    else
        log_info "No kitting image for variant ${VARIANT^^} — skipping"
    fi

    log_success "Phase 2 complete: Non-slot partitions flashed"
}

# ──────────────────────────────────────────────────────────────────────────────
# Phase 3: Flash Dynamic Partitions (fastbootd mode)
# ──────────────────────────────────────────────────────────────────────────────

flash_dynamic_partitions() {
    log_phase "3 — DYNAMIC PARTITIONS (fastbootd mode)"

    # Reboot to fastbootd for dynamic partition support
    log_info "Rebooting to fastbootd mode..."
    fb_exec reboot fastboot
    # UFS 4.1 init + fastbootd userspace boot can take 15-30s — give it time
    sleep 15
    wait_for_device "fastbootd" 120

    STEP=0
    TOTAL_STEPS=10

    # Wipe super partition first
    log_step "Wiping super partition with empty layout"
    fb_exec wipe-super "${SCRIPT_DIR}/super_empty.img"

    # Determine variant-specific images
    local product_img="product-${VARIANT}.img"
    local vbmeta_sys_img="vbmeta_system-${VARIANT}.img"
    local system_ext_img="system_ext-${VARIANT}.img"
    local userdata_img="userdata-${VARIANT}.img"

    # Flash dynamic partitions to slot
    log_info "Flashing dynamic partitions..."

    flash_partition "system_${SLOT}"         "system.img"
    flash_partition "system_dlkm_${SLOT}"    "system_dlkm.img"

    # system_ext: try variant-specific first, then kira variant, then generic
    if [[ -f "${SCRIPT_DIR}/${system_ext_img}" ]]; then
        flash_partition "system_ext_${SLOT}" "${system_ext_img}"
    elif [[ -f "${SCRIPT_DIR}/system_ext-kira.img" ]]; then
        log_info "Using system_ext-kira.img (shared across variants)"
        flash_partition "system_ext_${SLOT}" "system_ext-kira.img"
    elif [[ -f "${SCRIPT_DIR}/system_ext.img" ]]; then
        flash_partition "system_ext_${SLOT}" "system_ext.img"
    else
        log_warn "No system_ext image found, skipping"
    fi

    flash_partition "vendor_${SLOT}"         "vendor.img"
    flash_partition "vendor_dlkm_${SLOT}"    "vendor_dlkm.img"
    flash_partition "odm_${SLOT}"            "odm.img"

    # Product partition: flash_partition searches SCRIPT_DIR → KIRA_DIR → VARIANT_DIR
    flash_partition "product_${SLOT}"        "${product_img}"

    # vbmeta_system: variant-specific
    flash_partition "vbmeta_system_${SLOT}"  "${vbmeta_sys_img}"

    # SKU and kitting are flashed in Phase 2 (fastboot mode) — NOT here.
    # fastbootd mode cannot see fixed partitions. Removed from Phase 3.

    log_success "Phase 3 complete: Dynamic partitions flashed"
}

# ──────────────────────────────────────────────────────────────────────────────
# Phase 4: Userdata & Finalize
# ──────────────────────────────────────────────────────────────────────────────

flash_userdata_and_finalize() {
    log_phase "4 — USERDATA & FINALIZE"

    STEP=0
    TOTAL_STEPS=4

    # Flash userdata
    if [[ "${WIPE_USERDATA}" == true ]]; then
        # IMPORTANT: Always flash userdata-kira.img to provide valid Ext4 headers.
        # fastboot erase zeroes the partition and causes Sharp init to panic.
        local userdata_img="userdata-${VARIANT}.img"
        if [[ -f "${KIRA_DIR}/${userdata_img}" ]]; then
            flash_partition "userdata" "${userdata_img}"
        elif [[ -f "${KIRA_DIR}/userdata-kira.img" ]]; then
            log_info "Variant generic userdata not found, using userdata-kira.img (Ext4 prebuilt)"
            flash_partition "userdata" "userdata-kira.img"
        else
            log_step "Formatting userdata (mke2fs)"
            fb_exec format:ext4 userdata
        fi
    else
        log_info "Skipping userdata (use -w to wipe)"
    fi

    # Set active slot
    log_step "Setting active slot to ${BOLD}${SLOT}${NC}"
    fb_exec set_active "${SLOT}"

    # Note: vbmeta already flashed in Phase 1 with correct image
    # (vbmeta_verification_disabled.img if -d flag was used)

    # Reboot
    log_step "Rebooting device..."
    fb_exec reboot

    log_success "Phase 4 complete: Finalized"
}

# ──────────────────────────────────────────────────────────────────────────────
# Jenkins ROM Flash Flow (partial ROM)
# Jenkins ROM includes: system.img, system_ext-kira.img, pvmfw.img,
# variant/{product-*.img, vbmeta_system-*.img}
# No bootloader, boot, init_boot, or radio firmware.
# ──────────────────────────────────────────────────────────────────────────────

main_jenkins() {
    log_header "PS11 JENKINS ROM — PARTIAL FLASH"

    local vbmeta
    vbmeta="$(find_bundled_vbmeta)"
    if [[ -z "$vbmeta" ]]; then
        log_warn "vbmeta_verification_disabled.img not found — skipping vbmeta flash"
        log_warn "Device may fail to boot due to AVB chain verification failure"
    fi

    # Determine images
    local product_img="product-${VARIANT}.img"
    local vbmeta_sys_img="vbmeta_system-${VARIANT}.img"
    local system_ext_img="system_ext-kira.img"

    # Show summary
    echo ""
    echo -e "${BOLD}  ┌─────────────────────────────────────────────┐${NC}"
    echo -e "${BOLD}  │     JENKINS FLASH CONFIGURATION SUMMARY     │${NC}"
    echo -e "${BOLD}  ├─────────────────────────────────────────────┤${NC}"
    echo -e "${BOLD}  │${NC}  Device:       ${CYAN}PS11 (Sharp Aquos KIRA)${NC}      ${BOLD}│${NC}"
    echo -e "${BOLD}  │${NC}  Variant:      ${CYAN}${VARIANT^^}${NC}$(printf '%*s' $((24 - ${#VARIANT})) '')${BOLD}│${NC}"
    echo -e "${BOLD}  │${NC}  Target Slot:  ${CYAN}${SLOT^^}${NC}                        ${BOLD}│${NC}"
    echo -e "${BOLD}  │${NC}  ROM Type:     ${YELLOW}Jenkins (partial)${NC}            ${BOLD}│${NC}"
    echo -e "${BOLD}  │${NC}  Wipe Data:    ${CYAN}${WIPE_USERDATA}${NC}$(printf '%*s' $((22 - ${#WIPE_USERDATA})) '')${BOLD}│${NC}"
    echo -e "${BOLD}  │${NC}  Dry Run:      ${CYAN}${DRY_RUN}${NC}$(printf '%*s' $((22 - ${#DRY_RUN})) '')${BOLD}│${NC}"
    echo -e "${BOLD}  └─────────────────────────────────────────────┘${NC}"

    if [[ "${AUTO_YES}" != true ]] && [[ "${DRY_RUN}" != true ]]; then
        echo ""
        log_warn "═══════════════════════════════════════════════════════════"
        log_warn "Jenkins ROM is a PARTIAL firmware package."
        log_warn "Only system + system_ext + product + vbmeta are included."
        log_warn "Bootloader and radio firmware are NOT updated."
        log_warn "═══════════════════════════════════════════════════════════"
        echo ""
        read -rp "    Proceed with Jenkins flash? [y/N] " answer
        case "${answer}" in
            [yY][eE][sS]|[yY]) ;;
            *) log_fatal "Aborted by user." ;;
        esac
    fi

    local start_time
    start_time=$(date +%s)

    # ── Phase 1: Bootloader mode — flash vbmeta + set slot ──
    detect_sudo
    wait_for_device "fastboot"

    log_phase "1 — BOOTSTRAP (bootloader mode)"
    STEP=0
    TOTAL_STEPS=3

    # Flash vbmeta with verity disabled to both slots
    if [[ -n "$vbmeta" ]]; then
        log_step "Flashing vbmeta with verification disabled (both slots)"
        local vb_errors=0
        if ! fb_exec flash --disable-verity --disable-verification vbmeta_a "$vbmeta"; then
            log_warn "vbmeta_a flash failed"
            vb_errors=$((vb_errors + 1))
        else
            log_success "vbmeta_a OK"
        fi
        if ! fb_exec flash --disable-verity --disable-verification vbmeta_b "$vbmeta"; then
            log_warn "vbmeta_b flash failed"
            vb_errors=$((vb_errors + 1))
        else
            log_success "vbmeta_b OK"
        fi
        if [[ ${vb_errors} -gt 0 ]]; then
            ERRORS=$((ERRORS + vb_errors))
        fi
    fi

    # Set active slot before fastbootd
    log_step "Setting active slot to ${BOLD}${SLOT}${NC}"
    fb_exec --set-active="${SLOT}"

    log_success "Phase 1 complete"

    # ── Phase 2: Fastbootd mode — flash dynamic partitions ──
    log_info "Rebooting to fastbootd mode..."
    fb_exec reboot fastboot
    sleep 15
    wait_for_device "fastbootd" 120

    log_phase "2 — DYNAMIC PARTITIONS (fastbootd mode)"
    STEP=0
    TOTAL_STEPS=6

    # Wipe super
    if [[ -f "${SCRIPT_DIR}/super_empty.img" ]]; then
        log_step "Wiping super partition"
        fb_exec wipe-super "${SCRIPT_DIR}/super_empty.img"
    fi

    # Delete slot_b logical partitions to free super space for slot_a resize
    if [[ "${DRY_RUN}" != true ]]; then
        for part in system_b system_ext_b product_b; do
            fb_exec delete-logical-partition "$part" 2>/dev/null || true
        done
    fi

    # Flash dynamic partitions
    flash_partition "system_${SLOT}"         "system.img"
    flash_partition "system_ext_${SLOT}"     "${system_ext_img}"
    flash_partition "product_${SLOT}"        "${product_img}"

    # ── Phase 3: Userdata ──
    if [[ "${WIPE_USERDATA}" == true ]]; then
        log_step "Erasing userdata"
        fb_exec erase userdata
        fb_exec erase metadata 2>/dev/null || true
    else
        log_info "Skipping userdata (use -w to wipe)"
    fi

    log_success "Phase 2 complete"

    # ── Phase 4: Reboot to bootloader — flash vbmeta_system + reboot ──
    log_info "Rebooting to bootloader for finalize..."
    fb_exec reboot bootloader
    sleep 5
    wait_for_device "fastboot" 60

    log_phase "3 — FINALIZE (bootloader mode)"
    STEP=0
    TOTAL_STEPS=3

    # Flash vbmeta_system
    flash_partition "vbmeta_system_${SLOT}"  "${vbmeta_sys_img}"

    # Set active slot
    log_step "Setting active slot to ${BOLD}${SLOT}${NC}"
    fb_exec --set-active="${SLOT}"

    # Reboot
    log_step "Rebooting device..."
    fb_exec reboot

    # Summary
    local end_time elapsed
    end_time=$(date +%s)
    elapsed=$((end_time - start_time))

    log_header "JENKINS FLASH COMPLETE"
    echo -e "  ${GREEN}${BOLD}Duration:${NC}  $((elapsed / 60))m $((elapsed % 60))s"
    echo -e "  ${GREEN}${BOLD}Errors:${NC}    ${ERRORS}"
    echo -e "  ${YELLOW}${BOLD}Skipped:${NC}   ${SKIPPED}"
    echo -e "  ${GREEN}${BOLD}Variant:${NC}   ${VARIANT^^}"
    echo -e "  ${GREEN}${BOLD}Slot:${NC}      ${SLOT^^}"
    echo ""
    if [[ ${ERRORS} -gt 0 ]]; then
        log_warn "${ERRORS} error(s) occurred. Device may not boot correctly."
    else
        log_success "All partitions flashed successfully!"
        log_info "Device is rebooting. First boot may take 5-10 minutes."
    fi
    echo ""
}


# ──────────────────────────────────────────────────────────────────────────────
# Main Execution
# ──────────────────────────────────────────────────────────────────────────────

main() {
    log_header "SHARP AQUOS KIRA (PS11) — ROM FLASH TOOL"

    # Detect ROM type first (before validation)
    detect_rom_type
    echo -e "${DIM}  ROM type:  ${ROM_TYPE}${NC}"
    echo -e "${DIM}  Firmware:  $(basename "${SCRIPT_DIR}")${NC}"
    echo -e "${DIM}  Script:    $(basename "$0") v1.0${NC}"
    echo -e "${DIM}  Date:      $(date '+%Y-%m-%d %H:%M:%S')${NC}"

    # Validate (uses ROM_TYPE to decide which images are required)
    validate_environment

    if [[ "${DRY_RUN}" == true ]]; then
        echo ""
        log_warn "DRY-RUN MODE: No commands will be executed"
    fi

    # Dispatch to Jenkins flow if detected
    if [[ "${ROM_TYPE}" == "jenkins" ]]; then
        main_jenkins
        return
    fi

    # ── Official flow below ──

    # Confirm before proceeding
    if [[ "${BOOTLOADER_ONLY}" == true ]]; then
        confirm "Flash BOOTLOADER & FIRMWARE only to slot ${SLOT^^}?"
    elif [[ "${SYSTEM_ONLY}" == true ]]; then
        confirm "Flash DYNAMIC PARTITIONS only to slot ${SLOT^^}?"
    else
        confirm "Perform FULL FLASH to slot ${SLOT^^}? This may take 10-15 minutes."
    fi

    local start_time
    start_time=$(date +%s)

    # Execute phases based on mode
    if [[ "${BOOTLOADER_ONLY}" == true ]]; then
        flash_bootloader_firmware
    elif [[ "${SYSTEM_ONLY}" == true ]]; then
        flash_dynamic_partitions
        flash_userdata_and_finalize
    else
        # Full flash sequence
        flash_bootloader_firmware
        flash_non_slot_partitions
        flash_dynamic_partitions
        flash_userdata_and_finalize
    fi

    # Summary
    local end_time elapsed
    end_time=$(date +%s)
    elapsed=$((end_time - start_time))

    log_header "FLASH COMPLETE"
    echo -e "  ${GREEN}${BOLD}Duration:${NC}  $((elapsed / 60))m $((elapsed % 60))s"
    echo -e "  ${GREEN}${BOLD}Errors:${NC}    ${ERRORS}"
    echo -e "  ${YELLOW}${BOLD}Skipped:${NC}   ${SKIPPED} (optional/secure partitions)"
    echo -e "  ${GREEN}${BOLD}Variant:${NC}   ${VARIANT^^}"
    echo -e "  ${GREEN}${BOLD}Slot:${NC}      ${SLOT^^}"

    if [[ ${ERRORS} -gt 0 ]]; then
        echo ""
        log_warn "${ERRORS} error(s) occurred. Device may not boot correctly."
        log_warn "Re-run with -n (dry-run) to review the flash sequence."
    else
        echo ""
        log_success "All partitions flashed successfully!"
        log_info "Device is rebooting. First boot may take 5-10 minutes."
    fi

    echo ""
}

main "$@"
