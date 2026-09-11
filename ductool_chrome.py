from __future__ import annotations
import json, os, shutil
from pathlib import Path
from urllib.parse import urlparse
from ductool_config import load_config

def chrome_settings(number:int):
    cfg=load_config(); g=cfg.get("general",{}); c=cfg.get("chrome",{})
    profile_root=Path(c.get("profile_root") or g.get("chrome_profile_root") or r"C:\duc\FacebookChrome")
    ports=c.get("ports",{}) or {}
    port=int(ports.get(str(number), int(g.get("chrome_port_base",9310))+number))
    executable=str(c.get("executable") or "").strip()
    proxies=c.get("proxies",{}) or {}
    proxy=str(proxies.get(str(number),"") or "").strip()
    return executable, profile_root, port, proxy

def find_chrome(configured=""):
    candidates=[configured, shutil.which("chrome"), shutil.which("chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES",""),"Google","Chrome","Application","chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)",""),"Google","Chrome","Application","chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA",""),"Google","Chrome","Application","chrome.exe")]
    for p in candidates:
        if p and os.path.exists(p): return p
    raise RuntimeError("Không tìm thấy Google Chrome trên máy.")

def parse_proxy(value):
    value=(value or "").strip()
    if not value: return None
    if "://" not in value and value.count(":")>=3 and "@" not in value:
        host,port,user,password=value.split(":",3)
        return {"scheme":"http","host":host.strip(),"port":int(port),"username":user,"password":password}
    raw=value if "://" in value else "http://"+value
    p=urlparse(raw)
    if not p.hostname or not p.port: raise ValueError(f"Proxy không hợp lệ: {value}")
    return {"scheme":(p.scheme or "http").lower(),"host":p.hostname,"port":int(p.port),"username":p.username or "","password":p.password or ""}

def _proxy_auth_extension(number, proxy):
    ext=Path(r"C:\duc\proxy_extensions")/f"Chrome_{number}"; ext.mkdir(parents=True,exist_ok=True)
    scheme=proxy["scheme"] if proxy["scheme"] in ("http","https","socks4","socks5") else "http"
    manifest={"manifest_version":3,"name":f"DUCTOOL Proxy Chrome {number}","version":"1.0.0","permissions":["proxy","storage","webRequest","webRequestAuthProvider"],"host_permissions":["<all_urls>"],"background":{"service_worker":"background.js"}}
    (ext/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    js = "chrome.proxy.settings.set({value:{mode:'fixed_servers',rules:{singleProxy:{scheme:%s,host:%s,port:%d},bypassList:['localhost','127.0.0.1']}},scope:'regular'});\n" % (json.dumps(scheme),json.dumps(proxy['host']),int(proxy['port']))
    js += "chrome.webRequest.onAuthRequired.addListener(function(details){return {authCredentials:{username:%s,password:%s}};},{urls:['<all_urls>']},['blocking']);\n" % (json.dumps(proxy['username']),json.dumps(proxy['password']))
    (ext/"background.js").write_text(js,encoding="utf-8")
    return ext

def proxy_args(number, value):
    p=parse_proxy(value)
    if not p: return []
    server=f"{p['scheme']}://{p['host']}:{p['port']}"
    args=[f"--proxy-server={server}"]
    if p.get("username"):
        ext=_proxy_auth_extension(number,p)
        args += [f"--disable-extensions-except={ext}",f"--load-extension={ext}"]
    return args
