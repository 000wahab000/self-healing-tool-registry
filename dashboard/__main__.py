import os

import uvicorn

from dashboard.app import create_app

uvicorn.run(
    create_app(), host="127.0.0.1", port=int(os.environ.get("DASHBOARD_PORT", "8080"))
)
