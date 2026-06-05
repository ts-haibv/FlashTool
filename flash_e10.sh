#!/usr/bin/env bash
set -Eeuo pipefail

# ==============================================================================
#  E10 Device Flashing Script (Lyle)
# ==============================================================================
#  Supports SKU variants: MC5, PDC5, PEC5, PHC5, PKC5, TAC5, TDC5, TEC5
#
#  Auto-detects ROM type:
#    Official — full ROM with boot.img, vendor.img, bootloader firmware
#    Jenkins  — partial ROM (system/system_ext/product + init_boot/pvmfw only)
#
#  Bootloader images (xbl, tz, abl, etc.) always come from MC5/.
#  Modem/BT files come from the selected SKU folder if present, else MC5/.
# ==============================================================================

SCRIPT_DIR="$(cd "${FLASH_FIRMWARE_DIR:-$(dirname "${BASH_SOURCE[0]}")}" && pwd)"
SCRIPT_ABS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL="MC5"
SERIAL=""
DRY_RUN=0
WIPE=0
DISABLE_VERITY=1
REBOOT_AFTER=1
RETRY_COUNT=3
YES=0
TARGET_SLOT="a"
FASTBOOT_CHUNK_SIZE="32M"

# ROM type detection
# Official: full firmware with boot.img, bootloader, etc.
# Jenkins: partial ROM (system/system_ext/product + pvmfw only)
ROM_TYPE=""  # "official" | "jenkins" | "" (auto-detect from boot.img)

VALID_MODELS=(MC5 PDC5 PEC5 PHC5 PKC5 TAC5 TDC5 TEC5)
BASE_MODEL="MC5"   # Always the source of bootloader binaries

usage() {
  cat <<'EOF'
Usage:
  ./flash_e10.sh [options]

  Auto-detects ROM type:
    Official  — full ROM package with boot.img, vendor.img, bootloader firmware
    Jenkins   — partial ROM (system/system_ext/product + init_boot/pvmfw only)

Options:
  -m, --model MODEL       SKU to flash: MC5 PDC5 PEC5 PHC5 PKC5 TAC5 TDC5 TEC5
                          Default: MC5
  -s, --serial SERIAL     adb/fastboot serial (multi-device setups)
      --wipe              Erase userdata (userdata-*.img if present, else erase)
      --disable-verity    Flash vbmeta_verification_disabled.img (default)
      --enable-verity     Flash vbmeta.img instead
      --rom-type TYPE     Override auto-detect: official | jenkins
      --dry-run           Print commands without executing
      --no-reboot         Leave device in fastboot after flashing
      --target-slot SLOT  Slot to flash and activate: a or b. Default: a
      --chunk-size SIZE   fastboot -S chunk size. Default: 32M
  -y, --yes               Skip FLASH confirmation prompt
  -h, --help              Show this help

Device must be unlocked and connected via adb or fastboot/bootloader.
This script uses fastboot/fastbootd only — not EDL/QFIL.
EOF
}

# ── Utility helpers ────────────────────────────────────────────────────────────

die()  { echo "ERROR: $*" >&2; exit 1; }
log()  { echo; echo "==> $*"; }

adb_cmd() {
  [[ -n "$SERIAL" ]] && adb -s "$SERIAL" "$@" || adb "$@"
}

fastboot_cmd() {
  [[ -n "$SERIAL" ]] && fastboot -s "$SERIAL" -S "$FASTBOOT_CHUNK_SIZE" "$@" \
                     || fastboot -S "$FASTBOOT_CHUNK_SIZE" "$@"
}

# Flash without -S re-chunking — required for Qualcomm sparse blobs
fastboot_cmd_raw() {
  [[ -n "$SERIAL" ]] && fastboot -s "$SERIAL" "$@" || fastboot "$@"
}

run_adb() {
  echo "+ adb ${SERIAL:+-s $SERIAL }$*"
  (( DRY_RUN )) && return 0
  retry adb_cmd "$@"
}

run_fastboot() {
  echo "+ fastboot ${SERIAL:+-s $SERIAL }-S $FASTBOOT_CHUNK_SIZE $*"
  (( DRY_RUN )) && return 0
  retry fastboot_cmd "$@"
}

run_fastboot_raw() {
  echo "+ fastboot ${SERIAL:+-s $SERIAL }$*"
  (( DRY_RUN )) && return 0
  retry fastboot_cmd_raw "$@"
}

retry() {
  local attempt=1
  until "$@"; do
    (( attempt >= RETRY_COUNT )) && return 1
    attempt=$((attempt + 1))
    echo "Retry $attempt/$RETRY_COUNT: $*" >&2
    sleep 2
  done
}

