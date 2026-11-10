# Mi 4i (`ferrari`) audioserver boot crash — root-cause analysis

**ROM:** LineageOS 17.1-20200628-UNOFFICIAL-ferrari (Android 10, non-Treble, MSM8939)
**Crash:** `audioserver` tight crash loop, ~50 tombstones, all SIGSEGV in
`android::audio_policy::EngineBase::loadAudioPolicyEngineConfig()`
(`/system/lib64/libaudiopolicyenginedefault.so`).

```
signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x0
x0  00000076035b35e0   x1  0000000000000000     # x1 == NULL
#00 libaudiopolicyenginedefault.so (EngineBase::loadAudioPolicyEngineConfig()+2340)
#01 libaudiopolicyenginedefault.so (Engine::Engine()+152)
#02 libaudiopolicyenginedefault.so (EngineInstance::queryInterface<AudioPolicyManagerInterface>()+144)
#03 libaudiopolicymanagerdefault.so (AudioPolicyManager::initialize()+88)
```

---

## TL;DR — the exact cause

`EngineBase::loadAudioPolicyEngineConfig()` builds the audio **engine**'s
*product-strategy → volume-group* map. In Android 10 that function ends up with an
**empty `mVolumeGroups` map**, while the (hard-coded) default product strategies reference
volume groups by name. The very first lookup fails, and the code dereferences an invalid
`sp<VolumeGroup>` whose raw pointer is NULL → `SIGSEGV @ 0x0` (`x1 == 0` in the tombstone).

Why is `mVolumeGroups` empty? Two compounding reasons:

1. `engineConfig::parse()` is called with its default path
   `/vendor/etc/audio_policy_engine_configuration.xml` (a file this device does **not** ship),
   so it returns a NULL config and the engine takes the fallback path.
2. The fallback uses the hard-coded default config (`gDefaultEngineConfig`) whose `volumeGroups`
   is **empty**, and then calls `parseLegacyVolumes()` which is supposed to fill volume groups
   from the **`<volumes>`** section of `audio_policy_configuration.xml`. The device's XML is a
   *modules-only* config converted from `audio_policy.conf` — it has **no `<volumes>` section** —
   so zero volume groups are created.

The crash is a symptom of a config that is valid for the *audio-policy manager* (modules/ports/routes)
but incomplete for the *policy engine* (which needs `<volumes>` / `audio_policy_engine_configuration.xml`).

The tombstone memory dump proves the fallback path was taken: the heap contains the default
config's strings — `.STRATEGY_PHONE`, `*STRATEGY_SONIFICATION`, `,STRATEGY_ACCESSIBILITY`,
`.phone`, `.sco`, `.ring`, `AUDIO_STREAM_RING`, and the path buffer
`/vendor/etc/audio_policy_configuration.xml` (built by `parseLegacyVolumes()`).

---

## 1. What `loadAudioPolicyEngineConfig()` does, and where it dereferences NULL

Relevant AOSP `android-10.0.0_r1` sources:

