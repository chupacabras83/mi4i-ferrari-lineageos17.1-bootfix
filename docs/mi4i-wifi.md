# Mi 4i (ferrari) — WiFi on LineageOS 17.1: FIXED

Status (2026-11-11 14:30 SGT): **WiFi works.** `dumpsys wifi` → `Wi-Fi is enabled`,
`wpa_supplicant` running, scans return 2.4 GHz and 5 GHz networks (RSSI around −28 dBm near the AP).

## Symptoms (before)
- `wifi_on=1` but `Wi-Fi is disabled`; WifiController loops `StaEnabledState → StaDisabledWithScanState`
- Driver healthy: prima `wlan` v3.0.11.85, WCNSS `CNSS-PR-2-0-1-c4-00017`, `wlan.driver.status=ok`

## Fix 1: create the WiFi HAL socket directory
`libwifi-hal.so` binds `/dev/socket/wifihal/wifihal_ctrlsock`; nothing created the dir.
Append to `/vendor/etc/init/android.hardware.wifi@1.0-service.legacy.rc` (file in `fix/wifi/`):
```
on post-fs
    mkdir /dev/socket/wifihal 0770 wifi wifi
```

## Fix 2 (the real blocker): supplicant HIDL version in the VINTF manifest
Framework log (`docs/wifi-failure-logcat-before-fix.txt`):
```
I SupplicantStaIfaceHal: Completed initialization of ISupplicant.
E SupplicantStaIfaceHal: Got zero HIDL supplicant ifaces. Stopping supplicant HIDL startup.
E SupplicantStaIfaceHal: setupIface got null iface
E WifiNative: Failed to setup iface in supplicant on Iface:{Name=wlan0,...STA_CONNECTIVITY}
```
`wpa_supplicant` (v2.8-devel) implements `android.hardware.wifi.supplicant@1.2`, and the
Android 10 framework requires ≥1.1 to add an interface. But `/vendor/etc/vintf/manifest.xml`
declared only **@1.0**, so hwservicemanager registered only 1.0. The framework could not create
the STA interface and killed the supplicant about 4 s later.

Fix (`fix/wifi/manifest-supplicant-1.2.patch`, full file `fix/manifest.xml`):
```diff
         <name>android.hardware.wifi.supplicant</name>
         <transport>hwbinder</transport>
-        <version>1.0</version>
+        <version>1.2</version>
 ...
-        <fqname>@1.0::ISupplicant/default</fqname>
+        <fqname>@1.2::ISupplicant/default</fqname>
```
After reboot, `lshal` shows supplicant @1.0, @1.1 and @1.2 registered, and WiFi comes up.

Apply with adb (userdebug build):
```
adb root
adb shell mount -o rw,remount /
adb push manifest.xml /vendor/etc/vintf/manifest.xml
adb shell "chmod 0644 /vendor/etc/vintf/manifest.xml; chcon u:object_r:vendor_configs_file:s0 /vendor/etc/vintf/manifest.xml"
adb reboot
```

## Harmless leftovers
`acquire_driver_supported_features: requestResponse Error:-3` / `Failed to get wifi Capabilities`
is still logged. The modern Qualcomm HAL asks prima for QCA vendor features it doesn't have.
This is non-fatal: features are reported as 0 (no GSCAN/logger/RTT), and normal STA works.
Same for `wificond: Failed to get NL80211_ATTR_EXT_FEATURES`.

## Earlier investigation (no longer needed)
The stock MIUI V6.6.10.0 WiFi files were pulled from the recovery OTA with HTTP Range requests
(`scripts/extract_stock_wifi_ranged.py`; hashes in `fix/wifi/stock-miui-V6.6.10.0-wifi-files.sha256`).
Its HAL `libwifi-hal-qcom.so` (Android 5) lacks `init_wifi_vendor_hal_func_table` and
can't replace the Android 10 HAL. It turned out not to be needed.

## Unrelated issue seen
`thermal-engine` (root, pid ~387) was using about 1000% CPU (load average about 12), which makes the
phone sluggish and adb slow. Worth looking at next (e.g. the thermal-engine config, or disabling it).
