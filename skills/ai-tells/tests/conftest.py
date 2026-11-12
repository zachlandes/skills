import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

FAKE_KEY = "test-key-0123456789abcdef"


class Mock:
    """Loopback stand-in for the System One endpoint. Answers are deterministic; yes_if picks sentences to flag."""

    def __init__(self, yes_if=None, model_override=None):
        self.requests, self.auth = [], []
        self.yes_if, self.model_override = yes_if or (lambda tell, sentence: 0.05), model_override
        mock = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                mock.requests.append(body)
                mock.auth.append(self.headers.get("Authorization"))
                state = body["state"]
                text = state.get("sentence", state.get("last_sentence", state.get("last_paragraph", "")))
                ans = {k: {"type": "noul", "noul": mock.yes_if(k, text)} for k in body["questions"]}
                out = json.dumps({"answers": ans, "model": mock.model_override or body["model"],
                                  "usage": {"input_tokens": len(json.dumps(body)) // 4}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(out)

        self.server = HTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


@pytest.fixture(autouse=True)
def loopback_network_only(monkeypatch):
    import urllib.request
    from urllib.parse import urlparse
    real = urllib.request.urlopen

    def local_only(request, *args, **kwargs):
        url = request.full_url if hasattr(request, "full_url") else request
        assert urlparse(url).hostname == "127.0.0.1", "tests must not contact a paid or public endpoint"
        return real(request, *args, **kwargs)
    monkeypatch.setattr(urllib.request, "urlopen", local_only)


@pytest.fixture
def mock_factory(monkeypatch):
    made = []

    def make(**kw):
        m = Mock(**kw)
        made.append(m)
        monkeypatch.setenv("AITELLS_TEST_ENDPOINT", m.url)
        monkeypatch.setenv("TYPESAFE_API_KEY", FAKE_KEY)
        return m
    yield make
    for m in made:
        m.close()
