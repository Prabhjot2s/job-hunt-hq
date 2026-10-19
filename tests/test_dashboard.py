import http.client
import json
import threading

import pytest

from jhq import config
from jhq.dashboard import server


@pytest.fixture()
def srv(data):
    s = server.make_server(0, data)  # port 0 = any free port
    t = threading.Thread(target=s.serve_forever, daemon=True)
    t.start()
    config.write_json(data.leads, [{"id": "abc123def456", "company": "Acme", "title": "Analyst", "fit": 8}])
    yield s
    s.shutdown()


def call(s, method, path, body=None, headers=None, host=None):
    port = s.server_address[1]
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    h = {"Host": host or f"127.0.0.1:{port}", **(headers or {})}
    c.request(method, path, body=body, headers=h)
    r = c.getresponse()
    return r.status, r.read(), dict(r.getheaders())


def post_headers(s, extra=None):
    port = s.server_address[1]
    return {"Origin": f"http://127.0.0.1:{port}", "X-HQ": "1", "Content-Type": "application/json", **(extra or {})}


def test_page_and_api(srv):
    status, body, headers = call(srv, "GET", "/")
    assert status == 200 and b"Job Hunt HQ" in body
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert "Access-Control-Allow-Origin" not in headers
    status, body, _ = call(srv, "GET", "/api/profile")
    assert json.loads(body)["first_name"] == "Alex"


def test_rejects_foreign_host(srv):
    assert call(srv, "GET", "/api/data", host="evil.example:80")[0] == 403


def test_file_serving_is_confined(srv, data, tmp_path):
    outside = tmp_path / "secret.txt"
    outside.write_text("secret")
    assert call(srv, "GET", f"/file?path={outside}")[0] == 404
    assert call(srv, "GET", f"/file?path={data.root}/../secret.txt")[0] == 404
    inside = data.applications / "x.docx"
    inside.write_bytes(b"PK")
    status, _, headers = call(srv, "GET", f"/file?path={inside}")
    assert status == 200 and headers["Content-Type"] == "application/octet-stream"
    assert headers["Content-Disposition"].startswith("attachment")


def test_post_needs_origin_header_and_json(srv):
    body = json.dumps({"id": "abc123def456", "status": "Interested"})
    assert call(srv, "POST", "/api/lead-status", body, {"Content-Type": "application/json", "X-HQ": "1"})[0] == 403
    assert call(srv, "POST", "/api/lead-status", body, post_headers(srv, {"X-HQ": "0"}))[0] == 403
    assert call(srv, "POST", "/api/lead-status", body, post_headers(srv, {"Content-Type": "text/plain"}))[0] == 403
    assert call(srv, "POST", "/api/lead-status", body,
                post_headers(srv, {"Origin": "http://evil.example"}))[0] == 403
    assert call(srv, "POST", "/api/lead-status", body, post_headers(srv))[0] == 200


def test_lead_status_whitelist(srv, data):
    h = post_headers(srv)
    assert call(srv, "POST", "/api/lead-status", json.dumps({"id": "nope", "status": "Applied"}), h)[0] == 400
    assert call(srv, "POST", "/api/lead-status", json.dumps({"id": "abc123def456", "status": "Hacked"}), h)[0] == 400
    assert call(srv, "POST", "/api/lead-status", "x" * 5000, h)[0] == 413
    call(srv, "POST", "/api/lead-status",
         json.dumps({"id": "abc123def456", "status": "Skipped", "reasons": ["Low pay", "<script>"]}), h)
    saved = config.read_json(data.lead_status)["abc123def456"]
    assert saved["status"] == "Skipped" and saved["reasons"] == ["Low pay"]


def test_open_folder_is_confined(srv, tmp_path):
    h = post_headers(srv)
    assert call(srv, "POST", "/api/open", json.dumps({"path": str(tmp_path)}), h)[0] == 404


def test_other_methods_refused(srv):
    for m in ("PUT", "DELETE", "OPTIONS"):
        assert call(srv, m, "/api/data")[0] == 405
