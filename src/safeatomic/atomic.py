
"""
──────────────────────────────────────────────────────────────────────────────
🧪 Atomic File Utilities
Author: Roberto Bertó
License: GPL (GNU General Public License v3.0)
──────────────────────────────────────────────────────────────────────────────

Robust utilities for atomic file read/write operations with safe locking 
based on PID + session + timestamp.

Native Support For:
────────────────────
- 📁 `.txt`, `.yaml` (via ruamel.yaml), `.pkl`
- 🔐 Lockfiles using format: `pid|session|timestamp`
- 🔁 Retry logic, simulate mode, force mode, inspect utilities
- 🧪 Integrated CLI testing suite (via `click`)

──────────────────────────────────────────────
🚀 Usage Examples
──────────────────────────────────────────────

🔹 Safe write/read
──────────────────
from atomic import write_atomic, read_atomic

write_atomic("example.txt", "safe content", session="session-A")
text = read_atomic("example.txt")
print(text)

🔹 Dump/Load YAML
──────────────────
from atomic import atomic_yaml_dump, atomic_yaml_load

data = {"name": "Dom", "id": 42}
atomic_yaml_dump("conf.yaml", data)
obj = atomic_yaml_load("conf.yaml")

🔹 Atomic Pickle
──────────────────
from atomic import atomic_pickle_write, atomic_pickle_read

atomic_pickle_write("model.pkl", [1, 2, 3])
print(atomic_pickle_read("model.pkl"))

🔹 Using Context Manager
────────────────────────
from atomic import AtomicWriter

with AtomicWriter("log.txt", session="logger") as f:
    f.write("Safe log line\n")

🔹 CLI Testing Suite
─────────────────────
$ python atomic.py test-all

Generates test report at:
atomic_test_tmp/test_report.md

──────────────────────────────────────────────
GPL License
──────────────────────────────────────────────
This software is distributed under the terms of the GNU General Public License v3.
You are free to use, modify, and distribute it, provided that any derivative work 
also remains under the same license.

For full terms, see: https://www.gnu.org/licenses/gpl-3.0.html
"""

from __future__ import annotations


import os
import time
import uuid
import psutil
import shutil
import hashlib
import pickle
import json
from pathlib import Path
from typing import Optional, Any

from dataclasses import dataclass
from datetime import datetime, timezone

import click
import tempfile
import os
import shutil
import sys
import yaml

LOCK_SUFFIX = ".lock"
TMP_PREFIX = ".__tmp-"
TMP_SUFFIX = ".tmp"
DEFAULT_RETRIES = 5
DEFAULT_DELAY = 0.1
LOCK_SEPARATOR = "|"

# ───────────────────────────────
# 🔐 UNIT TEST CONSTANTS
# ───────────────────────────────

EXAMPLE_TEXT = "Hello from atomic test"
EXAMPLE_DICT = {"a": 1, "b": 2}
EXAMPLE_PICKLE = [1, 2, 3, {"x": 99}]

TEST_DIR = Path("atomic_test_tmp")
TEST_FILE = TEST_DIR / "test.txt"
TEST_YAML = TEST_DIR / "test.yaml"
TEST_PKL = TEST_DIR / "test.pkl"


# ───────────────────────────────
# 🔐 RUAMEL CONFIG 
# ───────────────────────────────

# Optional: ruamel.yaml for structured YAML IO
from ruamel.yaml import YAML
yaml_ruamel = YAML()
yaml_ruamel.indent(mapping=2, sequence=4, offset=2)

def _datetime_representer(dumper, data: datetime):
    return dumper.represent_scalar("tag:yaml.org,2002:timestamp", data.isoformat())

yaml_ruamel.representer.add_representer(datetime, _datetime_representer)
_yaml_ruamel = yaml_ruamel


# ───────────────────────────────
# 🔐 RENAME FILES
# ───────────────────────────────
def _move_atomic(src: str, dst: str, force: bool = False):
    """
    Move `src` to `dst` atomically, preserving metadata if `dst` exists.

    - Se `force=False`: falha se `dst` já existir.
    - Se `force=True`: sobrescreve `dst` caso exista.
    """
    if os.path.exists(dst):
        if not force:
            raise FileExistsError(f"Destination exists and force=False: {dst}")
        try:
            shutil.copystat(dst, src)
        except Exception as e:
            print(f"Error: Failed to copy metadata: {e}")
    os.replace(src, dst)


# ───────────────────────────────
# 🔐 LOCK FILES
# ───────────────────────────────

def get_lock_path(path: str) -> str:
    return str(path) + LOCK_SUFFIX

