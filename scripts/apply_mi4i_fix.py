import subprocess, time, os, sys

adb = r'C:\Users\iMac2019\AppData\Local\Android\Sdk\platform-tools\adb.exe'
xml = r'E:\Users\Ninja hp LAPTOP\Documents\deepseek-harness\default-workspace\analysis\mi4i-audio-policy-fixed.xml'

def run(args, timeout=30):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return (p.stdout or '') + (p.stderr or '')
    except Exception as e:
        return 'ERR ' + str(e)

# wait for adb recovery (TWRP) up to 5 min
t0 = time.time()
while time.time() - t0 < 300:
    o = run([adb, 'get-state'])
    if 'recovery' in o or 'device' in o:
        print('ADB STATE:', o.strip(), flush=True)
        break
    time.sleep(3)
else:
    print('NO ADB within 5 min', flush=True)
    sys.exit(1)

# mount system_root
print(run([adb, 'shell', 'mkdir -p /system_root; mount -t ext4 /dev/block/mmcblk0p34 /system_root']), flush=True)

# push the fixed XML to BOTH searched paths
for dest in ['/system_root/system/etc/audio_policy_configuration.xml',
             '/system_root/system/vendor/etc/audio_policy_configuration.xml']:
    r = run([adb, 'push', xml, dest])
    print('push ->', dest, ':', 'pushed' if 'pushed' in r else r.strip(), flush=True)
    run([adb, 'shell', 'chmod 0644 "%s"; chcon u:object_r:vendor_configs_file:s0 "%s" 2>/dev/null' % (dest, dest)])

# verify the pushed content has <volumes>
v = run([adb, 'shell', 'grep -c "AUDIO_STREAM_" /system_root/system/etc/audio_policy_configuration.xml'])
print('volume entries at /system/etc:', v.strip(), flush=True)

# check /vendor symlink
print(run([adb, 'shell', 'ls -la /vendor 2>&1 | head -3']), flush=True)

print('FIX APPLIED. Now reboot:', flush=True)
print(run([adb, 'reboot']), flush=True)
print('DONE', flush=True)
