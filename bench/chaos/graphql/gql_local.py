"""Serve the project's strawberry GraphQL mock with a runtime mutation switch. No LLM.

  POST /__mutation {"name": null|"M1"|"M2"|"M3"}   -> mock.set_mutation(name)
  everything else                                  -> the mock (/graphql)
"""

import argparse
import json

import uvicorn

from mock_api.graphql_app import create_app

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, required=True)
A = ap.parse_args()
mock = create_app()


async def app(scope, receive, send):
    if scope["type"] == "http" and scope["path"] == "/__mutation":
        body = b""
        while True:
            m = await receive()
            body += m.get("body", b"")
            if not m.get("more_body"):
                break
        mock.set_mutation(json.loads(body)["name"])
        out = json.dumps({"mutation": mock.mutation}).encode()
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": out})
        return
    await mock(scope, receive, send)


uvicorn.run(app, host="127.0.0.1", port=A.port, log_level="warning")
