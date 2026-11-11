# Mi 4i (ferrari) LineageOS 17.1: TWRP flashable fix pack

**`mi4i-ferrari-los17.1-fixpack-20261111.zip`**: SHA-256 `c97eb382352a8b0189202e7b5f494e95c701a2d599ef6d4686c8eaabee847149`

Applies every fix from this repo in one flash:

| Fix | File |
|---|---|
| Boot (VINTF) + WiFi (supplicant @1.2) | `/vendor/etc/vintf/manifest.xml` |
| Audio (complete `<volumes>`) | `/vendor/etc/audio_policy_configuration.xml`, `/system/etc/audio_policy_configuration.xml` |
| Bluetooth (no `bluetooth_loader` seclabel) + thermal (thermal-engine disabled, kernel msm_thermal on) | `/vendor/etc/init/hw/init.qcom.rc` |
| WiFi HAL socket dir | `/vendor/etc/init/android.hardware.wifi@1.0-service.legacy.rc` |

## Use
1. Flash `lineage-17.1-20200628-UNOFFICIAL-ferrari.zip` (+ GApps if wanted) in TWRP.
2. Flash this zip (or: `adb push <zip> /tmp/ && adb shell twrp install /tmp/<zip>`).
3. Reboot.

Safety: refuses to run unless the device is `ferrari` and LineageOS 17.1 is on system.
Originals are saved to `/system/mi4i-fix-backup/`.

Tested 2026-11-11 with TWRP 3.7.0_9-0: installed with RC=0 and booted; WiFi connected with internet, Bluetooth ON, audioserver running, thermal-engine not running.
Source of the zip: `src/`.
