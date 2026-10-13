import os

import uvicorn

from mock_api.app import create_app

uvicorn.run(
    create_app(), host="127.0.0.1", port=int(os.environ.get("MOCK_PORT", "8000"))
)
