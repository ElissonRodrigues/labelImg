__version_info__ = ("1", "8", "6")
__version__ = ".".join(__version_info__)


# Auto-compile Qt6 resources if not present
def _ensure_resources():
    from pathlib import Path
    import subprocess

    resources_py = Path(__file__).parent / "resources.py"
    resources_qrc = Path(__file__).parent.parent / "resources.qrc"

    if not resources_py.exists() and resources_qrc.exists():
        try:
            # pyside6-rcc is now a mandatory dependency in pyproject.toml
            subprocess.run(
                ["pyside6-rcc", "-o", str(resources_py), str(resources_qrc)], check=True
            )

            # Post-process: Ensure the generated file uses PyQt6 imports
            with open(resources_py, "r") as f:
                content = f.read()

            if "from PySide6" in content:
                content = content.replace("from PySide6", "from PyQt6")
                with open(resources_py, "w") as f:
                    f.write(content)
        except Exception:
            pass  # Fail silently or handle if needed


_ensure_resources()
