# Xiaomi Mi 4i (`ferrari`) — LineageOS 17.1 boot fix · Final write-up

This file closes out the Mi 4i documentation. It is the **companion** to
[`README.md`](README.md), which already covers the root-cause story, the flashing
walkthrough, and the repo layout. What follows is the *detail* the README points at but
does not yet spell out: per-fix **before/after** fragments, the **audio-policy tagName
rule**, the **complete verified file list with download links**, **credits**, and the
**current status / next steps**.

- Repo: `github.com/chupacabras83/mi4i-ferrari-lineageos17.1-bootfix`
- Device: **Xiaomi Mi 4i Global (16 GB)** — codename `ferrari`, Snapdragon 615 / MSM8939,
  2 GB RAM, kernel Linux 3.10, **no Project Treble**. Stock firmware V9.2.3.0.LXIMIEK.
- ROM under repair: **LineageOS 17.1 (Android 10)**
  `lineage-17.1-20200628-UNOFFICIAL-ferrari`.

---

## 1. What's new here vs. what's already in the README

| Topic | Where it lives |
|---|---|
| Root cause (`hwservicemanager` null-pointer in `libvintf`) + tombstones | ✅ [`README.md`](README.md) + [`docs/diagnosis.md`](docs/diagnosis.md) |
| High-level "five fixes" list | ✅ [`README.md`](README.md) § "Complete fix summary" |
| Step-by-step flash / backup / apply-fix guide | ✅ [`README.md`](README.md) |
| Partition map + button combos + TWRP quirks | ✅ [`docs/reference.md`](docs/reference.md) |
| **Per-fix before/after XML/`.rc` fragments** | 🆕 **this file** (§2) — README only shows the fix-1 diff |
| **Audio-policy rule: `attachedDevices`/`defaultOutputDevice` use `tagName`, not the enum string** | 🆕 **this file** (§2.6) — not explained in README |
| **Complete file list + verified download links + MD5s** (incl. PixysOS) | 🆕 **this file** (§3) — README only lists two MD5s |
| **Current status (paused at boot animation) + what remains** | 🆕 **this file** (§4) |
| **Credits** | 🆕 **this file** (§5) |
| **Next steps** | 🆕 **this file** (§6) |

> ⚠️ One discrepancy found while preparing this file: the repo's current
> [`fix/audio_policy_configuration.xml`](fix/audio_policy_configuration.xml) still uses
> the **enum strings** (`AUDIO_DEVICE_OUT_SPEAKER`) in `<attachedDevices>` /
> `<defaultOutputDevice>`. The corrected version (using `tagName`s) is the workspace
> `audio_policy_configuration.xml`. See §2.6 and §6 for the action item.

---

## 2. Complete fix summary (5 manifest fixes + 1 audio-policy fix)

The boot loop had **six** concrete edits across three files. Five are in the device HAL
manifest and its service config; one is the audio policy. Each is shown with the exact
before/after fragment (derived from the local `manifest.xml` /
`manifest_current.xml` / `hwservicemanager.rc` / `audio_policy_configuration.xml`
artifacts).

### 2.1 `manifest.xml` — remove `target-level="legacy"` from the root element

`target-level` is not a valid attribute on an Android 10 **device** manifest (the device
manifest root accepts only `version` + `type`). Its presence made `libvintf` reject the
whole manifest, so `VintfObject::GetDeviceHalManifest()` returned **null** and
`hwservicemanager` dereferenced it → SIGSEGV.

```xml
<!-- BEFORE -->
<manifest version="1.0" type="device" target-level="legacy">
```
```xml
<!-- AFTER -->
<manifest version="1.0" type="device">
```

### 2.2 `manifest.xml` — add the missing `IDevice` interface to `android.hardware.renderscript`

Every other `<hal>` block declares an `<interface>` + `<fqname>`; `renderscript` had only
`transport` + `version`, so it was structurally invalid.

```xml
<!-- BEFORE -->
    <hal format="hidl">
        <name>android.hardware.renderscript</name>
        <transport arch="32+64">passthrough</transport>
        <version>1.0</version>
    </hal>
```
```xml
<!-- AFTER -->
    <hal format="hidl">
        <name>android.hardware.renderscript</name>
        <transport arch="32+64">passthrough</transport>
        <version>1.0</version>
        <interface>
            <name>IDevice</name>
            <instance>default</instance>
        </interface>
        <fqname>@1.0::IDevice/default</fqname>
    </hal>
```

