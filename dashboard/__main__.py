import os
from pathlib import Path
import uvicorn
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from dashboard.app import create_app

uvicorn.run(
    create_app(), host="127.0.0.1", port=int(os.environ.get("DASHBOARD_PORT", "8080"))
)
