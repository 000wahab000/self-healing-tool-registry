"""Mock drift API: four operations, mutations M1-M8 / C1 switchable at runtime.

No `from __future__ import annotations`: handlers annotate their body with the model
chosen for the active mutation, and FastAPI needs real objects, not strings.

A mutation is a rebuilt FastAPI app. `MockApi` is the stable ASGI object that delegates to
the current one, so data, counters, the idempotency map and the request log survive rebuilds.
"""

import copy
import json
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

MUTATIONS = ("M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "C1")
SEED = {
    "users": {
        "123": {"name": "Ada", "email": "ada@example.com", "manager_id": None},
        "456": {"name": "Bob", "email": "bob@example.com", "manager_id": None},
    },
    "tickets": [],
}


class Strict(BaseModel):
    model_config = ConfigDict(strict=True)


class UserRef(Strict):
    user_id: str


class CustomerRef(Strict):  # M1
    customer_id: str


class Target(Strict):
    id: int


class TargetRef(Strict):  # M5
    target: Target


class UpdateEmail(Strict):
    user_id: str
    email: str


class UpdateEmailIntId(Strict):  # M2
    user_id: int
    email: str


class UpdateEmailAddress(Strict):  # M7: old `email` is not declared, so it is ignored
    user_id: str
    email_address: str | None = None


class SetManager(Strict):
    user_id: str = Field(description="ID of the user")
    manager_id: str = Field(description="ID of the manager")


class SetManagerRenamed(Strict):  # M6
    subject: str = Field(description="ID of the user whose manager is being set")
    supervisor: str = Field(description="User ID of the new manager")


class NewTicket(Strict):
    user_id: str
    title: str


class NewTicketPriority(NewTicket):  # M8
    priority: Literal["low", "medium", "high"]


class User(BaseModel):
    id: str
    name: str
    email: str


class UserEnvelope(BaseModel):  # M3
    data: User


class EmailOut(BaseModel):
    id: str
    email: str


class ManagerOut(BaseModel):
    id: str
    manager_id: str


class TicketOut(BaseModel):
    ticket_id: str
    user_id: str
    title: str


bearer = HTTPBearer(auto_error=False)


async def require_tenant(
    x_tenant_id: Annotated[str, Header(min_length=1)],
) -> None:  # M5
    pass


def build(api: "MockApi", mid: str | None) -> FastAPI:
    app = FastAPI(title="Mock API")

    async def require_bearer(
        creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ) -> None:  # M4
        if creds is None or creds.credentials != api.token:
            raise HTTPException(
                401, "Not authenticated", headers={"WWW-Authenticate": "Bearer"}
            )

    lookup_in = {"M1": CustomerRef, "M5": TargetRef}.get(mid, UserRef)
    email_in = {"M2": UpdateEmailIntId, "M7": UpdateEmailAddress}.get(mid, UpdateEmail)
    manager_in = SetManagerRenamed if mid == "M6" else SetManager
    ticket_in = NewTicketPriority if mid == "M8" else NewTicket

    @app.post(
        "/users/lookup",
        operation_id="get_user",
        response_model=UserEnvelope if mid == "M3" else User,
        dependencies=[Depends(require_tenant)] if mid == "M5" else [],
    )
    async def get_user(body: lookup_in):
        api.get_user_calls += 1
        if mid == "C1" and api.get_user_calls <= 2:
            raise HTTPException(503, "Service unavailable")
        uid = (
            body.customer_id
            if mid == "M1"
            else str(body.target.id)
            if mid == "M5"
            else body.user_id
        )
        user = {"id": uid, **api.user(uid)}
        return {"data": user} if mid == "M3" else user

    @app.patch("/users/email", operation_id="update_email", response_model=EmailOut)
    async def update_email(body: email_in):
        uid = str(body.user_id)
        user = api.user(uid)
        new = body.email_address if mid == "M7" else body.email
        if new is not None:
            user["email"] = new
        return {"id": uid, "email": user["email"]}

    @app.post("/users/manager", operation_id="set_manager", response_model=ManagerOut)
    async def set_manager(body: manager_in):
        uid, manager = (
            (body.subject, body.supervisor)
            if mid == "M6"
            else (body.user_id, body.manager_id)
        )
        user = api.user(uid)
        api.user(manager)
        user["manager_id"] = manager
        return {"id": uid, "manager_id": manager}

    @app.post(
        "/tickets",
        operation_id="create_ticket",
        response_model=TicketOut,
        dependencies=[Depends(require_bearer)] if mid == "M4" else [],
    )
    async def create_ticket(
        body: ticket_in, idempotency_key: Annotated[str | None, Header()] = None
    ):
        if idempotency_key in api.idempotency:
            return api.idempotency[idempotency_key]
        api.user(body.user_id)
        ticket = {"ticket_id": f"T-{len(api.data['tickets']) + 1}", **body.model_dump()}
        api.data["tickets"].append(ticket)
        if idempotency_key:
            api.idempotency[idempotency_key] = ticket
        return ticket

    return app


class MockApi:
    def __init__(self, token: str) -> None:
        self.token = token
        self.requests: list[dict] = []
        self.reset()

    def reset(self) -> None:
        self.data = copy.deepcopy(SEED)
        self.idempotency: dict[str, dict] = {}
        self.requests.clear()
        self.set_mutation(None)

    def set_mutation(self, mid: str | None) -> None:
        if mid is not None and mid not in MUTATIONS:
            raise ValueError(f"unknown mutation {mid!r}")
        self.get_user_calls = 0
        self.inner = build(self, mid)

    def state(self) -> dict:
        return copy.deepcopy(self.data)

    def user(self, uid: str) -> dict:
        if uid not in self.data["users"]:
            raise HTTPException(404, "User not found")
        return self.data["users"][uid]

    async def __call__(self, scope, receive, send) -> None:
        if (
            scope["type"] != "http"
        ):  # ponytail: lifespan reaches only the app current at the time
            return await self.inner(scope, receive, send)
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if message["type"] != "http.request" or not message.get("more_body"):
                break
        try:
            decoded = json.loads(body) if body else None
        except ValueError:
            decoded = None
        self.requests.append(
            {
                "method": scope["method"],
                "path": scope["path"],
                "body": decoded,
                # ponytail: repeated header names collapse to the last value
                "headers": {
                    k.decode("latin-1").lower(): v.decode("latin-1")
                    for k, v in scope["headers"]
                },
            }
        )
        replayed = False

        async def replay():
            nonlocal replayed
            if replayed:
                return await receive()
            replayed = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.inner(scope, replay, send)


def create_app(token: str = "test-token") -> MockApi:
    return MockApi(token)
