"""Build script: kill running exe, then run PyInstaller."""
import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable

# Kill running instance if present
subprocess.run(["taskkill", "/F", "/IM", "DarkModeAutoSwitcher.exe"],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# Build
result = subprocess.run(
    [PYTHON, "-m", "PyInstaller", "build.spec", "--clean", "--noconfirm"],
    cwd=ROOT,
)

sys.exit(result.returncode)
