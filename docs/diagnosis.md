# Diagnosis: why LineageOS 17.1 hung at the Mi logo

## Symptoms

After flashing `lineage-17.1-20200628-UNOFFICIAL-ferrari` + OpenGApps 10.0 pico, the phone
booted only as far as the Mi logo and never reached the Android UI. The framework never
started: `/data/app`, `/data/data`, and `/data/dalvik-cache` stayed empty and
`/data/system/packages.xml` was never created, meaning `system_server` never finished
initializing.

## Crash inventory (from `/data/tombstones`)

Every tombstone was a `SIGSEGV` (signal 11) with `fault addr 0x0` (null pointer). Four
processes crashed repeatedly:

| Process | Crash location |
|---------|----------------|
| `hwservicemanager` | `libvintf.so` → `HalManifest::getInstances()` |
| `audioserver` | `libaudiopolicyenginedefault.so` → `EngineBase::loadAudioPolicyEngineConfig()` |
| `android.hardware.memtrack@1.0-service` | `libc.so` → `je_free`/`je_large_dalloc` (HIDL object destruction) |
| `netd` | `libc.so` → `je_free`/`je_large_dalloc` (HIDL object destruction) |

## Root cause: `hwservicemanager` (the first domino)

`hwservicemanager` is the HIDL service registry. Its backtrace was:

```
#00 libvintf.so  HalManifest::getInstances(name, version, interfaceName) const +64
#01 hwservicemanager  android::hardware::getInstances(name) +212
#02 hwservicemanager  ServiceManager::listManifestByInterface(...) +136
#03 libhidlbase.so  BnHwServiceManager::_hidl_listManifestByInterface(...)
```

The crash register `x0 == 0x0` means `getInstances()` was invoked with a **null `this`**
pointer, i.e. `VintfObject::GetDeviceHalManifest()` returned **null** — the device HAL
manifest failed to parse/validate in libvintf.

Two anomalies in `/vendor/etc/vintf/manifest.xml` explain the failure:

1. **`target-level="legacy"`** on the root element — not valid for an Android 10 device
   manifest (the device manifest root only takes `version` + `type`).
2. **`android.hardware.renderscript`** HAL declared with **no `<interface>`/`<fqname>`**
   while every other HAL has them.

With the manifest rejected, `GetDeviceHalManifest()` returned null, and the
`listManifestByInterface` code path dereferenced it → SIGSEGV.

## The cascade

- `hwservicemanager` dies → all HIDL clients lose their registry.
- `memtrack@1.0-service` and `netd`'s HIDL threads then exit their thread pools and crash
  during object destruction (`RefBase::decStrong → BnHwBase::~BnHwBase → je_free`). This is
  a **secondary** shutdown-path crash, not an independent root cause.
- `audioserver` crashes independently: the ROM ships only the legacy
  `vendor/etc/audio_policy.conf` and no `audio_policy_configuration.xml`, which Android 10's
  `libaudiopolicyenginedefault` requires. This is a separate bug (audio), generally not a
  boot blocker.

## The fix

Make the device manifest valid so it loads: remove `target-level="legacy"` and add the
missing `renderscript` `<interface>`/`<fqname>`. See
[`fix/manifest.patch`](../fix/manifest.patch).

This addresses the first domino. (The `audioserver` audio-policy crash is a follow-up,
audio-specific issue that does not block boot.)

## How this was confirmed

- `hwservicemanager` SIGSEGV backtrace (above) with `x0 = 0`.
- `memtrack` and `netd` sharing an *identical* shutdown-path backtrace (secondary).
- Manifest inspected on-device; the two anomalies above are the only structural deviations
  from a well-formed Android 10 device manifest.
