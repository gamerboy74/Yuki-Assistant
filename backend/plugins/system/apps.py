"""
apps.py — Dynamic App Registry
Discovers ALL installed apps at runtime. No hardcoded list.
Sources: Start Menu shortcuts, UWP/Store apps (Get-StartApps), Registry App Paths.
Scanned once at startup in background thread. Cached to backend/data/app_registry.json (1hr TTL).
"""

import os, json, subprocess, threading, time, difflib, winreg
from pathlib import Path
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_CACHE_FILE = Path(__file__).parent.parent.parent / "data" / "app_registry.json"
_CACHE_TTL = 3600
_registry: dict = {}
_lock = threading.Lock()

_WEB_INDICATORS = {".com",".net",".org",".io",".in",".co",".ai",
                   ".app",".dev",".to","http://","https://","www."}

def _is_website(name: str) -> bool:
    n = name.lower()
    return any(x in n for x in _WEB_INDICATORS)

def _resolve_lnk(path: str) -> str | None:
    try:
        r = subprocess.run(
            ["powershell","-WindowStyle","Hidden","-Command",
             f"(New-Object -COM WScript.Shell).CreateShortcut('{path}').TargetPath"],
            capture_output=True, text=True, timeout=3,
            creationflags=subprocess.CREATE_NO_WINDOW)
        t = r.stdout.strip()
        return t if t and t.endswith(".exe") else None
    except: return None

def _scan_start_menu() -> dict:
    apps = {}
    dirs = [
        Path(os.environ.get("APPDATA","")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("ProgramData","")) / "Microsoft/Windows/Start Menu/Programs",
    ]
    skip = {"uninstall","readme","help","changelog","release notes"}
    for base in dirs:
        if not base.exists(): continue
        for lnk in base.rglob("*.lnk"):
            name = lnk.stem.lower()
            if any(s in name for s in skip): continue
            target = _resolve_lnk(str(lnk))
            if target:
                apps[name] = {"name": lnk.stem, "launch": target, "type": "exe"}
    return apps

def _scan_uwp() -> dict:
    apps = {}
    try:
        r = subprocess.run(
            ["powershell","-WindowStyle","Hidden","-Command","Get-StartApps | ConvertTo-Json"],
            capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW)
        if not r.stdout.strip(): return apps
        data = json.loads(r.stdout)
        if isinstance(data, dict): data = [data]
        for app in data:
            n = app.get("Name","").lower().strip()
            aid = app.get("AppId","")
            if n and aid:
                apps[n] = {"name": app.get("Name"), "launch": aid, "type": "uwp"}
    except: pass
    return apps

def _scan_registry() -> dict:
    apps = {}
    try:
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(key, i)
                    with winreg.OpenKey(key, sub) as sk:
                        try:
                            exe, _ = winreg.QueryValueEx(sk, "")
                            display = sub.replace(".exe","").lower()
                            apps[display] = {"name": sub.replace(".exe",""), "launch": exe.strip('"'), "type": "registry"}
                        except: pass
                    i += 1
                except OSError: break
    except: pass
    return apps

def _build() -> dict:
    r = {}
    r.update(_scan_uwp())
    r.update(_scan_registry())
    r.update(_scan_start_menu())  # highest priority wins
    return r

def _load_registry():
    global _registry
    with _lock:
        if _CACHE_FILE.exists():
            try:
                data = json.loads(_CACHE_FILE.read_text())
                if time.time() - data.get("_ts", 0) < _CACHE_TTL:
                    _registry = data
                    logger.info(f"[APPS] Loaded {len(_registry)-1} apps from cache")
                    return
            except: pass
        logger.info("[APPS] Scanning installed apps...")
        fresh = _build()
        fresh["_ts"] = time.time()
        _registry = fresh
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(json.dumps(fresh, indent=2))
        logger.info(f"[APPS] Done. {len(_registry)-1} apps indexed.")

