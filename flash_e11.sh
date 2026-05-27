#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "${FLASH_FIRMWARE_DIR:-$(dirname "${BASH_SOURCE[0]}")}" && pwd)"
MODEL="MC6"
SERIAL=""
DRY_RUN=0
WIPE=0
DISABLE_VERITY=1
REBOOT_AFTER=1
RETRY_COUNT=3
YES=0
TARGET_SLOT="a"
FASTBOOT_CHUNK_SIZE="32M"

usage() {
  cat <<'EOF'
Usage:
  ./flash_e11.sh [options]

Options:
  -m, --model MODEL       Model folder to use: MC6, PDC6, PEC6. Default: MC6
  -s, --serial SERIAL     adb/fastboot serial when more than one device is connected
      --wipe              Flash/erase userdata. This deletes user data
      --disable-verity    Flash vbmeta_verification_disabled.img. Default for this package
      --enable-verity     Flash vbmeta.img instead
      --dry-run           Print commands without executing
      --no-reboot         Do not reboot after flashing
      --target-slot SLOT  Slot to flash and activate: a or b. Default: a
      --chunk-size SIZE   fastboot -S chunk size for transfers. Default: 32M
  -y, --yes               Skip the FLASH confirmation prompt
  -h, --help              Show this help

Device must be unlocked and connected in adb mode or fastboot/bootloader mode.
This script uses fastboot/fastbootd. It does not perform Qualcomm EDL/QFIL provisioning.
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

log() {
  echo
  echo "==> $*"
}

adb_cmd() {
  if [[ -n "$SERIAL" ]]; then
    adb -s "$SERIAL" "$@"
  else
    adb "$@"
  fi
}

fastboot_cmd() {
  if [[ -n "$SERIAL" ]]; then
    fastboot -s "$SERIAL" -S "$FASTBOOT_CHUNK_SIZE" "$@"
  else
    fastboot -S "$FASTBOOT_CHUNK_SIZE" "$@"
  fi
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

retry() {
  local attempt=1
  until "$@"; do
    if (( attempt >= RETRY_COUNT )); then
      return 1
    fi
    attempt=$((attempt + 1))
    echo "Retry $attempt/$RETRY_COUNT: $*" >&2
    sleep 2
  done
}

require_tool() {
  command -v "$1" >/dev/null 2>&1 || die "Missing tool: $1"
}

require_file() {
  [[ -f "$1" ]] || die "Missing file: $1"
}

flash_if_exists() {
  local partition="$1"
  local image="$2"
  [[ -f "$image" ]] || return 0
  run_fastboot flash "$partition" "$image"
}

flash_slot_if_exists() {
  local partition="$1"
  local image="$2"
  [[ -f "$image" ]] || return 0
  run_fastboot flash "${partition}_${TARGET_SLOT}" "$image"
}

flash_fastbootd_bootstrap_partitions() {
  local vbmeta="$1"
  local bootstrap_vbmeta="$SCRIPT_DIR/vbmeta_verification_disabled.img"

  log "Flash boot images needed for fastbootd"
  flash_slot_if_exists boot "$SCRIPT_DIR/boot.img"
  flash_slot_if_exists init_boot "$SCRIPT_DIR/init_boot.img"
  flash_slot_if_exists vendor_boot "$SCRIPT_DIR/vendor_boot.img"
  flash_slot_if_exists recovery "$SCRIPT_DIR/recovery.img"
  flash_slot_if_exists dtbo "$SCRIPT_DIR/dtbo.img"

  if [[ -f "$bootstrap_vbmeta" ]]; then
    flash_slot_if_exists vbmeta "$bootstrap_vbmeta"
  else
    flash_slot_if_exists vbmeta "$vbmeta"
  fi
}

flash_bootloader_and_physical_partitions() {
  local model_dir="$1"
  local model_lower="$2"
  local vbmeta="$3"

  log "Flash bootloader and boot-slot partitions"
  flash_slot_if_exists xbl "$model_dir/xbl_s.melf"
  flash_slot_if_exists xbl_config "$model_dir/xbl_config.elf"
  flash_slot_if_exists multiimgqti "$model_dir/multi_image_qti.mbn"
  flash_slot_if_exists multiimgoem "$model_dir/multi_image.mbn"
  flash_slot_if_exists uefi "$model_dir/uefi.elf"
  flash_slot_if_exists aop "$model_dir/aop.mbn"
  flash_slot_if_exists aop_config "$model_dir/aop_devcfg.mbn"
  flash_slot_if_exists tz "$model_dir/tz.mbn"
  flash_slot_if_exists hyp "$model_dir/hypvm.mbn"
  flash_slot_if_exists modem "$model_dir/NON-HLOS.bin"
  flash_slot_if_exists bluetooth "$model_dir/BTFM.bin"
  flash_slot_if_exists abl "$model_dir/abl.elf"
  flash_slot_if_exists dsp "$model_dir/dspso.bin"
  flash_slot_if_exists keymaster "$model_dir/keymint.mbn"
  flash_slot_if_exists devcfg "$model_dir/devcfg.mbn"
  flash_slot_if_exists qupfw "$model_dir/qupv3fw.elf"
  flash_slot_if_exists uefisecapp "$model_dir/uefi_sec.mbn"
  flash_slot_if_exists imagefv "$model_dir/imagefv.elf"
  flash_slot_if_exists shrm "$model_dir/shrm.elf"
  flash_slot_if_exists cpucp "$model_dir/cpucp.elf"
  flash_slot_if_exists featenabler "$model_dir/featenabler.mbn"
  flash_slot_if_exists xbl_ramdump "$model_dir/XblRamdump.elf"
  flash_slot_if_exists cpucp_dtb "$model_dir/cpucp_dtbs.elf"
  flash_slot_if_exists pvmfw "$SCRIPT_DIR/pvmfw.img"
  flash_slot_if_exists boot "$SCRIPT_DIR/boot.img"
  flash_slot_if_exists init_boot "$SCRIPT_DIR/init_boot.img"
  flash_slot_if_exists vendor_boot "$SCRIPT_DIR/vendor_boot.img"
  flash_slot_if_exists recovery "$SCRIPT_DIR/recovery.img"
  flash_slot_if_exists dtbo "$SCRIPT_DIR/dtbo.img"
  flash_slot_if_exists vbmeta "$vbmeta"
  flash_slot_if_exists vbmeta_system "$model_dir/vbmeta_system-$model_lower.img"
  flash_slot_if_exists version "$SCRIPT_DIR/version.img"
  flash_slot_if_exists sdl "$model_dir/shprloader.img"
  flash_slot_if_exists ssfd "$model_dir/ssfd.img"

  log "Flash physical non-slot partitions"
  flash_if_exists persist "$SCRIPT_DIR/persist.img"
  flash_if_exists metadata "$SCRIPT_DIR/metadata.img"
  flash_if_exists durable "$SCRIPT_DIR/durable.img"
  flash_if_exists tombstones "$SCRIPT_DIR/tombstones.img"
  flash_if_exists kitting "$model_dir/kitting.img"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -m|--model)
        MODEL="${2:-}"
        [[ -n "$MODEL" ]] || die "--model requires a value"
        shift 2
        ;;
      -s|--serial)
        SERIAL="${2:-}"
        [[ -n "$SERIAL" ]] || die "--serial requires a value"
        shift 2
        ;;
      --wipe)
        WIPE=1
        shift
        ;;
      --disable-verity)
        DISABLE_VERITY=1
        shift
        ;;
      --enable-verity)
        DISABLE_VERITY=0
        shift
        ;;
      --dry-run)
        DRY_RUN=1
        shift
        ;;
      --no-reboot)
        REBOOT_AFTER=0
        shift
        ;;
      --target-slot)
        TARGET_SLOT="${2:-}"
        [[ "$TARGET_SLOT" == "a" || "$TARGET_SLOT" == "b" ]] || die "--target-slot must be a or b"
        shift 2
        ;;
      --chunk-size)
        FASTBOOT_CHUNK_SIZE="${2:-}"
        [[ "$FASTBOOT_CHUNK_SIZE" =~ ^[0-9]+[KMG]?$ ]] || die "--chunk-size must look like 32M, 64M, or 1048576"
        shift 2
        ;;
      -y|--yes)
        YES=1
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "Unknown option: $1"
        ;;
    esac
  done
}

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