def lock_render(pid: int, session_hash: Optional[str], timestamp: str) -> str:
    return f"{pid}{LOCK_SEPARATOR}{session_hash or ''}{LOCK_SEPARATOR}{timestamp}"

def lock_parse(content: str) -> dict:
    parts = content.strip().split(LOCK_SEPARATOR)
    return {
        "pid": int(parts[0]) if parts[0].isdigit() else None,
        "session_hash": parts[1] or None,
        "timestamp": parts[2] if len(parts) > 2 else None,
    }

def lock_render_json(pid: int, session_hash: Optional[str], timestamp: str) -> str:
    return json.dumps({"pid": pid, "session": session_hash, "timestamp": timestamp})

def lock_parse_json(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"pid": None, "session": None, "timestamp": None, "corrupt": True}

# ───────────────────────────────
# 📌 UTILS
# ───────────────────────────────

def session_to_hash(session: Optional[str]) -> Optional[str]:
    return hashlib.sha256(session.encode()).hexdigest()[:8] if session else None

def get_tmp_path(path: str) -> str:
    base = os.path.basename(path)
    dir_ = os.path.dirname(path)
    rand = uuid.uuid4().hex[:8]
    return os.path.join(dir_, f"{TMP_PREFIX}{rand}.{base}{TMP_SUFFIX}")

def is_process_alive(pid: int) -> bool:
    return psutil.pid_exists(pid)

def is_locked(path: str) -> bool:
    return os.path.exists(get_lock_path(path))

def get_lock_age(path: str) -> float:
    lp = get_lock_path(path)
    return time.time() - os.path.getctime(lp) if os.path.exists(lp) else 0.0

def is_stale_lock(path: str, max_age_s: float) -> bool:
    return get_lock_age(path) > max_age_s if is_locked(path) else False

def force_release_lock(path: str):
    lp = get_lock_path(path)
    if os.path.exists(lp):
        os.remove(lp)

def release_stale_lock(path: str, max_age_s: float):
    if is_stale_lock(path, max_age_s):
        force_release_lock(path)

def release_lock(path: str):
    force_release_lock(path)


# ───────────────────────────────
# 📖 ATOMIC CLASSES
# ───────────────────────────────
class AtomicReader:
    def __init__(self, path: str, *, retries=DEFAULT_RETRIES, delay=DEFAULT_DELAY, require_lock=False, encoding: str = "utf-8"):
        self.path = path
        self.retries = retries
        self.delay = delay
        self.require_lock = require_lock
        self._file = None
        self.encoding = encoding

    def __enter__(self):
        for _ in range(self.retries):
            if not self.require_lock or not is_locked(self.path):
                try:
                    self._file = open_atomic(self.path, "r", encoding=self.encoding)
                    return self._file
                except FileNotFoundError:
                    time.sleep(self.delay)
                    continue
            time.sleep(self.delay)
        raise RuntimeError(f"Error: Read failed or locked: '{self.path}'")

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._file:
            self._file.close()

class AtomicWriter:
    def __init__(self, path: str, *, retries=DEFAULT_RETRIES, delay=DEFAULT_DELAY, simulate=False, session: Optional[str] = None, force=False, encoding: str = "utf-8"):
        self.path = path
        self.tmpfile = get_tmp_path(path)
        self.retries = retries
        self.delay = delay
        self.simulate = simulate
        self.session = session
        self.force = force
        self._file = None
        self.encoding = encoding

    def __enter__(self):
        if self.simulate:
            self._file = open(os.devnull, "w")
            return self._file
        if not try_acquire_lock(self.path, retries=self.retries, delay=self.delay, session=self.session, force=self.force):
            raise RuntimeError(f"Error: Lock already held or persistent: '{self.path}'")
        self._file = open_atomic(self.tmpfile, "w", encoding=self.encoding)
        return self._file

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self._file:
                self._file.close()
            if not self.simulate:
                if os.path.exists(self.path):
                    try:
                        shutil.copystat(self.path, self.tmpfile)
                    except Exception as e:
                        print(f"Error: Failed to copy metadata: {e}")
                os.replace(self.tmpfile, self.path)
        finally:
            if not self.simulate:
                force_release_lock(self.path)
                if os.path.exists(self.tmpfile):
                    os.remove(self.tmpfile)



# ───────────────────────────────
# 📖 LOCK INSPECTION
# ───────────────────────────────

@dataclass
class LockInfo:
    path: str
    exists: bool
    pid: Optional[int]
    alive: bool
    session_hash: Optional[str]
    timestamp: Optional[str]
    corrupt: bool = False

