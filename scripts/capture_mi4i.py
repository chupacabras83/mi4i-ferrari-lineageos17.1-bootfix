import subprocess, time, os

adb = r'C:\Users\iMac2019\AppData\Local\Android\Sdk\platform-tools\adb.exe'
out = r'E:\Users\Ninja hp LAPTOP\Documents\deepseek-harness\default-workspace\analysis\mi4i-boot'
os.makedirs(out, exist_ok=True)

def run(args, timeout=15):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return (p.stdout or '') + (p.stderr or '')
    except Exception as e:
        return 'ERR ' + str(e)

t0 = time.time()
det = False
while time.time() - t0 < 300:
    o = run([adb, 'devices'])
    if '\tdevice' in o:
        det = True
        print('DEVICE at %.0fs' % (time.time()-t0), flush=True)
        break
    time.sleep(3)

if not det:
    print('NO DEVICE within 5 min', flush=True)
    raise SystemExit(0)

open(os.path.join(out, 'dmesg.txt'), 'w').write(run([adb, 'shell', 'dmesg']))
# capture logcat several times over 4 min (audioserver crash + boot state)
end = time.time() + 240
i = 0
while time.time() < end:
    i += 1
    bc = run([adb, 'shell', 'getprop sys.boot_completed']).strip()
    print('[%.0fs] boot_completed=%s' % (time.time()-t0, bc), flush=True)
    open(os.path.join(out, 'logcat_%02d.txt' % i), 'w').write(run([adb, 'logcat', '-b', 'all', '-d']))
    time.sleep(20)
print('DONE', flush=True)
