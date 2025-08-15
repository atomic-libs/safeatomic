# safeatomic

Safe, cross-platform **atomic file operations** with PID/session locking, stale lock detection, retries, and multi-format support (YAML, JSON, pickle).

Maintained as the modern, actively supported successor to [`python-atomicwrites`](https://github.com/untitaker/python-atomicwrites).  
**Backwards-compatible API** with new features for reliability and robustness.

---

## 📌 Overview

`safeatomic` provides **robust utilities** for atomic file read/write operations with safe locking based on:

- **PID**
- **Session**
- **Timestamp**

It prevents partial writes, detects stale locks, and supports retries or forced operations.

**Native Support For:**

- 📄 `.txt`  
- 📝 `.yaml` (via `ruamel.yaml`)  
- 📦 `.pkl` (pickle)  
- 🔐 Lockfiles using format: `pid|session|timestamp`  
- 🔁 Retry logic, simulate mode, force mode, inspect utilities  
- 🧪 Integrated CLI testing suite (via `click`)

---

## 🚀 Installation

```bash
pip install git+https://github.com/atomic-libs/safeatomic.git
```

## Development

```bash
git clone https://github.com/atomic-libs/safeatomic.git
cd safeatomic
pip install -e .[dev]
```

## **Filesystem and OS Compatibility**

`safeatomic` relies on `os.replace` to provide atomic file reads and writes. This approach works on file systems that guarantee atomic renames.

* Linux/Unix: ext4, XFS, Btrfs, and similar  
* macOS: APFS (and HFS+ on older versions)  
* Windows: NTFS and exFAT

Limitations

* Remote or network file systems (e.g., NFS, SMB, FUSE) may not offer atomic operations.  
* Requires Python ≥ 3.10.

## **python-atomicwrites compat**

We maintain a fork of [`python-atomicwrites`](https://pypi.org/project/atomicwrites/) at [`atomic-libs/python-atomicwrites`](https://github.com/atomic-libs/python-atomicwrites).  
The original project ([`untitaker/python-atomicwrites`](https://github.com/untitaker/python-atomicwrites)) is unmaintained after the PyPI 2FA requirement led to its deprecation.  

Our fork wraps [`safeatomic`](https://github.com/atomic-libs/safeatomic) while preserving the original API, ensuring that existing `atomicwrites` code continues to work without changes.

The original `atomicwrites` package on PyPI is also unmaintained.  
Install the actively maintained versions directly from GitHub:

```bash
pip install https://github.com/atomic-libs/safeatomic
pip install https://github.com/atomic-libs/python-atomicwrites
```

## Requirements

- Python 3.10+
- [click](https://pypi.org/project/click/) >= 8.2.1
- [psutil](https://pypi.org/project/psutil/) >= 7.0.0
- [PyYAML](https://pypi.org/project/PyYAML/) >= 6.0.2
- [ruamel.yaml](https://pypi.org/project/ruamel.yaml/) (opcional, mas necessário para `atomic_yaml_dump_ruamel`)


## **PyPI repo**

A packaged release on PyPI is planned soon.
