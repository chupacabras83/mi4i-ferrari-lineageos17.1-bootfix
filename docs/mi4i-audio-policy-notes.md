# Mi 4i (ferrari) — audio_policy_configuration.xml fix notes

## TL;DR

The boot-time `audioserver` crash (`SIGSEGV` null-deref in
`libaudiopolicyenginedefault.so EngineBase::loadAudioPolicyEngineConfig()`) is **not**
caused by a malformed `<modules>` tree. It is caused by a **missing/incomplete
`<volumes>` section** in `audio_policy_configuration.xml`. The fixed file is
`mi4i-audio-policy-fixed.xml`.

---

## 1. Root cause (why the engine loader null-derefs)

Trace (Android 10, `frameworks/av/services/audiopolicy/engine/`):

1. `Engine::Engine()` → `EngineBase::loadAudioPolicyEngineConfig()`.
2. It calls `engineConfig::parse()` which reads
   **`/vendor/etc/audio_policy_engine_configuration.xml`** (hard-coded path).
3. On this **non-Treble** device that file is absent, so `parse()` returns
   `parsedConfig == nullptr` and the code falls back to the built-in default config
   (`gDefaultEngineConfig`) **plus** `engineConfig::parseLegacyVolumes()`.
4. `parseLegacyVolumes()` searches `/odm/etc`, `/vendor/etc`, `/system/etc` for
   **`audio_policy_configuration.xml`** and parses its **`<volumes>`** section. Each
   `<volume stream="AUDIO_STREAM_X" ...>` becomes one VolumeGroup named `AUDIO_STREAM_X`.
5. `loadProductStrategies()` then iterates the default product strategies. Every
   strategy's `AttributesGroup` references a volume group **by name**
   (`AUDIO_STREAM_VOICE_CALL`, `AUDIO_STREAM_MUSIC`, … `AUDIO_STREAM_PATCH`), and the
   code does `iter->second->addSupportedStream(...)` **without checking** whether the
   lookup succeeded:
   ```cpp
   const auto &iter = std::find_if(... volumeGroup name match ...);
   ALOG_ASSERT(iter != end(volumeGroups), "Invalid Volume Group Name %s", ...);
   if (group.stream != AUDIO_STREAM_DEFAULT) {
       iter->second->addSupportedStream(group.stream);   // <-- end() deref -> SIGSEGV
   }
   ```
6. If `<volumes>` is missing (the "current broken" XML) or missing some stream (the
   "fuller" XML omitted `AUDIO_STREAM_REROUTING` and `AUDIO_STREAM_PATCH`), the lookup
   returns `end()` and `iter->second` dereferences a null `sp<>` → the observed crash.

**Fix:** provide a `<volumes>` section containing **every** stream type the default
strategies reference — all 13 Android 10 public stream types:
`VOICE_CALL`, `SYSTEM`, `RING`, `MUSIC`, `ALARM`, `NOTIFICATION`, `BLUETOOTH_SCO`,
`ENFORCED_AUDIBLE`, `DTMF`, `TTS`, `ACCESSIBILITY`, **`REROUTING`**, **`PATCH`**.

---

## 2. halVersion for the primary module

Use **`halVersion="2.0"`**.

- The Android 10 schema (`audio/5.0/config/audio_policy_configuration.xsd`) only
  enumerates `2.0` and `3.0`; **`1.0` is not a legal value**.
- `2.0` = the legacy `audio_hw_device_t` HAL (what `audio.primary.msm8916` implements).
- `3.0` = the HIDL-wrapped audio HAL (Audio HAL 4.0+). The AOSP *reference*
  `audio_policy_configuration.xml` uses `3.0` because it targets new HIDL devices;
  that is wrong for ferrari.
- The policy also uses `getModuleVersionMajor() < 3` to select legacy routing for the
  phone strategy; `2.0` keeps that correct.

---

## 3. Changes vs the "current broken" XML (workspace root file)

| # | Change | Why it matters |
|---|--------|----------------|
| 1 | Added a complete **`<volumes>`** section (13 streams × HEADSET/SPEAKER + VOICE_CALL EARPIECE) | This is the actual crash fix (see §1). The broken file had **no** `<volumes>` at all. |
| 2 | Expanded primary `<attachedDevices>` from `{Earpiece, Speaker}` to also include `Built-In Mic`, `Back Mic`, `Voice Call`, `FM Tuner` | Matches the legacy `attached_input_devices`; these are permanently-present inputs the policy must treat as always available. |
| 3 | Added `compress_offload` and `voip_rx` mixPorts + routes | The legacy `.conf` defines them and the HAL supports them; dropping them breaks offload playback and VoIP. |
| 4 | Split multi-format legacy lines into **one `<profile>` per format** (e.g. `AUDIO_FORMAT_MP3`, `AUDIO_FORMAT_AAC_LC`, …) and dropped the `*_OFFLOAD` pseudo-formats | The XML `format` attribute is a single enum (no `\|` lists). `AUDIO_FORMAT_PCM_16_BIT_OFFLOAD` / `_24_BIT_OFFLOAD` are not in the schema's `audioFormat` list. |
| 5 | Added `Remote Submix In` to the `r_submix` module's `<attachedDevices>` | Matches AOSP reference and the legacy `attached_input_devices` (REMOTE_SUBMIX). |
| 6 | Dropped `xmlns:xi="http://www.w3.org/2001/XInclude"` | Nothing is XIncluded (all modules are inlined), so the namespace is unnecessary. |

Everything else (structure, `tagName`-based `attachedDevices`, concrete device types,
routes, `defaultOutputDevice=Speaker`) was already correct in that file and is kept.

---

## 4. Bugs in the "fuller" XML (the 210-line file) — avoided here