wait_for_fastboot_device() {
  (( DRY_RUN )) && return 0
  local i
  for i in $(seq 1 45); do
    if device_in_fastboot; then
      return 0
    fi
    sleep 2
  done
  return 1
}

device_in_fastbootd() {
  (( DRY_RUN )) && return 0
  fastboot_cmd getvar is-userspace 2>&1 | grep -q "is-userspace: yes"
}

wait_for_fastbootd() {
  (( DRY_RUN )) && return 0
  local i
  for i in $(seq 1 30); do
    if device_in_fastbootd; then
      return 0
    fi
    sleep 2
  done
  return 1
}

wait_for_adb_device() {
  (( DRY_RUN )) && return 0
  local i
  for i in $(seq 1 45); do
    if device_in_adb; then
      return 0
    fi
    sleep 2
  done
  return 1
}

enter_fastbootd() {
  if device_in_fastbootd; then
    log "Device already in fastbootd"
    return 0
  fi

  log "Reboot to fastbootd"
  echo "+ fastboot ${SERIAL:+-s $SERIAL }-S $FASTBOOT_CHUNK_SIZE reboot fastboot"
  if (( ! DRY_RUN )); then
    fastboot_cmd reboot fastboot || true
  fi
  if wait_for_fastbootd; then
    return 0
  fi

  log "Fallback: boot recovery, then request fastbootd from adb"
  echo "+ fastboot ${SERIAL:+-s $SERIAL }-S $FASTBOOT_CHUNK_SIZE reboot recovery"
  if (( ! DRY_RUN )); then
    fastboot_cmd reboot recovery || true
  fi
  wait_for_adb_device || die "Could not boot recovery/adb for fastbootd fallback."
  run_adb reboot fastboot
  wait_for_fastbootd || die "Could not enter fastbootd. Boot/recovery/vendor_boot may be unbootable."
}

