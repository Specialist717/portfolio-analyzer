"""
Ensure runtime dependencies are importable before the GUI starts.

Installation strategies are tried in order: uv-managed Python, the active
virtual environment, then a local _vendor fallback.
"""

import importlib
import os
import shutil
import site
import subprocess
import sys

from config import REQUIRED_PACKAGES

# Local fallback vendor directory.
_VENDOR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_vendor")


def _is_uv_python() -> bool:
    """Return True when this interpreter is managed by uv."""
    exe = sys.executable.replace("\\", "/").lower()
    return "uv" in exe or "uv/python" in exe


def _uv_executable() -> str | None:
    """Return the path to the uv binary, or None if not on PATH."""
    return shutil.which("uv")


def _patch_sys_path() -> None:
    """Inject site-packages directories and vendor fallback into sys.path."""
    candidates: list[str] = []
    try:
        candidates.extend(site.getsitepackages())
    except Exception:
        pass
    try:
        candidates.append(site.getusersitepackages())
    except Exception:
        pass
    if os.path.isdir(_VENDOR_DIR):
        candidates.append(_VENDOR_DIR)

    for path in candidates:
        if path and path not in sys.path:
            sys.path.append(path)

    importlib.invalidate_caches()


def _can_import(module_name: str) -> bool:
    """Return True if *module_name* can be imported right now."""
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False


def _run(cmd: list[str]) -> bool:
    """Run a subprocess command; return True on success."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode == 0


def _install_into_current_env(pip_names: list[str]) -> bool:
    """Install packages into the active Python environment using pip."""
    print(f"[boot] Installing into current Python environment: {sys.executable}")
    args = [sys.executable, "-m", "pip", "install", "--upgrade", "--disable-pip-version-check"] + pip_names
    if _run(args):
        importlib.invalidate_caches()
        _patch_sys_path()
        return True
    return False


def ensure_packages() -> None:
    """
    Check for missing packages and install them automatically.
    Must be called before any third-party import in the application.
    """
    _patch_sys_path()

    missing = [
        (imp, pip)
        for imp, pip in REQUIRED_PACKAGES.items()
        if not _can_import(imp)
    ]
    if not missing:
        return

    pip_names = [pip for _, pip in missing]
    print(f"[boot] Missing packages: {', '.join(pip_names)}")

    # Strategy A: uv-managed Python.
    if _is_uv_python():
        uv = _uv_executable()
        if uv:
            print("[boot] uv-managed Python detected - using `uv pip install` ...")
            if _run([uv, "pip", "install"] + pip_names):
                importlib.invalidate_caches()
                _patch_sys_path()
                still_missing = [i for i, _ in missing if not _can_import(i)]
                if not still_missing:
                    print("[boot] All packages installed via uv.\n")
                    return

        print(
            "\n[boot] Could not install automatically into a uv-managed Python.\n"
            "Please run ONE of the following commands, then re-run this script:\n\n"
            f"    uv pip install {' '.join(pip_names)}\n\n"
            "  - or -\n\n"
            f"    {sys.executable} -m pip install {' '.join(pip_names)}\n"
        )
        sys.exit(1)

    # Strategy B: active virtual environment.
    in_venv = bool(os.environ.get("VIRTUAL_ENV")) or "venv" in sys.executable.lower() or "env" in sys.executable.lower()
    if in_venv:
        print("[boot] Virtual environment detected - using current environment pip install.")
        if _install_into_current_env(pip_names):
            still_missing = [i for i, _ in missing if not _can_import(i)]
            if not still_missing:
                print("[boot] All packages installed into current environment.\n")
                return
            print("[boot] Some packages still could not be imported after install; falling back to local vendor install.")

    # Strategy C: local vendor directory.
    print(f"[boot] Installing into local vendor dir: {_VENDOR_DIR}")
    os.makedirs(_VENDOR_DIR, exist_ok=True)

    for imp_name, pip_name in missing:
        print(f"[boot]   {pip_name} ...", end=" ", flush=True)
        ok = _run([
            sys.executable, "-m", "pip", "install", pip_name,
            "--target", _VENDOR_DIR,
            "--upgrade", "--disable-pip-version-check",
        ])
        importlib.invalidate_caches()

        if ok and _can_import(imp_name):
            print("OK")
        else:
            print("FAILED")
            print(
                f"\n[boot] Could not install '{pip_name}'.\n"
                f"Please run manually:\n"
                f"    {sys.executable} -m pip install {' '.join(pip_names)}\n"
            )
            sys.exit(1)

    print("[boot] All packages ready.\n")
