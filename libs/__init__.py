__version_info__ = ("1", "8", "6")
__version__ = ".".join(__version_info__)


# Auto-compile Qt resources if not present
def _ensure_resources():
    from pathlib import Path

    resources_py = Path(__file__).parent / "resources.py"
    resources_qrc = Path(__file__).parent.parent / "resources.qrc"

    if not resources_py.exists() and resources_qrc.exists():
        import subprocess
        import sys

        try:
            subprocess.run([sys.executable, "-m", "PyQt5.pyrcc_main", "-o", str(resources_py), str(resources_qrc)], check=True)
        except Exception:
            pass  # Will fail later with proper error message


_ensure_resources()
