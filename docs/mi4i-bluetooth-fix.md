# Bluetooth fix — `bluetooth_loader` SELinux type missing

## Symptom
After the manifest + audio-policy fixes, the phone boots to the Google setup screen with no
factory-reset loop, but **"Bluetooth keeps stopping"** pops up repeatedly.

## Root cause
`init` could not launch the Qualcomm HCI attach service because its SELinux label references a
type that does not exist in the LineageOS 17.1 GSI's policy:

```
F init: cannot setexeccon('u:r:bluetooth_loader:s0') for hciattach: Invalid argument
```

The vendor init script `/vendor/etc/init/hw/init.qcom.rc` (line ~169) declared:

```
service hciattach /system/vendor/bin/init.qcom.bt.sh
    ...
    seclabel u:r:bluetooth_loader:s0
```

The `bluetooth_loader` SELinux domain is not defined in the GSI's sepolicy (SELinux is
permissive, but `setexeccon` fails with `EINVAL` for an *undefined* type regardless of permissive
mode). Because `hciattach` never ran, the HCI UART was never set up, the Bluetooth stack's
startup timer expired (`libbluetooth.so startup_timer_expired`), `com.android.bluetooth` died,
and its death also crashed the HAL (`BluetoothHci::close()` → `std::bad_function_call`).

## Fix
Remove the invalid `seclabel` line so `hciattach` runs in the default init context:

```sh
adb root
adb shell "mount -o rw,remount /"
adb shell "sed -i '/bluetooth_loader/d' /vendor/etc/init/hw/init.qcom.rc"
adb reboot
```

Result: `init.svc.vendor.bluetooth-1-0=running`, `vendor.bluetooth.status=on`,
`sys.boot_completed=1`, and no more Bluetooth crash-loop.

## Summary of all Mi 4i fixes
1. **VINTF manifest** — removed `target-level="legacy"`, added `IDevice` to renderscript,
   removed duplicate `cas@1.0`, disabled mislabeled HALs, removed `hwservicemanager` `critical`.
2. **Audio policy** — added a complete `<volumes>` section (all 13 streams) to
   `audio_policy_configuration.xml`; use tagNames in `<attachedDevices>`/`<defaultOutputDevice>`;
   use concrete device types (`BLUETOOTH_SCO`/`BLUETOOTH_A2DP`, not `*_ALL_*` aliases).
3. **Bluetooth** — removed the invalid `seclabel u:r:bluetooth_loader:s0` from the `hciattach`
   service in `init.qcom.rc`.
