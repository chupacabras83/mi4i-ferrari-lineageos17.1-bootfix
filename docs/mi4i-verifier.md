# Mi 4i (ferrari) audioserver crash — independent verification

Verified against the tombstone, the two XML artifacts in the workspace, and the actual
Android 10 (`android-10.0.0_r1`) `libaudiopolicyenginedefault` source
(`EngineBase.cpp`, `EngineConfig.cpp`, `EngineDefaultConfig.h`, `audioserver.rc`,
`audio_policy_configuration.xml`, `audio_policy_volumes.xml`).

## 1. Crash confirmed — NULL deref in `loadAudioPolicyEngineConfig()`

Yes. `tombstone_00` is unambiguous:

- `signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x0` + `Cause: null pointer dereference`.
- Frame `#00` = `EngineBase::loadAudioPolicyEngineConfig()+2340` in
  `libaudiopolicyenginedefault.so`, reached via `Engine::Engine()` →
  `EngineInstance::queryInterface()` → `AudioPolicyManager::initialize()`.

### My hypothesis (mechanism, from source — not the other agent's conclusion)

`EngineBase::loadAudioPolicyEngineConfig()` (Android 10, `engine/common/src/EngineBase.cpp`) does:

1. `engineConfig::parse()` → reads **`/vendor/etc/audio_policy_engine_configuration.xml`**
   (`EngineConfig.h`: `DEFAULT_PATH`). This legacy-only ROM does not ship it, so it returns
   `nullptr`.
2. Fallback: `config = gDefaultEngineConfig` (hardcoded product strategies; **empty**
   `volumeGroups`), then `engineConfig::parseLegacyVolumes(config.volumeGroups)`.
3. `parseLegacyVolumes()` reads the **`<volumes>`** section out of
   `audio_policy_configuration.xml` (searching `/odm/etc`, `/vendor/etc`, `/system/etc`).
   The ROM ships only the legacy `audio_policy.conf` and **no** such XML, so `volumeGroups`
   stays **empty**.
4. `loadVolumeGroups(empty)` → `mVolumeGroups` empty. Then `loadProductStrategies(...)`:

```cpp
const auto &iter = std::find_if(begin(volumeGroups), end(volumeGroups),
    [&group](const auto &v){ return group.volumeGroup == v.second->getName(); });
ALOGE_ASSERT(iter != end(volumeGroups), "Invalid Volume Group Name %s", ...); // logs, does NOT abort
if (group.stream != AUDIO_STREAM_DEFAULT)
    iter->second->addSupportedStream(group.stream);   // <-- iter == end() → NULL deref
```

`iter == end(mVolumeGroups)` because the map is empty, `iter->second` is a null
`sp<VolumeGroup>`, and the member call faults at `0x0`. The heap strings in the dump
(`STRATEGY_PHONE`, `STRATEGY_SONIFICATION`, `STRATEGY_ACCESSIBILITY`, `phone`, `sco`,
`ring`, `AUDIO_STREAM_RING`) are exactly `gDefaultEngineConfig`'s `gOrderedStrategies`,
confirming the fallback path and that the crash hits the **first** strategy (`STRATEGY_PHONE`)
because the volume-group map is empty. The missing-volume-group diagnostic would have been
logged immediately before the fault as `Invalid Volume Group Name AUDIO_STREAM_VOICE_CALL`.

**Bottom line: the crash is 100% an audio-config bug, not a memory-corruption/random fault.**

## 2. Is audioserver a boot blocker? — No, not by itself

- Android 10 `frameworks/av/media/audioserver/audioserver.rc` defines audioserver as
  `class core` with **no `critical` keyword**. `critical` is what makes a crash fatal-reboot
  the device (that was the hwservicemanager issue, already fixed). audioserver crashing in a
  loop is restarted by init and is **not** fatal, and its `onrestart` only restarts the audio
  HALs (`vendor.audio-hal-2-0`, `audio-hal-2-0`).
- A non-critical audioserver crash-loop does **not** block `sys.boot_completed=1`; stock AOSP
  `AudioService` tolerates audioserver being down/restarting. So the phone would normally
  still reach the launcher (silent).

**Verdict:** fixing audioserver is **necessary** (no audio; 50 crash/restart cycles also
churn CPU, logs and tombstones on a 2 GB first-boot device) but is **not sufficient** to
explain a hang at the boot animation once `hwservicemanager` is fixed and `packages.xml`
exists. The hang is most likely (a) first-boot `dex2oat` + GApps setup on 2 GB, or (b) a
second blocker. **A fresh `adb logcat -b all` during the animation is required** before
declaring boot fixed — see §4.