require_tool() { command -v "$1" >/dev/null 2>&1 || die "Missing tool: $1"; }
require_file() { [[ -f "$1" ]] || die "Missing file: $1"; }

# Flash only if file exists (silently skip if absent)
flash_if_exists() {
  local partition="$1" image="$2"
  [[ -f "$image" ]] || return 0
  run_fastboot flash "$partition" "$image"
}

flash_slot_if_exists() {
  local partition="$1" image="$2"
  [[ -f "$image" ]] || return 0
  run_fastboot flash "${partition}_${TARGET_SLOT}" "$image"
}

# Like flash_slot_if_exists but uses raw fastboot (no -S) for sparse Qualcomm blobs
flash_slot_raw() {
  local partition="$1" image="$2"
  [[ -f "$image" ]] || return 0
  run_fastboot_raw flash "${partition}_${TARGET_SLOT}" "$image"
}

# Return first path that exists among the candidates, or empty string
first_existing() {
  for f in "$@"; do
    [[ -f "$f" ]] && echo "$f" && return 0
  done
  echo ""
}

# ── Device state helpers ───────────────────────────────────────────────────────

device_in_fastboot() {
  (( DRY_RUN )) && return 0
  if [[ -n "$SERIAL" ]]; then
    fastboot devices | awk '{print $1}' | grep -Fxq "$SERIAL"
  else
    [[ -n "$(fastboot devices | awk 'NF {print $1; exit}')" ]]
  fi
}

device_in_adb() {
  (( DRY_RUN )) && return 0
  if [[ -n "$SERIAL" ]]; then
    adb devices | awk '$2 == "device" {print $1}' | grep -Fxq "$SERIAL"
  else
    [[ -n "$(adb devices | awk '$2 == "device" {print $1; exit}')" ]]
  fi
}

device_in_fastbootd() {
  (( DRY_RUN )) && return 0
  fastboot_cmd getvar is-userspace 2>&1 | grep -q "is-userspace: yes"
}

wait_for_fastboot_device() {
  (( DRY_RUN )) && return 0
  local i
  for i in $(seq 1 45); do
    device_in_fastboot && return 0
    sleep 2
  done
  return 1
}

wait_for_fastbootd() {
  (( DRY_RUN )) && return 0
  local i
  for i in $(seq 1 30); do
    device_in_fastbootd && return 0
    sleep 2
  done
  return 1
}

wait_for_adb_device() {
  (( DRY_RUN )) && return 0
  local i
  for i in $(seq 1 45); do
    device_in_adb && return 0
    sleep 2
  done
  return 1
}

enter_bootloader() {
  device_in_fastboot && { log "Device already in fastboot"; return 0; }
  device_in_adb || die "No adb/fastboot device found"
  log "Reboot to bootloader"
  run_adb reboot bootloader
  wait_for_fastboot_device || die "Device did not return to bootloader."
}

enter_fastbootd() {
  device_in_fastbootd && { log "Device already in fastbootd"; return 0; }

  log "Reboot to fastbootd"
  echo "+ fastboot ${SERIAL:+-s $SERIAL }-S $FASTBOOT_CHUNK_SIZE reboot fastboot"
  if (( ! DRY_RUN )); then
    fastboot_cmd reboot fastboot || true
  fi
  if wait_for_fastbootd; then return 0; fi

  log "Fallback: boot recovery then request fastbootd via adb"
  echo "+ fastboot ${SERIAL:+-s $SERIAL }-S $FASTBOOT_CHUNK_SIZE reboot recovery"
  if (( ! DRY_RUN )); then fastboot_cmd reboot recovery || true; fi
  wait_for_adb_device || die "Could not boot recovery for fastbootd fallback."
  run_adb reboot fastboot
  wait_for_fastbootd || die "Could not enter fastbootd."
}

# ── ROM type detection ───────────────────────────────────────────────────────

detect_rom_type() {
  [[ -n "$ROM_TYPE" ]] && return 0
  if [[ -f "$SCRIPT_DIR/boot.img" ]]; then
    ROM_TYPE="official"
  else
    ROM_TYPE="jenkins"
  fi
}

# Find bundled vbmeta_verification_disabled.img for Jenkins mode.
find_bundled_vbmeta() {
  local deb_dir="/usr/share/FlashTool/assets/e10"
  for dir in "$deb_dir" "$SCRIPT_ABS"; do
    for name in vbmeta_verification_disabled.img vbmeta.img; do
      [[ -f "$dir/$name" ]] && echo "$dir/$name" && return 0
    done
  done
  echo ""
}

