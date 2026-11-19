"""Shared test setup.

Every test run uses a fresh temporary SQLite database and the knowledge-base
chatbot (Ollama off), so tests never touch your real data and need no AI model.
The ``server`` fixture starts the real FastAPI app with uvicorn on a free port.
"""

import itertools
import json
import os
import socket
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]

# Must happen before the app modules are imported anywhere.
_TMP_DIR = tempfile.mkdtemp(prefix="jeevandhara-tests-")
os.environ["JEEVANDHARA_DB"] = os.path.join(_TMP_DIR, "test.db")
os.environ["JEEVANDHARA_LLM"] = "off"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_counter = itertools.count(1)


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def server():
    """Run the app on a background thread; yields its base URL."""
    import uvicorn

    import main

    port = _free_port()
    config = uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="warning")
    uv_server = uvicorn.Server(config)
    thread = threading.Thread(target=uv_server.run, daemon=True)
    thread.start()

    deadline = time.time() + 20
    while not uv_server.started:
        if time.time() > deadline or not thread.is_alive():
            raise RuntimeError("Test server did not start")
        time.sleep(0.05)

    yield f"http://127.0.0.1:{port}"

    uv_server.should_exit = True
    thread.join(timeout=5)


class Api:
    """Tiny JSON client: api("GET", "/path") -> (status_code, body)."""

    def __init__(self, base_url):
        self.base_url = base_url

    def __call__(self, method, path, body=None, headers=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json", "Accept": "application/json", **(headers or {})},
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        try:
            with opener.open(request, timeout=30) as response:
                return response.status, _decode(response)
        except urllib.error.HTTPError as error:
            return error.code, _decode(error)

    def raw(self, path, headers=None):
        request = urllib.request.Request(self.base_url + path, headers=headers or {})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        try:
            with opener.open(request, timeout=30) as response:
                return response.status, dict(response.headers), response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            return error.code, dict(error.headers), error.read().decode("utf-8", "replace")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _decode(response):
    raw = response.read().decode("utf-8")
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return raw


@pytest.fixture(scope="session")
def api(server):
    return Api(server)


def make_profile(**overrides):
    number = next(_counter)
    profile = {
        "username": f"farmer{number}_{int(time.time() * 1000) % 100000}",
        "password": "secret123",
        "name": "Ramesh Kumar",
        "age": 38,
        "income": 75000,
        "land_size": 1.8,
        "state": "Punjab",
        "district": "Amritsar",
    }
    profile.update(overrides)
    return profile


@pytest.fixture
def new_farmer(api):
    """Factory: register (and log in) a farmer; returns its profile + user_id."""

    def create(**overrides):
        profile = make_profile(**overrides)
        status, body = api("POST", "/register", profile)
        assert status == 201, body
        status, body = api("POST", "/login", {"username": profile["username"], "password": profile["password"]})
        assert status == 200, body
        return {**profile, "id": body["user_id"]}

    return create


@pytest.fixture
def farmer(new_farmer):
    return new_farmer()