enter_bootloader() {
  if device_in_fastboot; then
    log "Device already in fastboot"
    return 0
  fi

  device_in_adb || die "No adb/fastboot device found"
  log "Reboot to bootloader"
  run_adb reboot bootloader
  wait_for_fastboot_device || die "Device did not return to bootloader fastboot."
}

confirm_destructive_flash() {
  (( DRY_RUN )) && return 0
  (( YES )) && return 0
  echo "Model: $MODEL"
  echo "Target slot: $TARGET_SLOT"
  echo "Package: $SCRIPT_DIR"
  echo "This will flash firmware images to the connected device."
  if (( WIPE )); then
    echo "WIPE is enabled. User data will be erased/flashed."
  fi
  read -r -p "Type FLASH to continue: " answer
  [[ "$answer" == "FLASH" ]] || die "Cancelled"
}

main() {
  parse_args "$@"

  MODEL="${MODEL^^}"
  local model_dir="$SCRIPT_DIR/$MODEL"
  local model_lower="${MODEL,,}"

  require_tool adb
  require_tool fastboot
  [[ -d "$model_dir" ]] || die "Missing model folder: $model_dir"

  require_file "$SCRIPT_DIR/boot.img"
  require_file "$SCRIPT_DIR/dtbo.img"
  require_file "$SCRIPT_DIR/init_boot.img"
  require_file "$SCRIPT_DIR/vendor_boot.img"
  require_file "$SCRIPT_DIR/system.img"
  require_file "$SCRIPT_DIR/system_ext-suletta.img"
  require_file "$SCRIPT_DIR/vendor.img"
  require_file "$SCRIPT_DIR/odm.img"
  require_file "$model_dir/product-$model_lower.img"
  require_file "$model_dir/vbmeta_system-$model_lower.img"

  local vbmeta="$SCRIPT_DIR/vbmeta.img"
  if (( DISABLE_VERITY )); then
    vbmeta="$SCRIPT_DIR/vbmeta_verification_disabled.img"
  fi
  require_file "$vbmeta"

  confirm_destructive_flash
  enter_bootloader

  flash_fastbootd_bootstrap_partitions "$vbmeta"
  log "Set active slot $TARGET_SLOT before fastbootd"
  run_fastboot --set-active="$TARGET_SLOT"

  enter_fastbootd

  log "Prepare super partition"
  if [[ -f "$SCRIPT_DIR/super_empty.img" ]]; then
    run_fastboot wipe-super "$SCRIPT_DIR/super_empty.img"
  fi

  log "Flash dynamic partitions"
  flash_if_exists system "$SCRIPT_DIR/system.img"
  flash_if_exists system_ext "$SCRIPT_DIR/system_ext-suletta.img"
  flash_if_exists vendor "$SCRIPT_DIR/vendor.img"
  flash_if_exists product "$model_dir/product-$model_lower.img"
  flash_if_exists odm "$SCRIPT_DIR/odm.img"
  flash_if_exists system_dlkm "$SCRIPT_DIR/system_dlkm.img"
  flash_if_exists vendor_dlkm "$SCRIPT_DIR/vendor_dlkm.img"
  flash_if_exists odm_dlkm "$SCRIPT_DIR/odm_dlkm.img"

  if (( WIPE )); then
    log "Wipe userdata"
    if [[ -f "$model_dir/userdata-$model_lower.img" ]]; then
      run_fastboot flash userdata "$model_dir/userdata-$model_lower.img"
    else
      run_fastboot erase userdata
    fi
  else
    log "Skip userdata. Add --wipe to erase/flash userdata"
  fi

  log "Reboot to bootloader for final firmware partitions"
  run_fastboot reboot bootloader
  wait_for_fastboot_device || die "Device did not return to bootloader fastboot."
  flash_bootloader_and_physical_partitions "$model_dir" "$model_lower" "$vbmeta"

  log "Set active slot $TARGET_SLOT"
  run_fastboot --set-active="$TARGET_SLOT"

  if (( REBOOT_AFTER )); then
    log "Reboot device"
    run_fastboot reboot
  else
    log "Done. Device left in fastbootd"
  fi
}

main "$@"
