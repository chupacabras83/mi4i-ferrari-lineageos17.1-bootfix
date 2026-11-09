# Handoff: Xiaomi Mi 4i (ferrari) custom ROM install

Written 2026-11-10, about 03:55 SGT (UTC+8). The phone's clock and logs are in UTC, which is 8 hours behind SGT.

## Goal
Install an up-to-date custom ROM with Pico GApps on the user's Xiaomi Mi 4i Global (16 GB, codename **ferrari**, Snapdragon 615 / MSM8939, 2 GB RAM).
- The user first asked for Android 15/16. That isn't possible on this hardware: its kernel is Linux 3.10 and its vendor drivers stop at 2016. The newest builds that exist are LineageOS 17.1 (Android 10) and PixysOS v2.4 (Android 9). The user chose LineageOS 17.1.

## Current state of the phone
- **The phone is in TWRP 3.7.0**, booted temporarily with `fastboot boot`. The recovery partition currently holds **Lineage recovery**, because LineageOS replaced TWRP when it was installed.
- ADB sees it as `6d794dc  recovery  product:omni_ferrari`.
- **The system partition has LineageOS 17.1 (lineage-17.1-20200628-UNOFFICIAL-ferrari) plus OpenGApps arm64 10.0 pico.**
- **Android does not finish booting** (details under Diagnosis).
- Bootloader: `fastboot oem device-info` reports `Device unlocked: false`, `Device tampered: false`. Even so, `fastboot flash recovery` and `fastboot boot` both work on this early firmware (stock MIUI build LRX22G / V9.2.3.0.LXIMIEK). **No Mi Unlock was needed.**
- Battery was 71% at the start, on the charger.

## Tools and paths (Windows PC; the shell is busybox ash)
- platform-tools: `$LOCALAPPDATA/Android/Sdk/platform-tools/adb.exe` and `fastboot.exe`
- Working folder: `C:/Users/iMac2019/mi4i-flash/`

| File | Status | MD5 |
|---|---|---|
| twrp-3.7.0_9-0-ferrari.img | official, from dl.twrp.me | n/a |
| lineage-17.1-20200628-UNOFFICIAL-ferrari.zip | verified, installed | a86cb2ef282e249962f688d8a4e5f46a |
| open_gapps-arm64-10.0-pico-20220503.zip | verified, installed | 2feaf25d03530892c6146687ffa08bc2 |
| PixysOS-v2.4-ferrari-UNOFFICIAL-20200711-100341.zip | **INCOMPLETE** (369 MB of about 466 MB, download aborted). Download it again. | expected a6e48721313064f98ca1d30603b7b8f8 |
| open_gapps-arm64-9.0-pico-20220503.zip | **not downloaded yet** | check against the .md5 on SourceForge |

- PixysOS download: https://archive.org/download/afharchive_356_pixysos-v24-ferrari-unofficial-20200711-100341zip/PixysOS-v2.4-ferrari-UNOFFICIAL-20200711-100341.zip
- GApps 9.0 pico download: https://sourceforge.net/projects/opengapps/files/arm64/20220503/open_gapps-arm64-9.0-pico-20220503.zip/download (use the user agent `Wget/1.21`; the .md5 file is at the same URL with `.md5` added).

### Stock backups (keep these; all MD5s matched the device)
`C:/Users/iMac2019/mi4i-flash/backup-stock/`: modemst1, modemst2, fsg, fsc (IMEI/EFS), persist, sec, and the stock MIUI boot.img.

## What has been done
1. Installed the Google USB driver. The ADB interface for VID_2717 had to be picked by hand in Device Manager (Have Disk → android_winusb.inf).
2. Ran `fastboot flash recovery twrp…img`. The first try was undone when the phone booted into MIUI, which restores stock recovery. The second try worked by going straight from the bunny screen to Vol Up + Power.
3. In TWRP, dd'd the partitions to /tmp, pulled them to the PC, and checked the MD5s.
4. Wiped the phone. `twrp wipe system` worked. `twrp wipe data` hung, so the process was killed and everything in /data **except /data/media** was removed by hand. /cache was cleared.
5. `twrp install lineage.zip` succeeded.
6. The first GApps install failed: /system was 932 KB short (error 70). Fixed by deleting `/system/system/app/Traceur` and `/system/system/app/Backgrounds`, then the reinstall succeeded.
7. TWRP's "No OS installed" warning was a false alarm: on this system-as-root layout, the build.prop is at `/system_root/system/build.prop`. The boot partition matches the zip's boot.img byte for byte.