### 2.3 `manifest.xml` — remove the duplicate `android.hardware.cas@1.0` entry

The main manifest declared `android.hardware.cas@1.0` while the vendor fragment already
declared `cas@1.1` — a duplicate HAL that libvintf rejects. The fix removes the whole
`cas@1.0` block from the main manifest, leaving the fragment's `1.1` as the only
declaration.

```xml
<!-- BEFORE (present in the pulled manifest) -->
    <hal format="hidl">
        <name>android.hardware.cas</name>
        <transport>hwbinder</transport>
        <version>1.0</version>
        <interface>
            <name>IMediaCasService</name>
            <instance>default</instance>
        </interface>
        <fqname>@1.0::IMediaCasService/default</fqname>
    </hal>
```
```xml
<!-- AFTER (block deleted entirely; the fragment's cas@1.1 remains) -->
```

The committed final manifest ([`fix/manifest.xml`](fix/manifest.xml)) has no `cas` block
between `camera.provider` and `configstore`, confirming the removal. The same change is in
[`fix/manifest.patch`](fix/manifest.patch).

### 2.4 Vendor HALs — relabel `light`/`power` and disable two mislabeled HALs

This one is a **`.rc` / SELinux** change, not an edit inside `manifest.xml`, so there is
no manifest fragment to show. The vendor HAL services were running under the wrong
SELinux labels, so init either failed to start them or `avc: denied` prevented them from
registering:

- `android.hardware.light` service → relabel to `u:object_r:hal_light_default_exec:s0`
- `android.hardware.power` service → relabel to `u:object_r:hal_power_default_exec:s0`
- `livedisplay-legacymm` and `cryptfshw` — two **non-essential** mislabeled vendor HAL
  services. Rather than fix their labels, they were **disabled by renaming their `.rc`
  files** (e.g. appending `.disabled`) so init no longer starts them.

> Note: the raw `.rc` / `file_contexts` files for these four services are not among the
> local artifacts in this session (only `hwservicemanager.rc` is), so the fragments above
> are stated from the README's fix record rather than reproduced byte-for-byte.

### 2.5 `hwservicemanager.rc` — remove the `critical` keyword

The `critical` keyword makes a crash of that service fatal-reboot the device. Removing it
lets `hwservicemanager` restart without taking the whole boot down — useful for diagnosis
and safe here. Only the **standalone** `critical` line was removed; the unrelated
`shutdown critical` at the end was kept.

```text
# BEFORE (service hwservicemanager /system/bin/hwservicemanager)
    group system readproc
    critical
    onrestart setprop hwservicemanager.ready false
```
```text
# AFTER
    group system readproc
    onrestart setprop hwservicemanager.ready false
```

The post-edit `hwservicemanager.rc` on disk is:

```text
service hwservicemanager /system/bin/hwservicemanager
    user system
    disabled
    group system readproc
    onrestart setprop hwservicemanager.ready false
    onrestart class_restart main
    onrestart class_restart hal
    onrestart class_restart early_hal
    writepid /dev/cpuset/system-background/tasks
    class animation
    shutdown critical
```

### 2.6 `audio_policy_configuration.xml` — device tags must be **tagNames**, not enum strings

The ROM ships only the legacy `vendor/etc/audio_policy.conf`; Android 10's
`libaudiopolicyenginedefault` requires an `audio_policy_configuration.xml`, and without it
`audioserver` crashes in `EngineBase::loadAudioPolicyEngineConfig()`.

The subtle rule that matters when writing that file: the values inside
`<attachedDevices>` / `<defaultOutputDevice>` must be the **`tagName`** of a
`<devicePort>` (e.g. `Speaker`), **not** the raw enum string (`AUDIO_DEVICE_OUT_SPEAKER`).
The enum string belongs only in the `type=` attribute of the `<devicePort>` element.