- [`services/audiopolicy/engine/common/src/EngineBase.cpp`](https://android.googlesource.com/platform/frameworks/av/+/refs/tags/android-10.0.0_r1/services/audiopolicy/engine/common/src/EngineBase.cpp)
- [`services/audiopolicy/engine/config/src/EngineConfig.cpp`](https://android.googlesource.com/platform/frameworks/av/+/refs/tags/android-10.0.0_r1/services/audiopolicy/engine/config/src/EngineConfig.cpp)
- [`services/audiopolicy/engine/config/include/EngineConfig.h`](https://android.googlesource.com/platform/frameworks/av/+/refs/tags/android-10.0.0_r1/services/audiopolicy/engine/config/include/EngineConfig.h)
- [`services/audiopolicy/engine/common/src/EngineDefaultConfig.h`](https://android.googlesource.com/platform/frameworks/av/+/refs/tags/android-10.0.0_r1/services/audiopolicy/engine/common/src/EngineDefaultConfig.h)

### 1.1 The function (quoted)

```cpp
engineConfig::ParsingResult EngineBase::loadAudioPolicyEngineConfig()
{
    auto loadProductStrategies =
            [](auto& strategyConfigs, auto& productStrategies, auto& volumeGroups) {
        for (auto& strategyConfig : strategyConfigs) {
            sp<ProductStrategy> strategy = new ProductStrategy(strategyConfig.name);
            for (const auto &group : strategyConfig.attributesGroups) {
                const auto &iter = std::find_if(begin(volumeGroups), end(volumeGroups),
                                                 [&group](const auto &volumeGroup) {
                            return group.volumeGroup == volumeGroup.second->getName(); });
                ALOG_ASSERT(iter != end(volumeGroups), "Invalid Volume Group Name %s",
                                group.volumeGroup.c_str());
                if (group.stream != AUDIO_STREAM_DEFAULT) {
                    iter->second->addSupportedStream(group.stream);      // <-- NULL deref site
                }
                for (const auto &attr : group.attributesVect) {
                    strategy->addAttributes({group.stream, iter->second->getId(), attr});
                    iter->second->addSupportedAttributes(attr);          // <-- NULL deref site
                }
            }
            product_strategy_t strategyId = strategy->getId();
            productStrategies[strategyId] = strategy;
        }
    };

    auto loadVolumeGroups = [](auto &volumeConfigs, auto &volumeGroups) {
        for (auto &volumeConfig : volumeConfigs) {
            sp<VolumeGroup> volumeGroup = new VolumeGroup(volumeConfig.name,
                                                          volumeConfig.indexMin,
                                                          volumeConfig.indexMax);
            volumeGroups[volumeGroup->getId()] = volumeGroup;
            for (auto &configCurve : volumeConfig.volumeCurves) {
                device_category deviceCat = DEVICE_CATEGORY_SPEAKER;
                if (!DeviceCategoryConverter::fromString(configCurve.deviceCategory, deviceCat)) {
                    ALOGE("%s: Invalid %s", __FUNCTION__, configCurve.deviceCategory.c_str());
                    continue;
                }
                sp<VolumeCurve> curve = new VolumeCurve(deviceCat);
                for (auto &point : configCurve.curvePoints) {
                    curve->add({point.index, point.attenuationInMb});
                }
                volumeGroup->add(curve);
            }
        }
    };

    auto result = engineConfig::parse();
    if (result.parsedConfig == nullptr) {
        ALOGW("%s: No configuration found, using default matching phone experience.",
              __FUNCTION__);
        engineConfig::Config config = gDefaultEngineConfig;
        android::status_t ret = engineConfig::parseLegacyVolumes(config.volumeGroups);
        result = {std::make_unique<engineConfig::Config>(config),
                  static_cast<size_t>(ret == NO_ERROR ? 0 : 1)};
    }
    ALOGE_IF(result.nbSkippedElement != 0, "skipped %zu elements", result.nbSkippedElement);
    loadVolumeGroups(result.parsedConfig->volumeGroups, mVolumeGroups);
    loadProductStrategies(result.parsedConfig->productStrategies, mProductStrategies,
                          mVolumeGroups);
    mProductStrategies.initialize();
    return result;
}
```

### 1.2 `mVolumeGroups` is a map of `sp<VolumeGroup>`

[`VolumeGroup.h`](https://android.googlesource.com/platform/frameworks/av/+/refs/tags/android-10.0.0_r1/services/audiopolicy/engine/common/include/VolumeGroup.h):

```cpp
class VolumeGroupMap : public std::map<volume_group_t, sp<VolumeGroup>>
{
public:
    void dump(String8 *dst, int spaces = 0) const;
};
```

So `iter->second` is a `sp<VolumeGroup>`. When `find_if` over an **empty** map returns
`end()`, `iter->second` is a garbage/null `sp<VolumeGroup>`; `iter->second->addSupportedStream()`
dereferences its `m_ptr`. With `m_ptr == 0`, a virtual/member access faults at **address 0x0**
— exactly the tombstone signature (`fault addr 0x0`, `x1 == 0`, "Cause: null pointer dereference").

> Note on the `ALOG_ASSERT`: AOSP's `ALOG_ASSERT(iter != end, "Invalid Volume Group Name %s", ...)`
> immediately precedes the dereference, and on a canonical AOSP userdebug build it would raise
> `SIGABRT`. The observed tombstone is a `SIGSEGV @ 0x0` whose **frame #00 is
> `loadAudioPolicyEngineConfig()+2340` itself** (not `__android_log_assert`/`abort`), so in this
> LineageOS binary the invalid `sp<VolumeGroup>` dereference is what actually executed. Either way,
> the trigger is identical: `mVolumeGroups` is empty.

### 1.3 The fallback default config has **empty** `volumeGroups`

[`EngineDefaultConfig.h`](https://android.googlesource.com/platform/frameworks/av/+/refs/tags/android-10.0.0_r1/services/audiopolicy/engine/common/src/EngineDefaultConfig.h):

```cpp
const engineConfig::Config gDefaultEngineConfig = {
    1.0,
    gOrderedStrategies,   // productStrategies — NON-empty (STRATEGY_PHONE, STRATEGY_MEDIA, …)
    {},                    // criteria — empty
    {},                    // criteriaTypes — empty
    {}                     // volumeGroups — EMPTY  <-- must be filled from <volumes>
};
```

`gOrderedStrategies`'s `attributesGroups[].volumeGroup` fields are **stream-type literals**, e.g.
`"AUDIO_STREAM_VOICE_CALL"`, `"AUDIO_STREAM_BLUETOOTH_SCO"`, `"AUDIO_STREAM_RING"`,
`"AUDIO_STREAM_ALARM"`, `"AUDIO_STREAM_MUSIC"`, `"AUDIO_STREAM_SYSTEM"`, etc. Those names must be
produced by `parseLegacyVolumes()` from `<volume stream="AUDIO_STREAM_…">` entries.

---

## 2. Is the XML found? What paths does Android 10 search?

There are **two different consumers** of `audio_policy_configuration.xml`, with different paths.

### 2.1 The policy **engine** (this crash) — two files

[`EngineConfig.h`](https://android.googlesource.com/platform/frameworks/av/+/refs/tags/android-10.0.0_r1/services/audiopolicy/engine/config/include/EngineConfig.h):

```cpp
/** Default path of audio policy usages configuration file. */
constexpr char DEFAULT_PATH[] = "/vendor/etc/audio_policy_engine_configuration.xml";

/** Directories where the effect libraries will be searched for. */
constexpr const char* POLICY_USAGE_LIBRARY_PATH[] = {"/odm/etc/", "/vendor/etc/", "/system/etc/"};
```

[`EngineConfig.cpp`](https://android.googlesource.com/platform/frameworks/av/+/refs/tags/android-10.0.0_r1/services/audiopolicy/engine/config/src/EngineConfig.cpp):

```cpp
static const char *kConfigLocationList[] = {"/odm/etc", "/vendor/etc", "/system/etc"};
static const int kConfigLocationListSize =
        (sizeof(kConfigLocationList) / sizeof(kConfigLocationList[0]));
...
static constexpr const char *apmXmlConfigFileName = "audio_policy_configuration.xml";
```

So the engine tries, in order:

1. `engineConfig::parse()` → **`/vendor/etc/audio_policy_engine_configuration.xml`** (the *new* engine
   config; normally absent) → returns `{nullptr, 0}`.
2. Fallback `parseLegacyVolumes()` → **`/odm/etc/audio_policy_configuration.xml`**,
   **`/vendor/etc/audio_policy_configuration.xml`**, **`/system/etc/audio_policy_configuration.xml`**,
   reading only the legacy **`<volumes>`** section.

### 2.2 The audio-policy **manager** (modules/ports/routes — the part your XML targets)

`AudioPolicyManager`/`Serializer` load `audio_policy_configuration.xml` from
**`/vendor/etc/audio_policy_configuration.xml`** (vendor config) with fallback to
**`/system/etc/audio_policy_configuration.xml`** (and `/odm/etc` in the fallback lists).

### 2.3 Non-Treble implication — yes, the path can be wrong

Your file currently lives at **`/system/vendor/etc/audio_policy_configuration.xml`**.
None of the searched directories is `/system/vendor/etc`. It is reachable as
`/vendor/etc/…` **only if `/vendor` is a symlink to `/system/vendor`**.

- If `/vendor → /system/vendor` exists (common on LineageOS legacy/non-Treble builds), then
  `/vendor/etc/audio_policy_configuration.xml` resolves to your file → the file **is** found,
  but it still has no `<volumes>` → the engine still crashes.
- If the `/vendor` symlink is missing/broken (also seen on some legacy ports), the file is **not
  found at all**, which produces the same result (empty `mVolumeGroups`).

Either way the crash is the same; the *fix* must therefore do **both**: place the file at a searched
path (via the `/vendor` symlink or by shipping it at `/vendor/etc` or `/system/etc`) **and** add the
missing engine sections.

---

## 3. Every bug in the current `audio_policy_configuration.xml`

The current file (117 lines) is a clean **modules-only** config. Bugs ranked by severity:

1. **FATAL — missing `<volumes>` section (this is the crash).**
   The engine has no volume groups. The legacy `<volumes>` table (or a separate
   `audio_policy_engine_configuration.xml` with `<volumeGroups>`/`<productStrategies>`) is mandatory
   when `audio_policy_engine_configuration.xml` is absent. The AOSP reference file documents this:

   ```xml
   <!-- Volume section:
        IMPORTANT NOTE: Volume tables have been moved to engine configuration.
                        Keep it here for legacy.
                        Engine will fallback on these files if none are provided by engine. -->
   <xi:include href="audio_policy_volumes.xml"/>
   <xi:include href="default_volume_tables.xml"/>
   ```

2. **File not on a searched path (contributing).**
   It sits at `/system/vendor/etc/`; the engine/APM search `/odm/etc`, `/vendor/etc`, `/system/etc`.
   Works only if `/vendor → /system/vendor`; otherwise invisible to audioserver.

3. **`halVersion="2.0"`** — accepted by the parser (valid values are `"2.0"`/`"3.0"`), so it is
   **not** the crash cause; but verify it matches the actual `audio.primary.msm8916` HAL version or
   you will fail later at HAL open time. Not related to this SIGSEGV.

4. **`<attachedDevices>` placement** — the task hint mentions "missing `<attachedDevices>` in
   globalConfiguration". That is a red herring: `<attachedDevices>` is a **`<module>`** child, not a
   `<globalConfiguration>` child. Your `<module name="primary">` already has a correct
   `<attachedDevices>`; `<globalConfiguration speaker_drc_enabled="false"/>` is complete.

5. **`role`/`flags` strings** — `role="source"|"sink"` and `flags="AUDIO_OUTPUT_FLAG_PRIMARY|FAST"`
   are correct. No bug here.

6. **a2dp/usb/r_submix** — present and correctly named (`a2dp`, `usb`, `r_submix`), with valid
   device ports and routes. They are *dynamic* modules, so omitting their `<attachedDevices>` and
   `<defaultOutputDevice>` is correct. (Cosmetic: A2DP could also declare
   `AUDIO_DEVICE_OUT_BLUETOOTH_A2DP_HEADPHONES/_SPEAKER`, but `AUDIO_DEVICE_OUT_BLUETOOTH_A2DP`
   alone is sufficient for basic function.)

**Net:** the only defect that matters for *this* crash is **#1 (missing `<volumes>`)**,
compounded by **#2 (path)**.

---

## 4. Ranked fixes

### Fix 1 (required, fixes the crash): add a `<volumes>` table

Add a self-contained `<volumes>` block as a **direct child of `<audioPolicyConfiguration>`**
(after `</modules>`). It must define at least one `<volume>` for **every** stream the default
product strategies reference, i.e. these 13 `stream` names:

`AUDIO_STREAM_VOICE_CALL`, `AUDIO_STREAM_BLUETOOTH_SCO`, `AUDIO_STREAM_RING`,
`AUDIO_STREAM_ALARM`, `AUDIO_STREAM_ENFORCED_AUDIBLE`, `AUDIO_STREAM_ACCESSIBILITY`,
`AUDIO_STREAM_NOTIFICATION`, `AUDIO_STREAM_MUSIC`, `AUDIO_STREAM_SYSTEM`, `AUDIO_STREAM_DTMF`,
`AUDIO_STREAM_TTS`, `AUDIO_STREAM_REROUTING`, `AUDIO_STREAM_PATCH`.

Use **inline `<point>` curves** (no `ref=`) so the file is self-contained (the referenced
`default_volume_tables.xml` is not present on this device). Minimal valid example:

```xml
    <volumes>
        <volume stream="AUDIO_STREAM_VOICE_CALL" deviceCategory="DEVICE_CATEGORY_EARPIECE">
            <point>0,-4000</point><point>100,0</point>
        </volume>
        <volume stream="AUDIO_STREAM_VOICE_CALL" deviceCategory="DEVICE_CATEGORY_SPEAKER">
            <point>0,-2400</point><point>100,0</point>
        </volume>
        <volume stream="AUDIO_STREAM_VOICE_CALL" deviceCategory="DEVICE_CATEGORY_HEADSET">
            <point>0,-4200</point><point>100,0</point>
        </volume>

        <volume stream="AUDIO_STREAM_BLUETOOTH_SCO" deviceCategory="DEVICE_CATEGORY_SPEAKER">
            <point>0,-2400</point><point>100,0</point>
        </volume>
        <volume stream="AUDIO_STREAM_BLUETOOTH_SCO" deviceCategory="DEVICE_CATEGORY_HEADSET">
            <point>0,-4200</point><point>100,0</point>
        </volume>

        <volume stream="AUDIO_STREAM_RING" deviceCategory="DEVICE_CATEGORY_SPEAKER">
            <point>0,-2970</point><point>100,0</point>
        </volume>
        <volume stream="AUDIO_STREAM_RING" deviceCategory="DEVICE_CATEGORY_HEADSET">
            <point>0,-2970</point><point>100,0</point>
        </volume>

        <volume stream="AUDIO_STREAM_ALARM" deviceCategory="DEVICE_CATEGORY_SPEAKER">
            <point>0,-2970</point><point>100,0</point>
        </volume>
        <volume stream="AUDIO_STREAM_ALARM" deviceCategory="DEVICE_CATEGORY_HEADSET">
            <point>0,-2970</point><point>100,0</point>
        </volume>

        <volume stream="AUDIO_STREAM_ENFORCED_AUDIBLE" deviceCategory="DEVICE_CATEGORY_SPEAKER">
            <point>1,-3000</point><point>100,-1800</point>
        </volume>
        <volume stream="AUDIO_STREAM_ENFORCED_AUDIBLE" deviceCategory="DEVICE_CATEGORY_HEADSET">
            <point>1,-3000</point><point>100,-1800</point>
        </volume>

        <volume stream="AUDIO_STREAM_ACCESSIBILITY" deviceCategory="DEVICE_CATEGORY_SPEAKER">
            <point>0,-4000</point><point>100,0</point>
        </volume>
        <volume stream="AUDIO_STREAM_ACCESSIBILITY" deviceCategory="DEVICE_CATEGORY_HEADSET">
            <point>0,-4000</point><point>100,0</point>
        </volume>

        <volume stream="AUDIO_STREAM_NOTIFICATION" deviceCategory="DEVICE_CATEGORY_SPEAKER">
            <point>1,-2970</point><point>100,0</point>
        </volume>
        <volume stream="AUDIO_STREAM_NOTIFICATION" deviceCategory="DEVICE_CATEGORY_HEADSET">
            <point>1,-2970</point><point>100,0</point>
        </volume>

        <volume stream="AUDIO_STREAM_MUSIC" deviceCategory="DEVICE_CATEGORY_SPEAKER">
            <point>0,-4000</point><point>100,0</point>
        </volume>
        <volume stream="AUDIO_STREAM_MUSIC" deviceCategory="DEVICE_CATEGORY_HEADSET">
            <point>0,-4000</point><point>100,0</point>
        </volume>

        <volume stream="AUDIO_STREAM_SYSTEM" deviceCategory="DEVICE_CATEGORY_SPEAKER">
            <point>1,-3000</point><point>100,-1800</point>
        </volume>
        <volume stream="AUDIO_STREAM_SYSTEM" deviceCategory="DEVICE_CATEGORY_HEADSET">
            <point>1,-3000</point><point>100,-1800</point>
        </volume>

        <volume stream="AUDIO_STREAM_DTMF" deviceCategory="DEVICE_CATEGORY_SPEAKER">
            <point>0,-2400</point><point>100,0</point>
        </volume>
        <volume stream="AUDIO_STREAM_DTMF" deviceCategory="DEVICE_CATEGORY_HEADSET">
            <point>0,-2400</point><point>100,0</point>
        </volume>

        <volume stream="AUDIO_STREAM_TTS" deviceCategory="DEVICE_CATEGORY_SPEAKER">
            <point>0,-4000</point><point>100,0</point>
        </volume>
        <volume stream="AUDIO_STREAM_TTS" deviceCategory="DEVICE_CATEGORY_HEADSET">
            <point>0,-4000</point><point>100,0</point>
        </volume>

        <volume stream="AUDIO_STREAM_REROUTING" deviceCategory="DEVICE_CATEGORY_SPEAKER">
            <point>0,-4000</point><point>100,0</point>
        </volume>
        <volume stream="AUDIO_STREAM_REROUTING" deviceCategory="DEVICE_CATEGORY_HEADSET">
            <point>0,-4000</point><point>100,0</point>
        </volume>

        <volume stream="AUDIO_STREAM_PATCH" deviceCategory="DEVICE_CATEGORY_SPEAKER">
            <point>0,-4000</point><point>100,0</point>
        </volume>
        <volume stream="AUDIO_STREAM_PATCH" deviceCategory="DEVICE_CATEGORY_HEADSET">
            <point>0,-4000</point><point>100,0</point>
        </volume>
    </volumes>
```

The curves above are only placeholders; the values are irrelevant to the crash. You may instead
copy the real tables from AOSP's [`audio_policy_volumes.xml`](https://android.googlesource.com/platform/frameworks/av/+/refs/tags/android-10.0.0_r1/services/audiopolicy/config/audio_policy_volumes.xml) and
[`default_volume_tables.xml`](https://android.googlesource.com/platform/frameworks/av/+/refs/tags/android-10.0.0_r1/services/audiopolicy/config/default_volume_tables.xml)
and `<xi:include>` them (that matches the AOSP reference exactly), but only if you also ship both
files next to the main config.

### Fix 2 (required): make the file reachable at a searched path

- Confirm `/vendor` is a symlink to `/system/vendor` (`ls -l /vendor`), or
- ship/copy the XML to **`/vendor/etc/audio_policy_configuration.xml`** (or `/system/etc/...`).

Without this, `parseLegacyVolumes()` (engine) and the APM loader can't read the file at all.

### Fix 3 (alternative / more correct): provide `/vendor/etc/audio_policy_engine_configuration.xml`

The "proper" Android 10 engine config is a separate file with `<volumeGroups>`, `<productStrategies>`,
`<criteria>`, `<criteria_types>`. If you ship it, the engine uses it directly and the crash goes
away even without `<volumes>` in the main XML. This is more work; Fix 1 + Fix 2 is the smallest change.

### Fix 4 (secondary, not this crash): confirm `halVersion`

Keep `halVersion="2.0"` only if `audio.primary.msm8916` reports HAL 2.0; otherwise use the matching
version. This affects HAL open, not `loadAudioPolicyEngineConfig()`.

---

## Appendix — source references

- `EngineBase::loadAudioPolicyEngineConfig()`: `services/audiopolicy/engine/common/src/EngineBase.cpp`
- engine config parser (`parse`, `parseLegacyVolumes`, `kConfigLocationList`): `services/audiopolicy/engine/config/src/EngineConfig.cpp`
- engine config paths (`DEFAULT_PATH`, `POLICY_USAGE_LIBRARY_PATH`): `services/audiopolicy/engine/config/include/EngineConfig.h`
- default engine config (empty `volumeGroups`): `services/audiopolicy/engine/common/src/EngineDefaultConfig.h`
- `VolumeGroupMap` (`std::map<volume_group_t, sp<VolumeGroup>>`): `services/audiopolicy/engine/common/include/VolumeGroup.h`
- `Engine::Engine()` calling `loadAudioPolicyEngineConfig()`: `services/audiopolicy/enginedefault/src/Engine.cpp`
- AOSP reference config with the "Volume tables moved to engine" note: `services/audiopolicy/config/audio_policy_configuration.xml`
- AOSP legacy volume table: `services/audiopolicy/config/audio_policy_volumes.xml`

All URLs use `https://android.googlesource.com/platform/frameworks_av/+/refs/tags/android-10.0.0_r1/…`.
