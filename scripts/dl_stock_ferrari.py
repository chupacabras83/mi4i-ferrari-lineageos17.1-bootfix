import urllib.request, sys

urls = [
    'https://bigota.d.miui.com/V6.6.10.0.LXIMICF/ferrari_global_images_V6.6.10.0.LXIMICF_20150626.0000.4_5.0_global_52e9660609.tgz',
    'https://bigota.d.miui.com/V6.6.10.0.LXIMICF/miui_MI4iGlobal_V6.6.10.0.LXIMICF_80f20c0908_5.0.zip',
]
out = r'C:\Users\iMac2019\mi4i-flash\stock-ferrari.dl'

for url in urls:
    print('TRYING:', url, flush=True)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            total = int(r.headers.get('Content-Length', 0) or 0)
            print('  HTTP OK, size =', total, flush=True)
            if total == 0 or total > 4*1024*1024*1024:
                print('  (size suspicious, skipping)', flush=True)
                continue
            done = 0
            with open(out, 'wb') as f:
                while True:
                    chunk = r.read(1024*1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        print('  %.1f%% (%d / %d)' % (100.0*done/total, done, total), flush=True)
            print('DOWNLOAD DONE ->', out, '(%d bytes)' % done, flush=True)
            sys.exit(0)
    except Exception as e:
        print('  ERR:', e, flush=True)
print('ALL URLS FAILED', flush=True)