```xml
<!-- BEFORE (WRONG — enum strings; the parser looks for a devicePort tagName
     literally named "AUDIO_DEVICE_OUT_SPEAKER", which does not exist) -->
<globalConfiguration speaker_driver_status_dummy_device="false">
    <attachedDevices>
        <item>AUDIO_DEVICE_OUT_EARPIECE</item>
        <item>AUDIO_DEVICE_OUT_SPEAKER</item>
        <item>AUDIO_DEVICE_OUT_TELEPHONY_TX</item>
    </attachedDevices>
    <defaultOutputDevice>AUDIO_DEVICE_OUT_SPEAKER</defaultOutputDevice>
</globalConfiguration>
```
```xml
<!-- AFTER (CORRECT — tagNames referencing the devicePort elements) -->
<globalConfiguration speaker_drc_enabled="false"/>
...
<module name="primary" halVersion="2.0">
    <attachedDevices>
        <item>Earpiece</item>
        <item>Speaker</item>
    </attachedDevices>
    <defaultOutputDevice>Speaker</defaultOutputDevice>
```
```xml
    <!-- and the devicePorts those tagNames point at: -->
    <devicePort tagName="Earpiece" type="AUDIO_DEVICE_OUT_EARPIECE" role="sink"/>
    <devicePort tagName="Speaker"  type="AUDIO_DEVICE_OUT_SPEAKER"  role="sink"/>
```

The corrected file is the workspace `audio_policy_configuration.xml` (header comment:
*"attachedDevices use tagNames (correct per AOSP Serializer)"*). The repo's current
[`fix/audio_policy_configuration.xml`](fix/audio_policy_configuration.xml) still contains
the enum-string form and should be replaced with the corrected version.

---

## 3. Complete file list, download links, and checksums

All links below were checked against live pages (2026-11-11). MD5s are the verified ones
from the device/session. Local copies also exist under `C:\Users\iMac2019\mi4i-flash\`
(listed as a fallback — these are not redistributed in the repo, see README §Legal).

### 3.1 LineageOS 17.1 (Android 10) — the ROM this repo fixes

- **Working mirror (verified):** [afharchive.xyz/file/355](http://afharchive.xyz/file/355)
  — `lineage-17.1-20200628-UNOFFICIAL-ferrari.zip`, 526.31 MB.
- **MD5:** `a86cb2ef282e249962f688d8a4e5f46a`
- Original AndroidFileHost link (may be dead): `https://androidfilehost.com/?fid=8889791610682879431`.
  The afharchive page notes the build is *"Endangered … newer build by same developer
  already gone dead on AFH"* and offers an **Internet Archive** mirror on the same page.
- Local archive: `C:\Users\iMac2019\mi4i-flash\lineage-17.1-20200628-UNOFFICIAL-ferrari.zip`
  (551,871,991 bytes).

### 3.2 TWRP 3.7.0_9-0 (official, TeamWin)

