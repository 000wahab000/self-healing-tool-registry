from __future__ import annotations

import argparse
import os
import sys
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from starlette.routing import Mount

from dashboard.app import create_app as create_dashboard_app
from healer import mcp_server

ROOT = Path(__file__).resolve().parent.parent


def create_app(args: argparse.Namespace) -> FastAPI:
    app = create_dashboard_app(
        args.db,
        mcp_port=args.port,
        upstream_config_path=getattr(args, "mcp_servers", None),
    )
    dashboard_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(dashboard_lifespan(app))
            registry = await stack.enter_async_context(
                mcp_server.registry_context(args)
            )
            app.state.dash.gateway = registry
            token = os.environ.get(args.token_env) if args.token_env else None
            if args.token_env and not token:
                raise ValueError(
                    "configured bearer-token environment variable is empty"
                )
            mcp_app = mcp_server.create_http_app(
                registry,
                host=args.host,
                bearer_token=token,
                allowed_hosts=args.allowed_host,
                allowed_origins=args.allowed_origin,
            )
            await stack.enter_async_context(mcp_app.router.lifespan_context(mcp_app))
            mount = Mount("/", app=mcp_app)
            app.router.routes.append(mount)
            try:
                yield
            finally:
                app.router.routes.remove(mount)

    app.router.lifespan_context = lifespan
    return app


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Serve the dashboard and MCP gateway together"
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--spec-path", default="/openapi.json")
    parser.add_argument("--tools", default=str(ROOT / "config/tools.json"))
    parser.add_argument("--db", default=os.environ.get("DB_PATH") or str(ROOT / "healer.db"))
    parser.add_argument("--mcp-servers", default=str(ROOT / "config/mcp_servers.json"))
    parser.add_argument(
        "--host",
        default=os.environ.get("HOST")
        or ("0.0.0.0" if "PORT" in os.environ else "127.0.0.1"),
    )
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT") or 8080))
    parser.add_argument("--token-env", default=os.environ.get("MCP_TOKEN_ENV"))
    parser.add_argument("--allowed-host", action="append")
    parser.add_argument("--allowed-origin", action="append")
    parser.add_argument("--repair", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args(argv)
    args.allowed_host = args.allowed_host or _env_list("MCP_ALLOWED_HOSTS")
    args.allowed_origin = args.allowed_origin or _env_list("MCP_ALLOWED_ORIGINS")
    return args


def _env_list(name: str) -> list[str] | None:
    values = [value.strip() for value in os.environ.get(name, "").split(",") if value.strip()]
    return values or None


def main(argv: list[str] | None = None) -> None:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)
    args = _arguments(argv)
    if not Path(args.db).is_absolute():
        args.db = str(ROOT / args.db)
    for field in ("tools", "mcp_servers"):
        if not Path(getattr(args, field)).is_absolute():
            setattr(args, field, str(ROOT / getattr(args, field)))
    sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
    uvicorn.run(create_app(args), host=args.host, port=args.port, workers=1)


if __name__ == "__main__":
    main()
