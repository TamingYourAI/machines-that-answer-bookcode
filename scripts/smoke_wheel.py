"""Install the wheel in a clean venv and request the UI from an unrelated directory."""
from pathlib import Path
import subprocess
import sys
import tempfile
import venv

ROOT = Path(__file__).resolve().parents[1]
wheel = sorted((ROOT / "full-app/dist").glob("*.whl"))[-1]
with tempfile.TemporaryDirectory(prefix="ova-wheel-") as temp:
    target = Path(temp)
    venv.create(target / "venv", with_pip=True)
    python = target / "venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    subprocess.run([str(python), "-m", "pip", "install", "--quiet", f"{wheel}[server]",
                    "-c", str(ROOT / "full-app/requirements.lock")], check=True)
    code = '''from fastapi.testclient import TestClient
from ova_server.app import create_app
from ova_server.settings import Settings
from pathlib import Path
with TestClient(create_app(Settings(data_dir=Path("data"),secret="wheel-test"))) as c:
    for url in ("/", "/static/app.js", "/static/app.css", "/api/config", "/healthz"):
        response = c.get(url)
        assert response.status_code == 200, (url,response.status_code)
print("Installed wheel: UI, static assets, synthetic policies and API work outside checkout")
'''
    subprocess.run([str(python), "-c", code], cwd=target, check=True)
