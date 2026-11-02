"""Locate and run LibreOffice (soffice) for HWPX/HWP conversions.

Minimal helper for this skill: finds the soffice binary on macOS, Linux and
Windows and runs it headless with an isolated user profile so that a running
LibreOffice instance or a fresh sandbox does not block the conversion.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

_CANDIDATES = [
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/usr/bin/soffice",
    "/usr/local/bin/soffice",
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
]


def find_soffice() -> str:
    """Return the path of the soffice executable or raise FileNotFoundError."""
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    for candidate in _CANDIDATES:
        if Path(candidate).exists():
            return candidate
    raise FileNotFoundError(
        "LibreOffice (soffice) not found. Install it, e.g. `brew install --cask libreoffice` "
        "or `sudo apt install libreoffice`."
    )


def run_soffice(args: list, **kwargs) -> subprocess.CompletedProcess:
    """Run soffice with `args`; accepts the same keyword arguments as subprocess.run."""
    profile = Path(tempfile.mkdtemp(prefix="hwpx-lo-profile-"))
    try:
        cmd = [find_soffice(), "-env:UserInstallation=" + profile.as_uri()] + list(args)
        env = dict(os.environ)
        env.setdefault("SAL_USE_VCLPLUGIN", "svp")  # headless rendering backend
        kwargs.setdefault("env", env)
        return subprocess.run(cmd, **kwargs)
    finally:
        shutil.rmtree(profile, ignore_errors=True)
