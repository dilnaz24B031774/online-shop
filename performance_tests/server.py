"""
Определяет, к какому серверу обращаться, и при необходимости запускает временный.

Порядок:
 1. Задана PERF_BASE_URL            -> используем её (сервер должен уже работать).
 2. На http://127.0.0.1:8000 есть сервер -> используем его.
 3. Иначе                           -> запускаем временный сервер на свободном порту
                                       (отдельная SQLite-база во временной папке, демо-данные seed_shop).
                                       Ваша PostgreSQL-база не затрагивается. После тестов сервер выключается.
"""
import atexit
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

from . import config

ROOT = Path(__file__).resolve().parent.parent
_state = {"base_url": None, "proc": None, "tmpdir": None, "log": None}


def _is_up(base_url):
    try:
        return requests.get(base_url + "/api/categories/", timeout=3).status_code == 200
    except requests.RequestException:
        return False


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _stop_temp_server():
    proc = _state["proc"]
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    if _state["log"]:
        _state["log"].close()
    if _state["tmpdir"]:
        shutil.rmtree(_state["tmpdir"], ignore_errors=True)


def _start_temp_server():
    port = _free_port()
    tmpdir = tempfile.mkdtemp(prefix="saudago_perf_")
    log_path = Path(tmpdir) / "server.log"
    log = open(log_path, "w", encoding="utf-8")
    env = dict(os.environ)
    env["PERF_SQLITE_PATH"] = str(Path(tmpdir) / "perf.sqlite3")
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.Popen(
        [sys.executable, str(Path(__file__).with_name("run_test_server.py")), str(port)],
        cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT,
    )
    _state.update(proc=proc, tmpdir=tmpdir, log=log)
    atexit.register(_stop_temp_server)

    base_url = f"http://127.0.0.1:{port}"
    deadline = time.time() + config.SERVER_START_TIMEOUT_S
    while time.time() < deadline:
        if proc.poll() is not None:
            log.flush()
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
            raise RuntimeError(f"Временный сервер не запустился (код {proc.returncode}). Лог:\n{tail}")
        if _is_up(base_url):
            return base_url
        time.sleep(0.5)
    raise RuntimeError("Временный сервер не успел запуститься за "
                       f"{config.SERVER_START_TIMEOUT_S} с. Проверьте, что установлены зависимости: "
                       "pip install -r requirements.txt")


def get_base_url():
    if _state["base_url"]:
        return _state["base_url"]
    if config.EXPLICIT_BASE_URL:
        url = config.EXPLICIT_BASE_URL.rstrip("/")
        if not _is_up(url):
            raise RuntimeError(f"PERF_BASE_URL={url} не отвечает. Запустите сервер: python manage.py runserver")
    elif _is_up(config.DEFAULT_URL):
        url = config.DEFAULT_URL
    else:
        url = _start_temp_server()
    _state["base_url"] = url
    return url