# ── Official ROM flash flow ────────────────────────────────────────────────────

flash_official_bootstrap() {
  local vbmeta="$1"
  log "Flash boot images needed for fastbootd"
  flash_slot_if_exists boot        "$SCRIPT_DIR/boot.img"
  flash_slot_if_exists init_boot   "$SCRIPT_DIR/init_boot.img"
  flash_slot_if_exists vendor_boot "$SCRIPT_DIR/vendor_boot.img"
  flash_slot_if_exists recovery    "$SCRIPT_DIR/recovery.img"
  flash_slot_if_exists dtbo        "$SCRIPT_DIR/dtbo.img"
  flash_slot_if_exists vbmeta      "$vbmeta"
}

flash_official_bootloader() {
  local model_dir="$1" model_lower="$2" vbmeta="$3"
  local base_dir="$SCRIPT_DIR/$BASE_MODEL"

  log "Flash bootloader and boot-slot partitions"
  flash_slot_if_exists xbl          "$base_dir/xbl_s.melf"
  flash_slot_if_exists xbl_config   "$base_dir/xbl_config.elf"
  flash_slot_if_exists multiimgqti  "$base_dir/multi_image_qti.mbn"
  flash_slot_if_exists multiimgoem  "$base_dir/multi_image.mbn"
  flash_slot_if_exists uefi         "$base_dir/uefi.elf"
  flash_slot_if_exists aop          "$base_dir/aop.mbn"
  flash_slot_if_exists aop_config   "$base_dir/aop_devcfg.mbn"
  flash_slot_if_exists tz           "$base_dir/tz.mbn"
  flash_slot_if_exists hyp          "$base_dir/hypvm.mbn"
  flash_slot_raw       modem        "$base_dir/NON-HLOS.bin"
  flash_slot_raw       bluetooth    "$base_dir/BTFM.bin"
  flash_slot_raw       dsp          "$base_dir/dspso.bin"
  flash_slot_if_exists abl          "$base_dir/abl.elf"
  flash_slot_if_exists keymaster    "$base_dir/keymint.mbn"
  flash_slot_if_exists devcfg       "$base_dir/devcfg.mbn"
  flash_slot_if_exists qupfw        "$base_dir/qupv3fw.elf"
  flash_slot_if_exists uefisecapp   "$base_dir/uefi_sec.mbn"
  flash_slot_if_exists imagefv      "$base_dir/imagefv.elf"
  flash_slot_if_exists shrm         "$base_dir/shrm.elf"
  flash_slot_if_exists cpucp        "$base_dir/cpucp.elf"
  flash_slot_if_exists cpucp_dtb    "$base_dir/cpucp_dtbs.elf"
  flash_slot_if_exists featenabler  "$base_dir/featenabler.mbn"
  flash_slot_if_exists xbl_ramdump  "$base_dir/XblRamdump.elf"
  flash_slot_if_exists pvmfw        "$SCRIPT_DIR/pvmfw.img"
  flash_slot_if_exists boot         "$SCRIPT_DIR/boot.img"
  flash_slot_if_exists init_boot    "$SCRIPT_DIR/init_boot.img"
  flash_slot_if_exists vendor_boot  "$SCRIPT_DIR/vendor_boot.img"
  flash_slot_if_exists recovery     "$SCRIPT_DIR/recovery.img"
  flash_slot_if_exists dtbo         "$SCRIPT_DIR/dtbo.img"
  flash_slot_if_exists vbmeta       "$vbmeta"
  flash_slot_if_exists vbmeta_system "$model_dir/vbmeta_system-$model_lower.img"
  flash_slot_if_exists version      "$SCRIPT_DIR/version.img"
  flash_slot_if_exists sdl          "$base_dir/shprloader.img"
  flash_slot_if_exists ssfd         "$base_dir/ssfd.img"

  log "Flash physical non-slot partitions"
  flash_if_exists persist    "$SCRIPT_DIR/persist.img"
  flash_if_exists metadata   "$SCRIPT_DIR/metadata.img"
  flash_if_exists durable    "$SCRIPT_DIR/durable.img"
  flash_if_exists tombstones "$SCRIPT_DIR/tombstones.img"
  flash_if_exists kitting    "$base_dir/kitting.img"
}

