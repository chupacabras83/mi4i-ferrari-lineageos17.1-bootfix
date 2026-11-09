import urllib.request, ssl, hashlib, os, re, time, sys

DEST_DIR = r"C:\Users\iMac2019\mi4i-flash"
UA = "Wget/1.21"

PIX_URL = "https://archive.org/download/afharchive_356_pixysos-v24-ferrari-unofficial-20200711-100341zip/PixysOS-v2.4-ferrari-UNOFFICIAL-20200711-100341.zip"
PIX_MD5 = "a6e48721313064f98ca1d30603b7b8f8"

G9_URL = "https://sourceforge.net/projects/opengapps/files/arm64/20220503/open_gapps-arm64-9.0-pico-20220503.zip/download"
G9_MD5_URL = "https://sourceforge.net/projects/opengapps/files/arm64/20220503/open_gapps-arm64-9.0-pico-20220503.zip.md5/download"


def log(msg):
    print(msg, flush=True)


def fetch_md5_from_sf(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        data = urllib.request.urlopen(req, timeout=60, context=ssl.create_default_context()).read().decode("utf-8", "ignore")
        m = re.search(r"[0-9a-fA-F]{32}", data)
        return m.group(0).lower() if m else None
    except Exception as e:
        log("  WARN could not fetch md5: %s %s" % (type(e).__name__, e))
        return None


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().lower()


def download(url, dest):
    """Download url to dest, resuming from dest.part if present. Returns final size."""
    part = dest + ".part"
    existing = os.path.getsize(part) if os.path.exists(part) else 0
    headers = {"User-Agent": UA}
    if existing > 0:
        headers["Range"] = "bytes=%d-" % existing
    ctx = ssl.create_default_context()
    r = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60, context=ctx)
    if existing > 0 and r.status != 206:
        # server ignored Range; start fresh
        r.close()
        existing = 0
        r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60, context=ctx)
    clen = int(r.headers.get("Content-Length") or 0)
    total = existing + clen
    mode = "ab" if existing > 0 else "wb"
    done = existing
    last_report = 0
    start = time.time()
    with open(part, mode) as f:
        while True:
            chunk = r.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if done - last_report >= 32 * 1024 * 1024:
                last_report = done
                pct = (done * 100.0 / total) if total else 0
                el = time.time() - start
                spd = (done - existing) / el / 1024.0 / 1024.0 if el > 0 else 0
                log("  %s: %d / %d bytes (%.1f%%, %.1f MB/s)" % (os.path.basename(dest), done, total, pct, spd))
    r.close()
    os.replace(part, dest)
    log("  finished %s (%d bytes)" % (os.path.basename(dest), done))
    return done


def download_verified(name, url, dest, expected_md5):
    if os.path.exists(dest) and not os.path.exists(dest + ".part"):
        sz = os.path.getsize(dest)
        # quick accept if already correct
        if expected_md5:
            actual = md5_of(dest)
            if actual == expected_md5:
                log("OK already present: %s (md5 %s)" % (name, actual))
                return True
        # else resume from it
        os.rename(dest, dest + ".part")
        log("resuming %s from %d bytes" % (name, sz))
    for attempt in range(2):
        if attempt == 1:
            for s in ("", ".part"):
                p = dest + s
                if os.path.exists(p):
                    os.remove(p)
            log("retry fresh download: %s" % name)
        download(url, dest)
        actual = md5_of(dest)
        log("  %s md5 = %s" % (name, actual))
        if expected_md5 and actual == expected_md5:
            log("VERIFIED: %s" % name)
            return True
        if not expected_md5:
            log("NO expected md5; size=%d" % os.path.getsize(dest))
            return True
        log("MISMATCH: %s (expected %s)" % (name, expected_md5))
    return False


def main():
    os.makedirs(DEST_DIR, exist_ok=True)

    log("=== GApps 9.0 md5 ===")
    g9_md5 = fetch_md5_from_sf(G9_MD5_URL)
    log("  expected: %s" % g9_md5)

    log("=== Download GApps 9.0 pico ===")
    g9_dest = os.path.join(DEST_DIR, "open_gapps-arm64-9.0-pico-20220503.zip")
    ok_g = download_verified("GApps9", G9_URL, g9_dest, g9_md5)

    log("=== Download PixysOS v2.4 ===")
    pix_dest = os.path.join(DEST_DIR, "PixysOS-v2.4-ferrari-UNOFFICIAL-20200711-100341.zip")
    ok_p = download_verified("PixysOS", PIX_URL, pix_dest, PIX_MD5)

    log("=== SUMMARY ===")
    log("GApps9 ok=%s" % ok_g)
    log("PixysOS ok=%s" % ok_p)
    if ok_g and ok_p:
        log("ALL_FILES_READY")
    else:
        log("FAILURES_PRESENT")


if __name__ == "__main__":
    main()
