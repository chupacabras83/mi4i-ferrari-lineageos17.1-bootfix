# Xiaomi Mi 4i (`ferrari`) — device reference

## Hardware

- SoC: Qualcomm Snapdragon 615 (MSM8939), 8× Cortex-A53
- RAM: 2 GB
- Storage: 16 GB eMMC
- Codename: `ferrari`
- Shipped with Android 5.0.2 (MIUI), kernel **Linux 3.10**
- **No Project Treble** (pre-Treble, so no GSI/Android 15-16 — impossible on this HW)

## Partition map (by-name → block)

| by-name | block | size |
|---------|-------|------|
| `system` | `mmcblk0p34` | ~1.63 GB (ext4) |
| `cache` | `mmcblk0p35` | ~375 MB |
| `userdata` | `mmcblk0p36` | ~12.2 GB |
| `boot` | — | 32 MB image |
| `recovery` | — | — |

EFS/IMEI-critical partitions (back these up): `modemst1`, `modemst2`, `fsg`, `fsc`,
`persist`, `sec`.

## Recovery / boot quirks (observed)

- Bootloader `fastboot oem device-info` reports `Device unlocked: false`, yet
  `fastboot flash recovery` and `fastboot boot` still work on stock
  V9.2.3.0.LXIMIEK. **No Mi Unlock was needed.**
- **Never let stock MIUI boot with TWRP in the recovery partition** — MIUI restores its own
  recovery.
- `twrp wipe data` **hangs** on this device. Wipe `/data` manually (keep `/data/media`).
- TWRP's "No OS installed" warning is a **false alarm** on this system-as-root layout: the
  build.prop is at `/system_root/system/build.prop`, which TWRP doesn't look at.
- **Fastboot USB can drop out** ("Configuration Descriptor Request Failed"). Fix: hold
  Power ~20 s, re-enter the bunny (fastboot) screen, and plug the cable in **directly**
  (not through a hub).
- Lineage recovery's ADB shows as `unauthorized`/`sideload` (no shell) — boot TWRP from
  fastboot (`fastboot boot twrp.img`) when you need a shell or logs.

## Button combos

- **Fastboot (bunny):** power off, then **Vol Down + Power**.
- **Recovery:** **Vol Up + Power**; keep holding Vol Up after releasing Power at the Mi logo.

## Build notes

- Latest builds that exist for `ferrari`: **LineageOS 17.1** (Android 10, the one fixed
  here) and **PixysOS v2.4** (Android 9). Newer (11+) does not exist and is not feasible
  (kernel 3.10, no Treble, 2016 vendor blobs, 2 GB RAM).
- The LineageOS 17.1 zip is block-based (`system.new.dat.br` + `system.transfer.list`), so
  files aren't individually browsable in the zip.