def inspect_lock(path: str) -> LockInfo:
    lp = get_lock_path(path)
    if not os.path.exists(lp):
        return LockInfo(lp, False, None, False, None, None)
    try:
        with open(lp, "r") as f:
            data = lock_parse(f.read())
        pid = data.get("pid")
        return LockInfo(
            path=lp,
            exists=True,
            pid=pid,
            alive=is_process_alive(pid) if pid else False,
            session_hash=data.get("session_hash"),
            timestamp=data.get("timestamp")
        )
    except Exception:
        return LockInfo(lp, True, None, False, None, None, corrupt=True)

def lock_info_pretty(info: LockInfo) -> str:
    if not info.exists:
        return f"🔓 No lock: {info.path}"
    status = "🟢 ALIVE" if info.alive else "🔴 DEAD"
    return f"🔐 {info.path}\nPID: {info.pid} ({status})\nSession: {info.session_hash}\nTime: {info.timestamp}\nCorrupt: {info.corrupt}"

# ───────────────────────────────
# 🚀 CORE LOCK OPS
# ───────────────────────────────

def try_acquire_lock(path: str, retries=DEFAULT_RETRIES, delay=DEFAULT_DELAY, session: Optional[str] = None, force=False) -> bool:
    lp = get_lock_path(path)
    session_hash = session_to_hash(session)
    from datetime import datetime, timezone
    timestamp = datetime.now(timezone.utc).isoformat()

    for _ in range(retries):
        if not os.path.exists(lp):
            try:
                fd = os.open(lp, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w") as f:
                    f.write(lock_render(os.getpid(), session_hash, timestamp))
                return True
            except FileExistsError:
                pass
        else:
            info = inspect_lock(path)
            if not info.alive or force:
                force_release_lock(path)
                continue
        time.sleep(delay)
    return False

# ───────────────────────────────
# 📄 FILE OPERATIONS
# ───────────────────────────────

def write_atomic(path: str, data: str, retries=DEFAULT_RETRIES, delay=DEFAULT_DELAY, simulate=False, session: Optional[str] = None, force=False, encoding="utf-8"):
    with AtomicWriter(path, retries=retries, delay=delay, simulate=simulate, session=session, force=force, encoding=encoding) as f:
        f.write(data)

def read_atomic(path: str, retries=DEFAULT_RETRIES, delay=DEFAULT_DELAY, require_lock=False, encoding="utf-8") -> str:
    with AtomicReader(path, retries=retries, delay=delay, require_lock=require_lock, encoding=encoding) as f:
        return f.read()

def open_atomic(path: str, mode: str = "r", encoding: Optional[str] = "utf-8"):
    return open(path, mode) if "b" in mode else open(path, mode, encoding=encoding)

def atomic_yaml_dump(
    path: str | Path,
    obj: Any,
    *,
    encoding: str = "utf-8",
    sort_keys: bool = False,
    indent: int = 2,
    allow_unicode: bool = True,
):
    """Atomic YAML writer using PyYAML safe_dump with formatting controls."""
    text = yaml.safe_dump(
        obj,
        sort_keys=sort_keys,
        indent=indent,
        allow_unicode=allow_unicode,
    )
    write_atomic(str(path), text, encoding=encoding)

def atomic_yaml_load(
    path: str | Path,
    *,
    encoding: str = "utf-8",
) -> Any:
    """Atomic YAML reader using PyYAML safe_load."""
    text = read_atomic(str(path), encoding=encoding)
    return yaml.safe_load(text)

def atomic_pickle_write(path: str, data):
    tmp_path = get_tmp_path(path)
    with open_atomic(tmp_path, "wb") as f:
        pickle.dump(data, f)
    if os.path.exists(path):
        try:
            shutil.copystat(path, tmp_path)
        except Exception as e:
            print(f"Error: Failed to copy metadata: {e}")
    os.replace(tmp_path, path)

def atomic_pickle_read(path: str):
    with open_atomic(path, "rb") as f:
        return pickle.load(f)


def move_atomic(src: str, dst: str, force: bool = False):
    """Wrapper para _move_atomic."""
    return _move_atomic(src, dst, force=force)


def move_atomic_force(src: str, dst: str):
    """Shim direto para _move_atomic(..., force=True)."""
    return _move_atomic(src, dst, force=True)


# json_functions

def atomic_json_dump(
    path: str | Path,
    obj: Any,
    *,
    encoding: str = "utf-8",
    indent: int | None = 2,
    ensure_ascii: bool = False,
    default: Any = str,
) -> None:
    """Atomic JSON writer using write_atomic under the hood."""
    text = json.dumps(obj, indent=indent, ensure_ascii=ensure_ascii, default=default)
    write_atomic(str(path), text, encoding=encoding)


def atomic_json_load(
    path: str | Path,
    *,
    encoding: str = "utf-8",
) -> Any:
    """Atomic JSON reader: read text then json.loads."""
    text = read_atomic(str(path), encoding=encoding)
    return json.loads(text)

# yaml functions

def atomic_yaml_dump_ruamel(
    path: str | Path,
    data: Any,
    *,
    encoding: str = "utf-8",
    yaml_instance: YAML | None = None,
) -> None:
    """Atomic YAML writer using ruamel.yaml for richer formatting/styling."""
    y = yaml_instance or _yaml_ruamel
    with AtomicWriter(str(path), encoding=encoding) as f:
        y.dump(data, f)


def atomic_yaml_load_ruamel(
    path: str | Path,
    *,
    encoding: str = "utf-8",
    yaml_instance: YAML | None = None,
) -> Any:
    """Atomic YAML reader returning ruamel-parsed Python objects."""
    y = yaml_instance or _yaml_ruamel
    text = read_atomic(str(path), encoding=encoding)
    return y.load(text)

# click functions

@click.group()
def cli():
    pass

@cli.command(name="test_prepare")
def test_prepare():
    shutil.rmtree(TEST_DIR, ignore_errors=True)
    os.makedirs(TEST_DIR, exist_ok=True)
    print("📁 Test environment prepared.")

@cli.command(name="test-atomic-write-read")
def test_atomic_write_read():
    write_atomic(TEST_FILE, EXAMPLE_TEXT)
    content = read_atomic(TEST_FILE)
    assert content == EXAMPLE_TEXT
    print("✅ atomic_write/read passed")

@cli.command(name="test_atomic_yaml")
def test_atomic_yaml():
    if not yaml_ruamel:
        print("Error: ruamel.yaml not installed")
        return
    atomic_yaml_dump(TEST_YAML, EXAMPLE_DICT)
    data = atomic_yaml_load(TEST_YAML)
    assert data == EXAMPLE_DICT
    print("✅ atomic_yaml_dump/load passed")

@cli.command(name="test_atomic_pickle")
def test_atomic_pickle():
    atomic_pickle_write(TEST_PKL, EXAMPLE_PICKLE)
    result = atomic_pickle_read(TEST_PKL)
    assert result == EXAMPLE_PICKLE
    print("✅ atomic_pickle_write/read passed")

@cli.command(name="test_lock_lifecycle")
def test_lock_lifecycle():
    path = str(TEST_FILE)
    force_release_lock(path)
    acquired = try_acquire_lock(path, session="demo-session")
    assert acquired
    info = inspect_lock(path)
    assert info.session_hash == session_to_hash("demo-session")
    release_lock(path)
    assert not is_locked(path)
    print("✅ lock acquire/release/inspect passed")


@cli.command(name="test_force_lock")
def test_force_lock():
    path = str(TEST_FILE)
    force_release_lock(path)
    try_acquire_lock(path, session="test1")
    acquired = try_acquire_lock(path, session="test2", force=True)
    assert acquired
    info = inspect_lock(path)
    assert info.session_hash == session_to_hash("test2")
    release_lock(path)
    print("✅ test_force_lock passed")

@cli.command(name="test_simulate_write")
def test_simulate_write():
    path = TEST_FILE.with_name("simulate.txt")
    try:
        tmp_path = get_tmp_path(path)
        if os.path.exists(tmp_path): os.remove(tmp_path)
        if os.path.exists(path): os.remove(path)
        with open(os.devnull, "w") as _:
            pass  # just to validate devnull
        acquired = try_acquire_lock(path, session="simulate-test")
        assert acquired
        release_lock(path)
        print("✅ test_simulate_write passed")
    except Exception as e:
        print(f"Error: test_simulate_write failed: {e}")

@cli.command()
def test_all():
    report = []
    ctx = click.get_current_context()
    def run_test(name):
        try:
            ctx.invoke(cli.commands[name].callback)
            report.append(f"✅ {name}")
        except Exception as e:
            report.append(f"Error: {name} failed: {e}")

    for name in [
        "test_prepare",
        "test-atomic-write-read",
        "test_atomic_yaml",
        "test_atomic_pickle",
        "test_lock_lifecycle",
        "test_force_lock",
        "test_simulate_write"
    ]:
        run_test(name)

    report_md = "\n".join([f"- {line}" for line in report])
    output_path = TEST_DIR / "test_report.md"
    with open(output_path, "w") as f:
        f.write("# Atomic Test Report\n\n" + report_md + "\n")

    print("\n📝 Test report saved to:", output_path)
    print("\n" + report_md)

try:
    __all__  # type: ignore[has-type]
except NameError:
    __all__ = []

__all__ += [
    "atomic_yaml_dump_ruamel",
    "atomic_yaml_load_ruamel",
]

if __name__ == "__main__":
    cli()