## 3. Concrete bugs in the XML (ranked) + the fix

### Workspace `audio_policy_configuration.xml` (tagNames correct)

1. **[FATAL] Missing `<volumes>` entirely.** This is the direct cause of the crash above:
   even with this file pushed, `parseLegacyVolumes()` finds no `<volume>` elements →
   empty volume groups → same SIGSEGV. This file does **not** fix the crash.

### `mi4i-ferrari-lineageos17.1-bootfix/fix/audio_policy_configuration.xml`

1. **[FATAL] `<volumes>` present but incomplete.** It lists 11 of the 13 streams the
   fallback engine requires. `gDefaultEngineConfig` also defines
   `STRATEGY_REROUTING` → `AUDIO_STREAM_REROUTING` and `STRATEGY_PATCH` →
   `AUDIO_STREAM_PATCH`. With these missing, the loader gets past the early strategies and
   then **crashes at `STRATEGY_REROUTING`** with `Invalid Volume Group Name
   AUDIO_STREAM_REROUTING`. So this file, as-is, still crashes audioserver (later).
2. (Minor, non-crashing) `globalConfiguration` uses `speaker_driver_status_dummy_device`
   instead of `speaker_drc_enabled` — irrelevant to this crash.

### Single most likely fix

Ship **one** `/vendor/etc/audio_policy_configuration.xml` that has **both**:

- the `<modules>` section from the workspace file (tagNames are already correct), **and**
- a **complete** `<volumes>` section covering **all 13 legacy streams**:
  `VOICE_CALL, SYSTEM, RING, MUSIC, ALARM, NOTIFICATION, BLUETOOTH_SCO,
  ENFORCED_AUDIBLE, DTMF, TTS, ACCESSIBILITY, REROUTING, PATCH`.

Minimal delta to the existing `fix/` file — append the two missing streams (any valid
`deviceCategory` makes the group exist; 0 dB is correct for pass-through streams):

```xml
<volume stream="AUDIO_STREAM_REROUTING" deviceCategory="DEVICE_CATEGORY_HEADSET">
    <point>0,0</point><point>100,0</point>
</volume>
<volume stream="AUDIO_STREAM_REROUTING" deviceCategory="DEVICE_CATEGORY_SPEAKER">
    <point>0,0</point><point>100,0</point>
</volume>
<volume stream="AUDIO_STREAM_PATCH" deviceCategory="DEVICE_CATEGORY_HEADSET">
    <point>0,0</point><point>100,0</point>
</volume>
<volume stream="AUDIO_STREAM_PATCH" deviceCategory="DEVICE_CATEGORY_SPEAKER">
    <point>0,0</point><point>100,0</point>
</volume>
```

(Equivalent alternative: also provide `/vendor/etc/audio_policy_engine_configuration.xml`
in the new `<volumeGroups>` format so `engineConfig::parse()` never falls back — but the
`<volumes>` addition above is the minimal, idiomatic fix for a legacy-only device.)

Permissions/SELinux after push: `0644`, `u:object_r:vendor_configs_file:s0`.

## 4. What a fresh `adb logcat -b all` must show to confirm the fix

Success (audioserver fixed):
- **No** `Fatal signal 11 (SIGSEGV)` from `audioserver`, and no new `tombstone_*` for
  `audioserver` with `loadAudioPolicyEngineConfig`.
- **No** `APM::AudioPolicyEngine/Base: Invalid Volume Group Name ...` line (that log
  precedes the fault).
- Expected-but-benign: `APM::AudioPolicyEngine/Base: No configuration found, using default
  matching phone experience.` (fallback) — must be followed by normal init, not a crash.
- `audioserver` stays alive: `getprop init.svc.audioserver` → `running`, and it is no longer
  restarted by init.
- `AudioPolicyService`/`AudioFlinger` publish: `AudioPolicyService` registered; `ps -A |
  grep audioserver` shows one stable pid; audio HAL loads (`audio_hw_primary` /
  `primary audio hw device`).

Boot completion (separate question — audioserver fix alone may not be enough):
- `getprop sys.boot_completed` → `1`, and
  `SystemServerTiming` / `OnBootPhase_1000` → `ActivityManager: Boot completed` /
  `finishBooting()`.
- SetupWizard/launcher surface; `dex2oat` finishing (watch for `dex2oat` draining rather
  than erroring), and no other `FATAL EXCEPTION` / persistent-service crash-loop.

If `sys.boot_completed` stays `0` while audioserver is now stable, capture `-b all` and
look for the real second blocker (dex2oat, GApps, or another crash) — do not assume audio
was the only issue.
