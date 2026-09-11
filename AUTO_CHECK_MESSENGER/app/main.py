from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .watcher import Watcher
from .chrome_selector import save_selection, resolve_chrome

app = FastAPI(title="Messenger Telegram / Zalo Watcher")
watcher = Watcher()

HTML = """
<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<title>Messenger Telegram / Zalo Watcher</title>
<style>
body{font-family:Arial,sans-serif;max-width:760px;margin:35px auto;padding:0 16px}
.card{border:1px solid #ccc;border-radius:12px;padding:18px;margin:16px 0}
button{padding:10px 18px;margin:5px;font-size:16px;cursor:pointer}
pre{background:#f4f4f4;padding:14px;border-radius:8px;white-space:pre-wrap}
</style>
</head>
<body>
<h2>Messenger → Telegram / Zalo</h2>
<div class="card">
<h3>Chọn Chrome của tool đăng bài</h3>
<button onclick="choose(1)">Chrome 1</button>
<button onclick="choose(2)">Chrome 2</button>
<button onclick="choose(3)">Chrome 3</button>
<button onclick="choose(4)">Chrome 4</button>
<p id="chrome"></p>
</div>
<div class="card">
<button onclick="startW()">START</button>
<button onclick="stopW()">STOP</button>
<pre id="status"></pre>
</div>
<script>
async function choose(n){
 await fetch('/chrome/select/'+n,{method:'POST'});
 await refresh();
}
async function startW(){
 await fetch('/start',{method:'POST'});
 setTimeout(refresh,700);
}
async function stopW(){
 await fetch('/stop',{method:'POST'});
 await refresh();
}
async function refresh(){
 const c=await fetch('/chrome/status').then(r=>r.json());
 document.getElementById('chrome').innerText='Đang chọn Chrome '+c.chrome_number+' | port '+c.port;
 const s=await fetch('/status').then(r=>r.json());
 document.getElementById('status').innerText=JSON.stringify(s,null,2);
}
refresh();
setInterval(refresh,3000);
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML

@app.post("/chrome/select/{number}")
async def select_chrome(number: int):
    try:
        save_selection(number)
        n, port = resolve_chrome()
        return {"ok": True, "chrome_number": n, "port": port}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

@app.get("/chrome/status")
async def chrome_status():
    number, port = resolve_chrome()
    return {"chrome_number": number, "port": port}

@app.post("/start")
async def start():
    return {"ok": True, "status": "started" if watcher.start() else "already_running"}

@app.post("/stop")
async def stop():
    await watcher.stop()
    return {"ok": True, "status": "stopped"}

@app.get("/status")
async def status():
    return watcher.status()