main_official() {
  local model_dir="$SCRIPT_DIR/$MODEL"
  local model_lower="${MODEL,,}"

  [[ -d "$model_dir" ]] || die "Missing model folder: $model_dir"
  require_file "$SCRIPT_DIR/boot.img"
  require_file "$SCRIPT_DIR/dtbo.img"
  require_file "$SCRIPT_DIR/init_boot.img"
  require_file "$SCRIPT_DIR/vendor_boot.img"
  require_file "$SCRIPT_DIR/system.img"
  require_file "$SCRIPT_DIR/system_ext-lyle.img"
  require_file "$SCRIPT_DIR/vendor.img"
  require_file "$model_dir/product-$model_lower.img"
  require_file "$model_dir/vbmeta_system-$model_lower.img"

  local vbmeta="$SCRIPT_DIR/vbmeta.img"
  (( DISABLE_VERITY )) && vbmeta="$SCRIPT_DIR/vbmeta_verification_disabled.img"
  require_file "$vbmeta"

  confirm_flash
  enter_bootloader
  flash_official_bootstrap "$vbmeta"

  log "Set active slot $TARGET_SLOT before fastbootd"
  run_fastboot --set-active="$TARGET_SLOT"

  enter_fastbootd

  log "Prepare super partition"
  [[ -f "$SCRIPT_DIR/super_empty.img" ]] && run_fastboot wipe-super "$SCRIPT_DIR/super_empty.img"

  log "Flash dynamic partitions"
  flash_if_exists system      "$SCRIPT_DIR/system.img"
  flash_if_exists system_ext  "$SCRIPT_DIR/system_ext-lyle.img"
  flash_if_exists vendor      "$SCRIPT_DIR/vendor.img"
  flash_if_exists product     "$model_dir/product-$model_lower.img"
  flash_if_exists odm         "$SCRIPT_DIR/odm.img"
  flash_if_exists system_dlkm "$SCRIPT_DIR/system_dlkm.img"
  flash_if_exists vendor_dlkm "$SCRIPT_DIR/vendor_dlkm.img"
  flash_if_exists odm_dlkm    "$SCRIPT_DIR/odm_dlkm.img"

  if (( WIPE )); then
    log "Wipe userdata"
    local userdata
    userdata="$(first_existing \
      "$model_dir/userdata-$model_lower.img" \
      "$base_dir/userdata-mc5.img")"
    if [[ -n "$userdata" ]]; then
      run_fastboot flash userdata "$userdata"
    else
      run_fastboot erase userdata
      run_fastboot erase metadata 2>/dev/null || true
    fi
  else
    log "Skipping userdata — pass --wipe to erase"
  fi

  log "Reboot to bootloader for final firmware partitions"
  run_fastboot reboot bootloader
  wait_for_fastboot_device || die "Device did not return to bootloader."
  flash_official_bootloader "$model_dir" "$model_lower" "$vbmeta"

  log "Set active slot $TARGET_SLOT"
  run_fastboot --set-active="$TARGET_SLOT"

  if (( REBOOT_AFTER )); then
    log "Reboot device"
    run_fastboot reboot
  else
    log "Done. Device left in fastboot"
  fi
}

# ── Jenkins ROM flash flow ─────────────────────────────────────────────────────

main_jenkins() {
  local model_dir="$SCRIPT_DIR/$MODEL"
  local model_lower="${MODEL,,}"

  local vbmeta; vbmeta="$(find_bundled_vbmeta)"
  if [[ -z "$vbmeta" ]]; then
    echo "WARNING: vbmeta_verification_disabled.img not found — skipping vbmeta flash" >&2
    echo "WARNING: device may fail to boot due to AVB chain verification failure" >&2
  fi

  [[ -d "$model_dir" ]] || die "Missing model folder: $model_dir"
  require_file "$SCRIPT_DIR/init_boot.img"
  require_file "$SCRIPT_DIR/pvmfw.img"
  require_file "$SCRIPT_DIR/system.img"
  require_file "$SCRIPT_DIR/system_ext-lyle.img"
  require_file "$model_dir/product-$model_lower.img"
  require_file "$model_dir/vbmeta_system-$model_lower.img"

  confirm_flash
  enter_bootloader

  log "Flash boot images needed for fastbootd"
  if [[ -n "$vbmeta" ]]; then
    run_fastboot flash --disable-verity --disable-verification "vbmeta_a" "$vbmeta"
    run_fastboot flash --disable-verity --disable-verification "vbmeta_b" "$vbmeta"
  fi
  flash_slot_if_exists init_boot "$SCRIPT_DIR/init_boot.img"
  flash_slot_if_exists pvmfw     "$SCRIPT_DIR/pvmfw.img"

  log "Set active slot $TARGET_SLOT before fastbootd"
  run_fastboot --set-active="$TARGET_SLOT"

  enter_fastbootd

  log "Prepare super partition"
  log "Flash dynamic partitions"
  if (( ! DRY_RUN )); then
    for part in system_b system_ext_b product_b; do
      fastboot_cmd delete-logical-partition "$part" 2>/dev/null || true
    done
  fi
  flash_if_exists system     "$SCRIPT_DIR/system.img"
  flash_if_exists system_ext "$SCRIPT_DIR/system_ext-lyle.img"
  flash_if_exists vendor     "$SCRIPT_DIR/vendor.img"
  flash_if_exists product    "$model_dir/product-$model_lower.img"

  if (( WIPE )); then
    log "Wipe userdata"
    run_fastboot erase userdata
    (( DRY_RUN )) || fastboot_cmd erase metadata 2>/dev/null || true
  else
    log "Skipping userdata — pass --wipe to erase"
  fi

  log "Reboot to bootloader for firmware partitions"
  run_fastboot reboot bootloader
  wait_for_fastboot_device || die "Device did not return to bootloader."

  log "Flash bootloader and boot-slot partitions"
  flash_slot_if_exists vbmeta_system "$model_dir/vbmeta_system-$model_lower.img"

  log "Set active slot $TARGET_SLOT"
  run_fastboot --set-active="$TARGET_SLOT"

  if (( REBOOT_AFTER )); then
    log "Reboot device"
    run_fastboot reboot
  else
    log "Done. Device left in fastboot"
  fi
}

