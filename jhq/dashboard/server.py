"""Job Hunt HQ dashboard: a live, local website over your tracker and job leads.

    jhq dashboard            # http://127.0.0.1:8765
    jhq dashboard --open     # ...and open the browser
    jhq dashboard --port 9000

Security model (local-only, nothing leaves your computer):
- Binds to 127.0.0.1 only: unreachable from your network or the internet.
- Rejects requests whose Host header isn't 127.0.0.1/localhost:<port> (blocks DNS rebinding,
  where a web page tries to reach local servers through your browser).
- No CORS headers, so other websites open in your browser can't read its data.
- The two write actions (open a folder; save a lead's status) need same-origin + a custom
  header. The lead-status write can only touch radar/lead_status.json, only for lead ids that
  exist, only with whitelisted values, and bodies over 4 KB are refused.
- Files are served only from inside your data folder (symlinks resolved first).
- Strict security headers (CSP, no framing, no referrer). No external scripts or fonts.
The tracker is read into memory (the file is released at once, so Excel can always save) and
re-read only when it changes. The page polls /api/version and refreshes itself.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import mimetypes
import secrets
import os
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .. import config
from .. import tracker as trk

HERE = Path(__file__).resolve().parent
LEAD_STATUSES = {"New", "Interested", "Applied", "Skipped"}
SKIP_REASONS = {"Too senior", "Low pay", "On-site", "Wrong role", "Company/industry",
                "Location/eligibility", "Stale/closed", "Not now"}
LIKE_REASONS = {"Company", "Role type", "Remote", "Pay", "Skills match", "Startup"}
DOC_NAMES = ("_Cover_Letter.pdf", "Interview Prep - ")

P: config.Paths = None  # set in main()
_lock = threading.Lock()
_status_lock = threading.Lock()
_cache = {"mtime": None, "payload": None, "error": None}
_sync_timer = None


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0


def load_tracker():
    """(payload, mtime, error); keeps the last good copy if a read fails (Excel mid-save)."""
    mtime = _mtime(P.tracker) or None
    if mtime is None:
        return {"headers": trk.HEADERS, "rows": []}, None, None
    with _lock:
        if _cache["mtime"] != mtime or _cache["payload"] is None:
            try:
                rows = trk.rows(P)
                for r in rows:
                    rf = r.get("Resume File")
                    guess = P.applications / config.safe_name(f"{r.get('Company')} - {r.get('Job Title')}")
                    r["_folder"] = str(Path(rf).parent) if rf else (str(guess) if guess.is_dir() else None)
                _cache.update(payload={"headers": trk.HEADERS, "rows": rows}, mtime=mtime, error=None)
            except (Exception, SystemExit) as e:  # noqa: BLE001  (TrackerError is a SystemExit)
                _cache["error"] = f"{type(e).__name__}: {e}"
        return _cache["payload"], _cache["mtime"], _cache["error"]


def leads_version():
    return max(_mtime(P.leads), _mtime(P.lead_status), _mtime(P.synced), _mtime(P.review))


def _run_sync():
    try:
        exe = Path(sys.executable)
        if exe.name.lower().startswith("pythonw"):  # the console-less autostart interpreter
            exe = exe.with_name(exe.name.lower().replace("pythonw", "python"))
        subprocess.run([str(exe), "-m", "jhq", "radar", "sync"],
                       timeout=300, capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:  # noqa: BLE001  (retried on the next run)
        pass


def schedule_sync(delay=60):
    """Debounced: a burst of Applied clicks becomes one tracker write about a minute later."""
    global _sync_timer
    if os.environ.get("JHQ_NO_SYNC"):
        return
    if _sync_timer:
        _sync_timer.cancel()
    _sync_timer = threading.Timer(delay, _run_sync)
    _sync_timer.daemon = True
    _sync_timer.start()


def _list(v):
    return [x for x in v if isinstance(x, str)] if isinstance(v, list) else []


def save_lead_status(body):
    lid = str(body.get("id", ""))
    if lid not in {l.get("id") for l in config.read_json(P.leads, []) or []}:
        return False, "unknown lead"
    status = body.get("status")
    reasons = [r for r in _list(body.get("reasons")) if r in SKIP_REASONS][:4]
    likes = [r for r in _list(body.get("like_reasons")) if r in LIKE_REASONS][:6]
    with _status_lock:
        allst = config.read_json(P.lead_status, {}) or {}
        cur = allst.get(lid, {})
        if status is not None:
            if status not in LEAD_STATUSES:
                return False, "bad status"
            cur["status"] = status
            cur["at"] = dt.datetime.now(config.timezone()).isoformat(timespec="minutes")
            cur["reasons"] = reasons if status == "Skipped" else []
        if "liked" in body:
            cur["liked"] = bool(body["liked"])
            cur["like_reasons"] = likes if cur["liked"] else []
        allst[lid] = cur
        config.write_json(P.lead_status, allst)
    if status == "Applied":
        schedule_sync()
    return True, cur


def _under(path, root):
    return os.path.commonpath([path, root]) == root


def inside_root(p):
    """True only for paths inside the data folder.

    Checked as plain text FIRST: any web page can make your browser request
    /file?path=\\\\attacker\\share (e.g. with an <img> tag), and touching such a path on Windows
    would send the attacker your hashed login. Only after the text check passes are links and
    junctions resolved and checked again."""
    try:
        if not isinstance(p, str) or not p or "\x00" in p:
            return False
        root = os.path.normcase(os.path.abspath(P.root))
        if not _under(os.path.normcase(os.path.abspath(p)), root):  # no filesystem access yet
            return False
        real_root = os.path.normcase(os.path.realpath(P.root))
        return _under(os.path.normcase(os.path.realpath(p)), real_root)
    except (ValueError, TypeError, OSError):
        return False


def open_in_file_manager(p):
    if sys.platform == "win32":
        os.startfile(p)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", p])
    else:
        subprocess.Popen(["xdg-open", p])


def client_profile():
    prof = config.read_json(P.profile, {}) or {}
    prefs = config.read_json(P.prefs, {}) or {}
    return {"first_name": (prof.get("name") or "").split(" ")[0], "years": prof.get("years_experience"),
            "salary_floor": (prefs.get("salary") or {}).get("floor"),
            "salary_currency": (prefs.get("salary") or {}).get("currency", ""),
            "daily_goal": prefs.get("daily_goal") or {"weekday": 5, "weekend": 10},
            "timezone": config.load_config().get("timezone")}


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Content-Security-Policy": ("default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; "
                                "img-src 'self' data:; frame-ancestors 'none'; form-action 'none'; "
                                "base-uri 'none'"),
}
# The page itself gets a per-response nonce: only its own <script> runs. Text from job postings is
# HTML-escaped on render, and even if something slipped through, injected scripts or onerror=
# handlers would be blocked.
PAGE_CSP = ("default-src 'none'; script-src 'nonce-{nonce}'; style-src 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; form-action 'none'; "
            "base-uri 'none'")


class Handler(BaseHTTPRequestHandler):
    server_version = "HQ"
    sys_version = ""

    def log_message(self, *a):
        pass

    def _host_ok(self):
        port = self.server.server_address[1]
        return (self.headers.get("Host") or "").lower() in {f"127.0.0.1:{port}", f"localhost:{port}"}

    def _origin_ok(self):
        port = self.server.server_address[1]
        return self.headers.get("Origin") in {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in {**SECURITY_HEADERS, **(extra or {})}.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        return self._send(code, json.dumps(obj, ensure_ascii=False, default=str))

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, '{"error":"forbidden"}')
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ("/", "/index.html"):
            nonce = secrets.token_urlsafe(18)
            page = (HERE / "index.html").read_text(encoding="utf-8").replace("<script>", f'<script nonce="{nonce}">')
            return self._send(200, page, "text/html; charset=utf-8",
                              {"Content-Security-Policy": PAGE_CSP.format(nonce=nonce)})
        if u.path == "/api/version":
            _, mtime, err = load_tracker()
            return self._json({"mtime": mtime, "error": err, "lmtime": leads_version()})
        if u.path == "/api/profile":
            return self._json(client_profile())
        if u.path == "/api/leads":
            return self._json({"leads": config.read_json(P.leads, []) or [],
                               "status": config.read_json(P.lead_status, {}) or {},
                               "synced": config.read_json(P.synced, {}) or {},
                               "review": config.read_json(P.review, None), "lmtime": leads_version()})
        if u.path == "/api/skills":
            plan = next((str(p) for p in (P.skillgap_dir / "Learning Plan.docx",) if p.is_file()), None)
            return self._json({"data": config.read_json(P.skillgap, None), "plan": plan})
        if u.path == "/api/data":
            payload, mtime, err = load_tracker()
            out = dict(payload or {"headers": [], "rows": []})
            out.update(mtime=mtime, error=err, path=str(P.tracker),
                       modified=dt.datetime.fromtimestamp(mtime).isoformat(timespec="seconds") if mtime else None)
            return self._json(out)
        if u.path == "/api/docs":
            folder = (q.get("folder") or [""])[0]
            if not folder or not inside_root(folder) or not os.path.isdir(folder):
                return self._json({"docs": []})
            docs = sorted(str(p) for p in Path(folder).iterdir()
                          if p.is_file() and any(n in p.name for n in DOC_NAMES))
            jd = Path(folder) / "Job Description.docx"
            return self._json({"docs": docs, "jd": str(jd) if jd.is_file() else None})
        if u.path == "/file":
            p = (q.get("path") or [""])[0]
            if not p or not inside_root(p) or not os.path.isfile(p):
                return self._send(404, '{"error":"not found"}')
            ctype = mimetypes.guess_type(p)[0] or "application/octet-stream"
            disp = "inline" if ctype == "application/pdf" else "attachment"
            if ctype not in ("application/pdf",):
                ctype = "application/octet-stream"  # never render other files as pages
            name = os.path.basename(p).replace('"', "").encode("ascii", "replace").decode()
            return self._send(200, Path(p).read_bytes(), ctype, {"Content-Disposition": f'{disp}; filename="{name}"'})
        return self._send(404, '{"error":"not found"}')

    def do_POST(self):
        u = urlparse(self.path)
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if n < 0 or n > 4096:
            self.close_connection = True  # don't read an oversized body; just hang up after replying
            return self._send(413, '{"error":"too large"}')
        raw = self.rfile.read(n) if n else b""  # always drain, so the reply isn't cut off
        if (not self._host_ok() or not self._origin_ok()
                or u.path not in ("/api/open", "/api/lead-status") or self.headers.get("X-HQ") != "1"
                or not (self.headers.get("Content-Type") or "").startswith("application/json")):
            return self._send(403, '{"error":"forbidden"}')
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            return self._send(400, '{"error":"bad json"}')
        if not isinstance(body, dict):
            return self._send(400, '{"error":"bad json"}')
        if u.path == "/api/lead-status":
            ok, res = save_lead_status(body)
            return self._json({"ok": ok, "result": res}, 200 if ok else 400)
        p = str(body.get("path", ""))
        if not p or not inside_root(p) or not os.path.isdir(p):
            return self._send(404, '{"error":"not found"}')
        open_in_file_manager(os.path.realpath(p))
        return self._send(200, '{"ok":true}')


def _other_methods(self):
    self._send(405, '{"error":"method not allowed"}')


for _m in ("do_PUT", "do_DELETE", "do_PATCH", "do_OPTIONS", "do_HEAD", "do_TRACE", "do_CONNECT"):
    setattr(Handler, _m, _other_methods)


def make_server(port, paths=None):
    global P
    P = paths or config.Paths()
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="jhq dashboard")
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="no console output (autostart mode)")
    a = ap.parse_args(argv)
    port = a.port or int(config.load_config().get("dashboard_port") or 8765)
    url = f"http://127.0.0.1:{port}/"
    say = (lambda *_: None) if (a.quiet or sys.stdout is None) else print
    try:
        srv = make_server(port)
    except OSError:
        say(f"Port {port} is busy: Job Hunt HQ is probably already running at {url}")
        if a.open:
            webbrowser.open(url)
        return
    load_tracker()
    say(f"Job Hunt HQ running at {url}  (Ctrl+C to stop)\nData folder: {P.root}")
    if a.open:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
