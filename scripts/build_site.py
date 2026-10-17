"""Put the Python wheels the web page installs into site/wheels and list them.

    python scripts/build_site.py

The page runs the same `data_cleaner` package as the CLI, installed inside Pyodide from
these wheels, so the browser and the tests always exercise identical code.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WHEELS = ROOT / "site" / "wheels"
RUNTIME = ["openpyxl==3.1.5", "et-xmlfile==2.0.0"]


def pip(*args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "pip", "--disable-pip-version-check", "-q", *args], check=True
    )


def main() -> None:
    shutil.rmtree(WHEELS, ignore_errors=True)
    WHEELS.mkdir(parents=True)
    pip("download", "--no-deps", "--only-binary=:all:", "-d", str(WHEELS), *RUNTIME)
    pip("wheel", "--no-deps", "-w", str(WHEELS), str(ROOT))
    names = sorted(p.name for p in WHEELS.glob("*.whl"))
    (ROOT / "site" / "data").mkdir(exist_ok=True)
    (ROOT / "site" / "data" / "engine.json").write_text(json.dumps({"wheels": names}, indent=1))
    print("\n".join(names))


if __name__ == "__main__":
    main()
