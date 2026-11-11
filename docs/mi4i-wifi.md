# Mi 4i (ferrari) — WiFi on LineageOS 17.1: status & findings

Status: **not working yet**. Driver loads; the Android 10 WiFi HAL fails the capability query.

## Symptoms
- `settings get global wifi_on` = 1, but `dumpsys wifi` → `Wi-Fi is disabled`
- `StaEnabledState → StaDisabledWithScanState` (enable fails)
- Kernel side is healthy: `wlan: loading driver v3.0.11.85`, `WCNSS WLAN version 1.5.1.2`,
  `CNSS-PR-2-0-1-c4-00017`, `WCN v2.0 RadioPhy vIris_TSMC_4.0`, `wlan.driver.status=ok`
- Running: `android.hardware.wifi@1.0-service.legacy` (user wifi), `wificond`, `wcnss_service`

## Layer 1 — FIXED: missing HAL control-socket directory
`libwifi-hal.so` binds `/dev/socket/wifihal/wifihal_ctrlsock`, but nothing created the
directory → `ctrl_iface bind(PF_UNIX) failed: No such file or directory`.

Fix (applied on device, file in `fix/wifi/`): append to
`/vendor/etc/init/android.hardware.wifi@1.0-service.legacy.rc`:
```
on post-fs
    mkdir /dev/socket/wifihal 0770 wifi wifi
```
Verified: `/dev/socket/wifihal/wifihal_ctrlsock` now exists after boot.

## Layer 2 — OPEN: `acquire_driver_supported_features: requestResponse Error:-3`
→ `Failed to get wifi Capabilities, error: -3`.

Current on-device HAL `/vendor/lib64/libwifi-hal.so` (481616 bytes,
sha256 `991fed4ce3e195b129abde3bfca12514facbc741f50d2b8c5f92374dba4647ce`):
- is the modern Qualcomm **CLD/qcacld-style** HAL (`NEEDED: libcld80211.so`, LOWI, NAN, `qca_wlan_vendor_features`)
- exports `init_wifi_vendor_hal_func_table` (what the Android 10 HIDL legacy service needs)
- sends QCA vendor nl80211 commands that the old **prima/pronto** driver (v3.0.11.85) does not
  implement → -3 (ESRCH / unsupported vendor cmd).

## Stock MIUI HAL — extracted, but NOT a drop-in
Instead of downloading the full 1 GB ROM, the needed files were pulled straight out of the
recovery OTA zip with HTTP Range requests (`scripts/extract_stock_wifi_ranged.py`, ~10 MB
transferred, every file CRC-verified). 50 files; hashes in
`fix/wifi/stock-miui-V6.6.10.0-wifi-files.sha256`.

Source: `https://bigota.d.miui.com/V6.6.10.0.LXIMICF/miui_MI4iGlobal_V6.6.10.0.LXIMICF_80f20c0908_5.0.zip`

Important: in Android 5 MIUI the HAL is **`/system/lib64/libwifi-hal-qcom.so`** (there is no
`libwifi-hal.so`). ELF analysis:
- `NEEDED: libc, libdl, libhardware_legacy, liblog, libm, libnetutils, libnl, libstdc++`
- exports the bare `wifi_initialize`, `wifi_get_supported_feature_set`, … (C++-mangled), but
  **no `init_wifi_vendor_hal_func_table`**
- imports `wifi_load_driver` / `is_wifi_driver_loaded` from Android 5 `libhardware_legacy`

So simply renaming it to `libwifi-hal.so` will **fail to load** on Android 10
(missing func-table symbol; libstdc++ / old libhardware_legacy ABI).

## Options, best first
1. **Make the existing HAL tolerate the failure.** Error -3 comes only from the feature query;
   a HAL that treats "unsupported" as `feature_set = 0` lets the framework continue
   (this is how most prima-based Android 9/10 ports work: e.g. LineageOS msm8916 trees use
   `WIFI_HAL_INTERFACE_COMBINATIONS` + prima-compatible `wifi-hal` from
   `hardware/qcom/wlan` *legacy* branch, or set `WIFI_DRIVER_STATE_CTRL_PARAM`).
   Look for a ferrari / msm8916 (e.g. `wt88047`, `lettuce`, `harpia`) LineageOS 17.1 build whose
   `/vendor/lib64/libwifi-hal.so` is the prima flavour, and swap that in.
2. **Shim** the stock HAL: a small `libwifi-hal.so` that exports
   `init_wifi_vendor_hal_func_table` and forwards to `libwifi-hal-qcom.so` (also needs the
   Android 5 deps), or returns WIFI_SUCCESS with 0 features for `get_supported_feature_set`.
3. **PixysOS v2.4 (Android 9)** — already on disk, reported to flash fine; WiFi likely works.

## Restore
Back up before any swap:
```
adb root
adb shell mount -o rw,remount /
adb pull /vendor/lib64/libwifi-hal.so libwifi-hal.so.lineage
```