1. **Enum-string bug that would abort the platform-config load:** it used
   `type="AUDIO_DEVICE_OUT_ALL_SCO"` and `type="AUDIO_DEVICE_OUT_ALL_A2DP"` for the
   BT SCO and A2DP device ports. Those are bitmask **aliases**, not enum values:
   `deviceFromString()` cannot resolve them, so `DevicePortTraits::deserialize()`
   returns `BAD_VALUE` and `loadConfig()` fails. Fixed to
   `AUDIO_DEVICE_OUT_BLUETOOTH_SCO` / `AUDIO_DEVICE_OUT_BLUETOOTH_A2DP`.
2. **Invalid `<globalConfiguration>`:** it used
   `speaker_driver_status_dummy_device="false"` (unknown attribute) and nested
   `<attachedDevices>`/`<defaultOutputDevice>` children inside `<globalConfiguration>`.
   The schema requires the `speaker_drc_enabled` attribute and no children.
3. **Incomplete `<volumes>`:** missing `AUDIO_STREAM_REROUTING` and `AUDIO_STREAM_PATCH`.
4. **Pipe-separated formats** (`format="AUDIO_FORMAT_MP3|AUDIO_FORMAT_AAC_LC|..."`) are
   not split by the runtime `formatFromString()`, so they degrade to "dynamic format"
   and are invalid against the schema. One format per profile is used instead.

---

## 5. Faithful device conversion (audio_policy.conf → XML)

| Legacy `.conf` device | XML devicePort (`tagName` / `type`) |
|----------------------|--------------------------------------|
| `AUDIO_DEVICE_OUT_EARPIECE` | `Earpiece` / `AUDIO_DEVICE_OUT_EARPIECE` |
| `AUDIO_DEVICE_OUT_SPEAKER` | `Speaker` / `AUDIO_DEVICE_OUT_SPEAKER` |
| `AUDIO_DEVICE_OUT_WIRED_HEADSET` | `Wired Headset` / `AUDIO_DEVICE_OUT_WIRED_HEADSET` |
| `AUDIO_DEVICE_OUT_WIRED_HEADPHONE` | `Wired Headphone` / `AUDIO_DEVICE_OUT_WIRED_HEADPHONE` |
| `AUDIO_DEVICE_OUT_LINE` | `Line Out` / `AUDIO_DEVICE_OUT_LINE` |
| `AUDIO_DEVICE_OUT_ALL_SCO` | `BT SCO` / `AUDIO_DEVICE_OUT_BLUETOOTH_SCO` |
| `AUDIO_DEVICE_OUT_PROXY` | `Proxy` / `AUDIO_DEVICE_OUT_PROXY` |
| `AUDIO_DEVICE_OUT_AUX_DIGITAL` | `Aux Digital` / `AUDIO_DEVICE_OUT_AUX_DIGITAL` |
| `AUDIO_DEVICE_OUT_ANLG_DOCK_HEADSET` | `Dock Headset` / `AUDIO_DEVICE_OUT_ANLG_DOCK_HEADSET` |
| `AUDIO_DEVICE_OUT_FM` | `FM` / `AUDIO_DEVICE_OUT_FM` |
| `AUDIO_DEVICE_IN_BUILTIN_MIC` | `Built-In Mic` / `AUDIO_DEVICE_IN_BUILTIN_MIC` |
| `AUDIO_DEVICE_IN_WIRED_HEADSET` | `Wired Headset Mic` / `AUDIO_DEVICE_IN_WIRED_HEADSET` |
| `AUDIO_DEVICE_IN_BLUETOOTH_SCO_HEADSET` | `BT SCO Headset Mic` / `AUDIO_DEVICE_IN_BLUETOOTH_SCO_HEADSET` |
| `AUDIO_DEVICE_IN_BACK_MIC` | `Back Mic` / `AUDIO_DEVICE_IN_BACK_MIC` |
| `AUDIO_DEVICE_IN_ANLG_DOCK_HEADSET` | `Dock Headset Mic` / `AUDIO_DEVICE_IN_ANLG_DOCK_HEADSET` |
| `AUDIO_DEVICE_IN_VOICE_CALL` | `Voice Call` / `AUDIO_DEVICE_IN_VOICE_CALL` |
| `AUDIO_DEVICE_IN_FM_TUNER` | `FM Tuner` / `AUDIO_DEVICE_IN_FM_TUNER` |
| `AUDIO_DEVICE_OUT_REMOTE_SUBMIX` / `_IN_` | `r_submix` module ports (Remote Submix Out/In) |
| `AUDIO_DEVICE_OUT_USB_ACCESSORY` / `_DEVICE_` / `AUDIO_DEVICE_IN_USB_DEVICE` | `usb` module ports |

Legacy `global_configuration` also listed `AUDIO_DEVICE_OUT_TELEPHONY_TX` /
`AUDIO_DEVICE_IN_TELEPHONY_RX`; these modem loopback pseudo-devices are intentionally
**not** declared (no `voice_tx`/`voice_rx` mixPorts exist in the `.conf`), which keeps
the engine on the legacy primary-input/output voice path — the correct behavior for
this pre-telephony-TX HAL.

---

## 6. Verification

- XML is well-formed (balanced tags); validated with `[xml]` (System.Xml).
- Root `version="1.0"` matches the parser's expected `1.0`.
- Every `<route>` sink/source refers to a declared mixPort `name` or devicePort `tagName`.
- Every `<attachedDevices>/<item>` and `<defaultOutputDevice>` refers to a declared
  devicePort `tagName` in the same module.
- All device `type` values are concrete `AUDIO_DEVICE_*` enum names (no `*_ALL_*` masks).
- `<volumes>` contains all 13 stream types; `<reference>` names resolve.
