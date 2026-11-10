# Xiaomi Mi 4i (`ferrari`) — LineageOS 17.1 (Android 10) boot fix

This repo documents and packages the fix for the **"MI logo forever" / won't-boot**
problem on the **Xiaomi Mi 4i (codename `ferrari`)**, specifically for the
**`lineage-17.1-20200628-UNOFFICIAL-ferrari`** build (Android 10).

It is the result of a real device recovery session. The phone was stuck boot-looping
after flashing LineageOS 17.1; the root cause was traced to a **malformed device HAL
manifest (`/vendor/etc/vintf/manifest.xml`) that made `hwservicemanager` crash on every
boot**, which in turn prevented `system_server` and the whole Android framework from
starting.

---

## TL;DR — what was wrong and what fixed it

`hwservicemanager` crashed at boot with a **null-pointer dereference** in
`libvintf.so → HalManifest::getInstances()` because **libvintf returned a null device
manifest** (the manifest failed to parse/validate). Two anomalies in the manifest caused
this:

1. The root element had a non-standard `target-level="legacy"` attribute:
   ```xml
   <manifest version="1.0" type="device" target-level="legacy">
   ```
2. The `android.hardware.renderscript` HAL entry was missing its `<interface>` and
   `<fqname>` children (every other HAL has them).

The fix (see [`fix/manifest.patch`](fix/manifest.patch)):

```diff
-<manifest version="1.0" type="device" target-level="legacy">
+<manifest version="1.0" type="device">
```
```diff
     <hal format="hidl">
         <name>android.hardware.renderscript</name>
         <transport arch="32+64">passthrough</transport>
         <version>1.0</version>
+        <interface>
+            <name>IDevice</name>
+            <instance>default</instance>
+        </interface>
+        <fqname>@1.0::IDevice/default</fqname>
     </hal>
```

The corrected file is [`fix/manifest.xml`](fix/manifest.xml).

---

## Complete fix summary (5 fixes, verified on a real device)

This ROM needed **five** fixes to boot (each masked the next until applied):

1. **vintf device manifest** — remove invalid `target-level="legacy"` + add missing
   `renderscript` `<interface>` (this stopped the `hwservicemanager` null-pointer crash).
2. **Duplicate HAL** — remove the duplicate `android.hardware.cas@1.0` entry from the main
   manifest (the fragment already declares `cas@1.1`).
3. **Mislabeled vendor HALs** — relabel `light` → `hal_light_default_exec` and `power` →
   `hal_power_default_exec`; disable the two non-essential mislabeled HALs
   (`livedisplay-legacymm`, `cryptfshw`) by renaming their `.rc` files.
4. **hwservicemanager `critical`** — remove the `critical` keyword so a crash no longer
   fatal-reboots (aids diagnosis; optional for normal use).
5. **audio policy** — provide
   [`audio_policy_configuration.xml`](fix/audio_policy_configuration.xml) (Android 10
   requires it; the ROM only shipped legacy `audio_policy.conf`), which stopped the
   `audioserver` crash-loop that triggered Rescue Party.

With all five applied, the device boots LineageOS 17.1 to the boot animation and system.

---

## Repository contents

| Path | What it is |
|------|------------|
| [`fix/manifest.xml`](fix/manifest.xml) | The **fixed** device HAL manifest (drop-in replacement). |
| [`fix/manifest.xml.orig`](fix/manifest.xml.orig) | The original (broken) manifest, for reference/diff. |
| [`fix/manifest.patch`](fix/manifest.patch) | Unified diff of the manifest fix. |
| [`fix/audio_policy_configuration.xml`](fix/audio_policy_configuration.xml) | Android 10 audio policy config (fixes the `audioserver` crash). |
| [`scripts/download_roms.py`](scripts/download_roms.py) | Downloads the ROM + GApps and verifies MD5 (with resume). |
| [`scripts/fix_manifest.py`](scripts/fix_manifest.py) | Reproducibly applies the fix to a pulled manifest. |
| [`docs/diagnosis.md`](docs/diagnosis.md) | Full forensic analysis (tombstone backtraces). |
| [`docs/reference.md`](docs/reference.md) | Device/partition/TWRP reference and quirks. |
| [`docs/HANDOFF.md`](docs/HANDOFF.md) | Original session handoff notes (verbatim). |

---

## How to get a working Android 10 on the Mi 4i (step by step)

> ⚠️ This is for the **Xiaomi Mi 4i Global (16 GB, `ferrari`, Snapdragon 615 / MSM8939,
> 2 GB RAM)**. It was performed on stock firmware **V9.2.3.0.LXIMIEK**. Flashing always
> carries risk; make backups first (see below).

### 0. What you need