def _find(query: str):
    if not _registry: _load_registry()
    q = query.lower().strip()
    keys = [k for k in _registry if not k.startswith("_")]
    if q in _registry: return q, _registry[q]
    starts = [k for k in keys if k.startswith(q) or q.startswith(k)]
    if starts:
        best = min(starts, key=len)
        return best, _registry[best]
    contains = [k for k in keys if q in k or k in q]
    if contains:
        best = min(contains, key=len)
        return best, _registry[best]
    matches = difflib.get_close_matches(q, keys, n=1, cutoff=0.6)
    if matches: return matches[0], _registry[matches[0]]
    return None, None

# Scan on import — background thread, doesn't block startup
threading.Thread(target=_load_registry, daemon=True, name="app_scan").start()

class AppControlPlugin(Plugin):
    name = "open_app"
    description = """Manage installed desktop applications.
Operations:
  open [name: str] — Launch an app (VS Code, Discord, etc.)
  close [name: str] — Close a running app
  list [search: str] — List installed apps
  refresh — Re-scan for newly installed apps
"""
    parameters = {
        "operation": {
            "type": "string",
            "required": True,
            "enum": ["open", "close", "list", "refresh"]
        },
        "name":   {"type": "string", "description": "App name for open/close"},
        "search": {"type": "string", "description": "Filter for list"}
    }

    def execute(self, operation: str = "open", name: str = "", search: str = "", **_) -> str:
        if operation == "open":
            return self._open(name)
        if operation == "close":
            return self._close(name)
        if operation == "list":
            return self._list(search)
        if operation == "refresh":
            return self._refresh()
        return f"Unknown app operation: {operation}"

    def _open(self, name: str) -> str:
        name = name.strip()
        if not name: return "What should I open, Sir?"
        if _is_website(name):
            return f"Sir, '{name}' is a website. Use 'browser' -> 'navigate' instead."

        match_name, app_data = _find(name)
        if not app_data:
            keys = [k for k in _registry if not k.startswith("_")]
            suggestions = difflib.get_close_matches(name.lower(), keys, n=3, cutoff=0.4)
            msg = f"I couldn't find '{name}' on this machine, Sir."
            if suggestions: msg += " Did you mean: " + ", ".join(suggestions) + "?"
            return msg

        launch = app_data["launch"]
        app_type = app_data["type"]
        try:
            if app_type == "uwp": subprocess.Popen(["explorer", f"shell:appsFolder\\{launch}"])
            else: subprocess.Popen([launch])
            return f"Opening {app_data['name']}."
        except:
            try:
                subprocess.Popen(["start", "", name], shell=True)
                return f"Opening {name}."
            except: return f"Failed to launch {name}."

    def _close(self, name: str) -> str:
        name = name.strip()
        if not name: return "What should I close, Sir?"
        match_name, app_data = _find(name)
        if app_data and app_data.get("launch"):
            exe_name = Path(app_data["launch"]).name
            subprocess.Popen(["taskkill", "/f", "/t", "/im", exe_name], shell=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"Closed {app_data['name']}."
        subprocess.Popen(["taskkill", "/f", "/fi", f"IMAGENAME eq {name}.exe"], shell=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Closed {name}."

    def _list(self, search: str) -> str:
        if not _registry: _load_registry()
        keys = sorted([_registry[k]["name"] for k in _registry if not k.startswith("_")])
        if search:
            search = search.lower()
            keys = [k for k in keys if search in k.lower()]
        if not keys: return "No matching apps found."
        return "Installed Apps:\n" + "\n".join(keys[:50]) + ("\n...and more" if len(keys) > 50 else "")

    def _refresh(self) -> str:
        global _registry
        with _lock:
            _registry = {}
            if _CACHE_FILE.exists(): _CACHE_FILE.unlink()
        threading.Thread(target=_load_registry, daemon=True).start()
        return "App registry refresh initiated in the background, Sir."
