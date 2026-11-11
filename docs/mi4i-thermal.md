# Mi 4i (ferrari): thermal-engine CPU hog: FIXED

## Symptom
`thermal-engine` (root, `/system/vendor/bin/thermal-engine`, stock Android 5 blob) used **300–1000% CPU**
permanently. Load average was about 12–14, the UI was sluggish, and adb/logcat often hung.

## Diagnosis
- One thread (`top -H`) at 100%; `strace` shows it spinning:
  `futex(..., FUTEX_WAIT_BITSET, ...) = -1 EAGAIN` about 1800×/s (a busy-loop on a stale futex value).
- Its config `/system/etc/thermal-engine-8939.conf` is fine (temps 48–63 °C, no alarms firing).
- Restarting it, or pointing `-c` at the config explicitly, does not help: it spins again right away.
  Most likely the old Android 5 binary is incompatible with Android 10 bionic.

## Fix (`fix/thermal/init.qcom.rc-thermal.patch`)
In `/vendor/etc/init/hw/init.qcom.rc`:
- mark `service thermal-engine` **`disabled`**
- turn on the kernel's own thermal driver at boot instead:
```
on boot
    write /sys/module/msm_thermal/parameters/enabled Y
    write /sys/module/msm_thermal/core_control/enabled 1
```
Kernel `msm_thermal` still throttles and hotplugs CPUs, and the tsens trip points (85–115 °C) still apply.

## Result
After reboot: `init.svc.thermal-engine` is empty (not started), `msm_thermal enabled=Y`, and the CPU
hog is gone. The load right after boot is from `dex2oat` (normal first-boot app compiling).

Backup of the original: `C:\Users\iMac2019\mi4i-flash\backup-stock\init.qcom.rc.before-thermal`

Apply:
```
adb root && adb shell mount -o rw,remount /
adb push fix/thermal/init.qcom.rc /vendor/etc/init/hw/init.qcom.rc
adb shell "chmod 0644 /vendor/etc/init/hw/init.qcom.rc; chcon u:object_r:vendor_configs_file:s0 /vendor/etc/init/hw/init.qcom.rc"
adb reboot
```
