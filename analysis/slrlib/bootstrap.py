"""Dependency bootstrap — was copy-pasted identically into 7 pipeline scripts."""
import subprocess
import sys


def ensure(package, import_name=None):
    """pip-install *package* if *import_name* (default: package) won't import."""
    name = import_name or package
    try:
        __import__(name)
    except ImportError:
        print(f"[bootstrap] Installing '{package}'...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package, "-q"])
