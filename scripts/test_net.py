import urllib.request, ssl

tests = [
    ("archive.org PixysOS",
     "https://archive.org/download/afharchive_356_pixysos-v24-ferrari-unofficial-20200711-100341zip/PixysOS-v2.4-ferrari-UNOFFICIAL-20200711-100341.zip"),
    ("sourceforge GApps9",
     "https://sourceforge.net/projects/opengapps/files/arm64/20220503/open_gapps-arm64-9.0-pico-20220503.zip/download"),
]

ctx = ssl.create_default_context()
for name, url in tests:
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Wget/1.21"})
        r = urllib.request.urlopen(req, timeout=30, context=ctx)
        print(name, "->", r.status, "len=", r.headers.get("Content-Length"), "final=", r.geturl())
    except Exception as e:
        print(name, "ERROR:", type(e).__name__, e)