# ── Argument parsing ───────────────────────────────────────────────────────────

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -m|--model)
        MODEL="${2:-}"; [[ -n "$MODEL" ]] || die "--model requires a value"; shift 2 ;;
      -s|--serial)
        SERIAL="${2:-}"; [[ -n "$SERIAL" ]] || die "--serial requires a value"; shift 2 ;;
      --wipe)            WIPE=1;         shift ;;
      --disable-verity)  DISABLE_VERITY=1; shift ;;
      --enable-verity)   DISABLE_VERITY=0; shift ;;
      --rom-type)
        ROM_TYPE="${2:-}"
        [[ "$ROM_TYPE" == "official" || "$ROM_TYPE" == "jenkins" ]] \
          || die "--rom-type must be 'official' or 'jenkins'"
        shift 2 ;;
      --dry-run)         DRY_RUN=1;     shift ;;
      --no-reboot)       REBOOT_AFTER=0; shift ;;
      --target-slot)
        TARGET_SLOT="${2:-}"
        [[ "$TARGET_SLOT" == "a" || "$TARGET_SLOT" == "b" ]] || die "--target-slot must be a or b"
        shift 2 ;;
      --chunk-size)
        FASTBOOT_CHUNK_SIZE="${2:-}"
        [[ "$FASTBOOT_CHUNK_SIZE" =~ ^[0-9]+[KMG]?$ ]] || die "--chunk-size must be e.g. 32M"
        shift 2 ;;
      -y|--yes)  YES=1;  shift ;;
      -h|--help) usage; exit 0 ;;
      *) die "Unknown option: $1" ;;
    esac
  done
}

confirm_flash() {
  (( DRY_RUN )) && return 0
  (( YES ))     && return 0
  echo "Model     : $MODEL"
  echo "Slot      : $TARGET_SLOT"
  echo "ROM type  : $ROM_TYPE"
  echo "Package   : $SCRIPT_DIR"
  (( WIPE )) && echo "WIPE      : enabled — user data will be ERASED"
  read -r -p "Type FLASH to continue: " answer
  [[ "$answer" == "FLASH" ]] || die "Cancelled"
}

# ── Main ───────────────────────────────────────────────────────────────────────

main() {
  parse_args "$@"

  MODEL="${MODEL^^}"

  # Validate model
  local valid=0
  for m in "${VALID_MODELS[@]}"; do [[ "$MODEL" == "$m" ]] && valid=1 && break; done
  (( valid )) || die "Unknown model: $MODEL. Valid: ${VALID_MODELS[*]}"

  local model_dir="$SCRIPT_DIR/$MODEL"
  local base_dir="$SCRIPT_DIR/$BASE_MODEL"

  require_tool adb
  require_tool fastboot

  # Base bootloader dir must always exist
  [[ -d "$base_dir" ]] || die "Missing base bootloader folder: $base_dir"

  # SKU dir must exist (may be empty for variants sharing MC5 bootloader)
  [[ -d "$model_dir" ]] || die "Missing model folder: $model_dir"

  detect_rom_type
  echo "==> ROM type: $ROM_TYPE (SCRIPT_DIR=$SCRIPT_DIR)"

  if [[ "$ROM_TYPE" == "jenkins" ]]; then
    main_jenkins
  else
    main_official
  fi
}

main "$@"