- **Official page:** [dl.twrp.me/ferrari](https://dl.twrp.me/ferrari/) →
  [`twrp-3.7.0_9-0-ferrari.img.html`](https://dl.twrp.me/ferrari/twrp-3.7.0_9-0-ferrari.img.html)
  (25.8 MB, 2022-10-09). Per TeamWin's terms, link the **HTML page**, not the raw `.img`.
- Local archive: `C:\Users\iMac2019\mi4i-flash\twrp-3.7.0_9-0-ferrari.img` (27,011,072 bytes).

### 3.3 OpenGApps — `arm64` / Android 10.0 / pico

- **Official SourceForge:** [OpenGApps arm64 10.0 pico (20220503)](https://sourceforge.net/projects/opengapps/files/arm64/20220503/open_gapps-arm64-10.0-pico-20220503.zip/download)
  — use user agent `Wget/1.21`; the `.md5` sits beside the same URL with `.md5` appended.
- **MD5:** `2feaf25d03530892c6146687ffa08bc2`
- Local archive: `C:\Users\iMac2019\mi4i-flash\open_gapps-arm64-10.0-pico-20220503.zip`
  (149,994,980 bytes).

### 3.4 PixysOS v2.4 (Android 9) — the fallback ROM

- **Working mirror (verified):** [afharchive.xyz/file/356](http://afharchive.xyz/file/356)
  — `PixysOS-v2.4-ferrari-UNOFFICIAL-20200711-100341.zip`, 466.48 MB.
- **MD5:** `a6e48721313064f98ca1d30603b7b8f8`
- XDA thread (source): [ROM][UNOFFICIAL] PixysOS v2.4 (Android 9)](https://xdaforums.com/t/rom-unofficial-pixysos-v2-4-android-9.4131769/)
- Internet Archive direct link (used by the downloader script):
  [archive.org …/PixysOS-v2.4-ferrari-UNOFFICIAL-20200711-100341.zip](https://archive.org/download/afharchive_356_pixysos-v24-ferrari-unofficial-20200711-100341zip/PixysOS-v2.4-ferrari-UNOFFICIAL-20200711-100341.zip)
- Local archive: `C:\Users\iMac2019\mi4i-flash\PixysOS-v2.4-ferrari-UNOFFICIAL-20200711-100341.zip`
  (489,138,058 bytes — now **complete**; it was incomplete/369 MB at the time of the
  original handoff).

### 3.5 Supplementary — OpenGApps `arm64` / Android 9.0 / pico (for PixysOS)

- [OpenGApps arm64 9.0 pico (20220503)](https://sourceforge.net/projects/opengapps/files/arm64/20220503/open_gapps-arm64-9.0-pico-20220503.zip/download)
- **MD5:** `8395a4372fc477a8be21bfe87eeb1465`
- Local archive: `C:\Users\iMac2019\mi4i-flash\open_gapps-arm64-9.0-pico-20220503.zip`
  (152,915,332 bytes).

### 3.6 Stock backups (keep these — IMEI/EFS safety net)

`C:\Users\iMac2019\mi4i-flash\backup-stock\`: `modemst1.img`, `modemst2.img`, `fsg.img`,
`fsc.img`, `persist.img`, `sec.img`, and the stock MIUI `boot.img` (all MD5-verified
against the device).

---

## 4. Current status and what remains

**Status (as of 2026-11-11, paused):**

- All six fixes from §2 were applied on-device.
- The device **no longer hangs at the static Mi logo** — the `hwservicemanager` /
  `audioserver` crash loop is gone and the phone now reaches the **LineageOS boot
  animation**.
- It is **still stuck there**: the user reported *"still in green line"* ~30 min after
  the audio-policy fix, i.e. first boot has not yet completed to the setup screen.

**What remains:**

1. **Confirm whether first boot ever completes.** First boot of Android 10 + GApps pico on
   a 2 GB / 8×Cortex-A53 device is slow (dex2oat runs at first boot). Give it a genuinely
   long window while watching `logcat`.
2. **Capture `logcat` during the boot-animation phase** (not the pre-animation crash
   phase) to see what is blocking: a service crash-looping, `dex2oat` still running, or a
   GApps/setup problem. `system_server` is now starting, so the failure mode is different
   from the original manifest crash.
3. **Push the corrected audio policy** (§2.6) so the on-device
   `audio_policy_configuration.xml` uses `tagName`s, and restore its permissions/SELinux
   context (`0644`, `u:object_r:vendor_configs_file:s0`) before rebooting.
4. **Isolate GApps** by testing a ROM-only boot (no GApps) if the animation phase won't
   finish — this separates a ROM issue from a GApps/setup issue.
5. **Fall back to PixysOS v2.4 (Android 9)** if LineageOS 17.1 first boot cannot be
   completed. PixysOS is now fully downloaded and MD5-verified (§3.4), so the switch is
   ready to execute per `docs/HANDOFF.md`.

---

## 5. Credits

- **LineageOS** — the `ferrari` device tree and the 17.1 (Android 10) build
  ([`LineageOS/android_device_xiaomi_ferrari`](https://github.com/LineageOS/android_device_xiaomi_ferrari)).
  `fix/manifest.xml` is a small modification of the manifest authored by the `ferrari`
  maintainer.
- **TWRP / Team Win** — official `twrp-3.7.0_9-0-ferrari.img`
  ([twrp.me](https://twrp.me/xiaomi/xiaomimi4i.html)).
- **OpenGApps** — the `arm64` 10.0 pico (and 9.0 pico) GApps packages.
- **PixysOS** — the Android 9 (v2.4) fallback build and its maintainer.
- **XDA community** — the device guides and the reports that cross-confirmed the
  "MI logo forever" symptom for this exact build.
- **AFHArchive / JoshAtticus** — the preserved AndroidFileHost mirrors that keep these
  otherwise-dead builds downloadable.

---

## 6. Next steps

1. Push this `FINAL.md` and, if the parent session approves, replace the repo's
   [`fix/audio_policy_configuration.xml`](fix/audio_policy_configuration.xml) with the
   corrected tagNames version (workspace `audio_policy_configuration.xml`).
2. On the device (still in TWRP / bootable from fastboot), push the corrected audio policy,
   restore its permissions + SELinux context, then boot and run a **long** `logcat`
   capture through the boot-animation phase.
3. If first boot completes → document the final "setup screen reached" state and close out.
4. If it does not → test ROM-only boot (no GApps) to isolate the blocker; if the ROM alone
   boots, the issue is GApps/setup-related. If neither completes, execute the PixysOS v2.4
   fallback (files ready, MD5-verified).
5. Keep the stock backups (§3.6) intact throughout — they are the IMEI/EFS safety net.
