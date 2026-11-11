import urllib.request, struct, zlib, os, hashlib
url='https://bigota.d.miui.com/V6.6.10.0.LXIMICF/miui_MI4iGlobal_V6.6.10.0.LXIMICF_80f20c0908_5.0.zip'
OUT='stock-wifi'
def get(a,b):
    return urllib.request.urlopen(urllib.request.Request(url,headers={'Range':'bytes=%d-%d'%(a,b),'User-Agent':'Mozilla/5.0'}),timeout=120).read()
want=('libwifi-hal-qcom.so','libwifi-service.so','wcnss_service','pronto_wlan.ko','init.qcom.wifi.sh','prima/','wpa_supplicant','p2p_supplicant','libwpa_client','libwcnss','WifiLogger','hostapd','libQWiFiSoftApCfg','wifi/','libqmi','libmdmdetect','libqmiservices','libidl','libdiag')
cd=open('cd.bin','rb').read(); p=0
while p<len(cd) and cd[p:p+4]==b'PK\x01\x02':
    meth,=struct.unpack('<H',cd[p+10:p+12]); crc,csz,usz=struct.unpack('<III',cd[p+16:p+28])
    nl,el,cl=struct.unpack('<HHH',cd[p+28:p+34]); off,=struct.unpack('<I',cd[p+42:p+46])
    name=cd[p+46:p+46+nl].decode(); p+=46+nl+el+cl
    if name.endswith('/') or not any(w in name for w in want) or 'odex' in name or 'media/' in name: continue
    lh=get(off,off+29); n2,e2=struct.unpack('<HH',lh[26:30])
    data=get(off+30+n2+e2, off+30+n2+e2+csz-1) if csz else b''
    if meth==8: data=zlib.decompress(data,-15)
    assert zlib.crc32(data)&0xffffffff==crc and len(data)==usz, name
    dst=os.path.join(OUT,*name.split('/')); os.makedirs(os.path.dirname(dst),exist_ok=True)
    open(dst,'wb').write(data); print('OK',usz,name)
