import subprocess, time

adb = r'C:\Users\iMac2019\AppData\Local\Android\Sdk\platform-tools\adb.exe'
fb = r'C:\Users\iMac2019\AppData\Local\Android\Sdk\platform-tools\fastboot.exe'
twrp = r'C:\Users\iMac2019\mi4i-flash\twrp-3.7.0_9-0-ferrari.img'

def run(args, timeout=15):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return (p.stdout or '') + (p.stderr or '')
    except Exception:
        return ''

print('MI4I MONITOR: polling for device (adb or fastboot)...', flush=True)
t0 = time.time()
while time.time() - t0 < 43200:  # 12 hours
    fbout = run([fb, 'devices'])
    if 'fastboot' in fbout:
        print('FASTBOOT DETECTED:', fbout.strip(), flush=True)
        print('booting TWRP...', flush=True)
        r = run([fb, 'boot', twrp], timeout=120)
        print('boot result:', r.strip()[-200:], flush=True)
        print('DONE (fastboot->twrp)', flush=True)
        raise SystemExit(0)
    adbout = run([adb, 'devices'])
    if '\tdevice' in adbout or '\trecovery' in adbout:
        print('ADB AUTHORIZED:', adbout.strip(), flush=True)
        raise SystemExit(0)
    elif '\tunauthorized' in adbout:
        print('ADB unauthorized (watching for authorization/fastboot)...', flush=True)
    time.sleep(5)
print('MONITOR TIMEOUT (12h)', flush=True)