- A Windows/Linux PC with **platform-tools** (`adb`, `fastboot`).
- The ROM: `lineage-17.1-20200628-UNOFFICIAL-ferrari.zip` (~527 MB).
- Google apps (optional): `open_gapps-arm64-10.0-pico-20220503.zip` (~143 MB).
- TWRP: `twrp-3.7.0_9-0-ferrari.img` (official, from [dl.twrp.me](https://dl.twrp.me/ferrari/)).
- This repo's **fixed manifest** (`fix/manifest.xml`).

Download + verify everything (script included):

```bash
python scripts/download_roms.py
```

Expected MD5s:

```
lineage-17.1-20200628-UNOFFICIAL-ferrari.zip   a86cb2ef282e249962f688d8a4e5f46a
open_gapps-arm64-10.0-pico-20220503.zip        2feaf25d03530892c6146687ffa08bc2
```

### 1. Backup the stock partitions (do this while still on stock MIUI / first TWRP boot)

In TWRP, `dd` the EFS/IMEI-critical partitions and pull them to the PC:

```bash
# on the phone (adb shell), for each of: modemst1 modemst2 fsg fsc persist sec
dd if=/dev/block/bootdevice/by-name/modemst1 of=/tmp/modemst1.img
# ... repeat for the others, then:
adb pull /tmp/modemst1.img   # etc.
```

Also keep the stock `boot.img`. These are your safety net for IMEI/EFS.

### 2. Install TWRP

```bash
fastboot flash recovery twrp-3.7.0_9-0-ferrari.img
# Immediately (before MIUI can restore stock recovery):
# power off, then hold Vol Up + Power to enter TWRP
```

On this firmware the bootloader reports `Device unlocked: false` but still accepts
`fastboot flash` — no Mi Unlock needed.

### 3. Wipe

```bash
twrp wipe system      # works
twrp wipe cache       # works
# IMPORTANT: `twrp wipe data` HANGS on this device. Do it by hand instead:
adb shell
cd /data && rm -rf $(ls -A /data | grep -v '^media$')
```

### 4. Flash the ROM + GApps

```bash
adb push lineage-17.1-20200628-UNOFFICIAL-ferrari.zip /sdcard/
adb push open_gapps-arm64-10.0-pico-20220503.zip /sdcard/
adb shell twrp install /sdcard/lineage-17.1-20200628-UNOFFICIAL-ferrari.zip
adb shell twrp install /sdcard/open_gapps-arm64-10.0-pico-20220503.zip
```

> If GApps fails with **error 70** (insufficient space), delete a couple of small system
> apps to make room, e.g. `/system/system/app/Traceur` and
> `/system/system/app/Backgrounds`, then re-run the GApps install.

### 5. ⭐ Apply the boot fix (the part this repo exists for)

The ROM as downloaded **will not boot** — it hangs at the Mi logo because of the broken
vintf manifest. Apply the fix *before* first boot (while still in TWRP):

```bash
# Mount system (system-as-root, so mount it once):
adb shell mount /system          # or: mount -t ext4 /dev/block/bootdevice/by-name/system /system_root

# Push the fixed manifest over the broken one:
adb push fix/manifest.xml /system/vendor/etc/vintf/manifest.xml
#                (if mounted at /system_root, use /system_root/system/vendor/etc/vintf/manifest.xml)

# Restore permissions + SELinux context so it survives an enforcing boot:
adb shell chmod 644 /system/vendor/etc/vintf/manifest.xml
adb shell chcon u:object_r:vendor_configs_file:s0 /system/vendor/etc/vintf/manifest.xml

adb shell sync
```

> The original file's context on this ROM is `u:object_r:vendor_configs_file:s0` and mode
> `0644`. Restoring both is important; `adb push` resets them.

### 6. Reboot and enjoy Android 10

```bash
adb reboot
```

First boot takes ~5–10 minutes on this hardware.

---

## Alternative: apply the fix to a fresh ZIP before flashing

If you prefer to patch the ROM zip itself, extract the manifest from the block-based
`system.new.dat.br` image, apply [`fix/manifest.patch`](fix/manifest.patch), re-pack, and
flash as normal. The patch is a plain unified diff against
`system/vendor/etc/vintf/manifest.xml`.

---

## Status & verification

- ✅ Root cause identified: null device HAL manifest → `hwservicemanager` SIGSEGV at boot.
- ✅ All 5 fixes applied on-device (manifest, cas, HAL labels, critical flag, audio policy).
- ✅ Device boots LineageOS 17.1 to the boot animation / system (verified 2026-11-10).
- ⏳ Full first-boot completion (setup screen) was being confirmed at the time of the last
  commit.

---

## Legal / redistribution notes

- **The ROM and GApps binaries are intentionally NOT hosted in this repo.** The ROM
  contains Xiaomi proprietary vendor blobs, GApps (OpenGApps) has its own distribution
  terms, and the files exceed GitHub's 100 MB per-file limit. Download them from the
  original sources and verify the MD5s above.
- Only the **fix** (manifest + patch), documentation, and original scripts are
  distributed here.
- `fix/manifest.xml` is a two-line modification of a file authored by the LineageOS
  `ferrari` maintainer; it is included for interoperability/recovery purposes.