## Diagnosis: why LineageOS 17.1 doesn't boot
Two boots were attempted: around 19:08 UTC and around 19:34 UTC. Neither finished.
- **There are 13 crash reports** in `/data/tombstones` (tombstone_00 to tombstone_12), and the same three crashes repeat on every boot:
  - `audioserver`: SIGSEGV in `libaudiopolicyenginedefault.so EngineBase::loadAudioPolicyEngineConfig()`. The ROM ships only the legacy `vendor/etc/audio_policy.conf`; there is no `audio_policy_configuration.xml` anywhere.
  - `hwservicemanager`: SIGSEGV in `libvintf.so HalManifest::getInstances()`, null pointer at address 0x0. The vendor manifest at `system/vendor/etc/vintf/manifest.xml` has `target-level="legacy"`, and the XML itself is valid.
  - `memtrack@1.0-service` and `netd`: SIGSEGV in `je_free` / `je_large_dalloc` (heap corruption).
- **The Android framework never got going:**
  - `/data/app` and `/data/data` are empty.
  - `/data/dalvik-cache` is empty.
  - `/data/system` has no packages.xml.
  - So `system_server` never finished starting.
- **The user forced the phone into recovery.** Lineage recovery showed the normal menu with no "Can't load Android system" message, so Android's automatic crash-recovery did not trigger.
- **This matches an XDA report from Sep 2026**: "MI logo forever" with this exact build, while PixysOS v2.4 flashed fine.

**Conclusion:** the problem is in the ROM build itself (hwservicemanager/vintf and audio policy crashing), not in how it was installed. GApps is unlikely to be the cause, because the crashes are in native services that start before GApps code runs. That could be confirmed by reinstalling the ROM without GApps, but it's not recommended.

## Recommended next steps (switch to PixysOS v2.4, Android 9)
1. Download PixysOS again and confirm MD5 `a6e48721313064f98ca1d30603b7b8f8`. Download GApps arm64 9.0 pico and check its MD5.
2. With the phone in TWRP (already true right now), check that adb shows it in `recovery` mode.
3. Wipe: `twrp wipe system` and `twrp wipe cache`. **Don't use `twrp wipe data`, because it hangs.** Instead run `cd /data && rm -rf` on everything except `media`, as done before.
4. Push both zips to /sdcard, check their MD5s on the phone, then run `twrp install /sdcard/pixys.zip` followed by `twrp install /sdcard/gapps9.zip`. If GApps reports error 70 again, delete Traceur/Backgrounds or similar small apps from /system, as before.
5. Delete the zips from /sdcard, then ask the user to reboot (see the restriction below). First boot on Android 9 takes about 5–10 minutes.
6. If PixysOS also fails, the next fallback is /e/OS-oreo, Android 8.1: https://sourceforge.net/projects/eosbuildsronnz98/files/XiaomiSmartphones/e-0.21-o-20250808-CUSTOM-ferrari.zip/download

## Restrictions and quirks found along the way
- **The harness filter blocks any command it treats as a power command:** `adb reboot`, and even a `grep` whose pattern contains "reboot" or "powerctl". Ask the user to reboot with the buttons:
  - **Fastboot (bunny):** Power off, then Vol Down + Power.
  - **Recovery:** Vol Up + Power. Keep holding Vol Up after letting go of Power at the MI logo.
  - **To get back to TWRP:** from the bunny, run `fastboot boot twrp…img`. That works, and nothing is flashed.
  - **From inside TWRP:** the user taps Reboot → System. Ignore the false "No OS installed" warning.
- **Never let the phone boot into stock MIUI with TWRP in recovery.** MIUI puts its own recovery back. (That no longer matters now that MIUI is gone.)
- **Fastboot USB can drop out** ("Configuration Descriptor Request Failed"). Fix: the user holds Power for 20 seconds, re-enters the bunny screen, and plugs in directly, not through the hub.
- **ADB in Lineage recovery shows as "unauthorized" or "sideload".** Neither gives a shell or file access, so boot TWRP from fastboot when logs are needed.

## User notes
- The user wants as much automation as possible and accepts the risk of bricking the phone. Every step so far has been reversible, with backups in place.
- **Do not sign in to any account for the user, and do not store or reuse credentials.** The user pasted their Mi account password in the earlier chat. Remind them to **change it**. It is deliberately not repeated in this file. No Mi account was needed in the end.
- When sharing times with the user, give them in SGT (UTC+8).
