import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Hosts run `python -m dashboard` from a plain checkout, without `pip install -e .`.
for p in (ROOT, ROOT / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import uvicorn
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from dashboard.app import create_app

# Hosting platforms (Railway, Render, Koyeb, Fly, Heroku...) inject PORT and need 0.0.0.0.
port = os.environ.get("PORT") or os.environ.get("DASHBOARD_PORT", "8080")
host = os.environ.get("HOST", "0.0.0.0" if "PORT" in os.environ else "127.0.0.1")

os.environ["DASHBOARD_BIND_HOST"] = host  # off localhost, the Connections routes need a token
uvicorn.run(create_app(), host=host, port=int(port))
