"""Hand-built operations()-shaped dicts: v1 and every mock-API mutation (contracts C2)."""

from __future__ import annotations

STR = {"type": "string"}
INT = {"type": "integer"}
HEADER_SOURCES = {"Authorization": "OAUTH_BEARER", "X-Tenant-Id": "TENANT_ID"}
CFG_KEYS = {"OAUTH_BEARER", "TENANT_ID"}


def obj(props: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "properties": props,
        "required": list(props) if required is None else required,
    }


def param(name: str, loc: str, schema: dict = STR, required: bool = True) -> dict:
    return {
        "name": name,
        "in": loc,
        "required": required,
        "schema": schema,
        "description": "",
    }


def make_op(
    op_id: str,
    method: str,
    path: str,
    body: dict | None,
    response: dict | None,
    params: list[dict] | None = None,
    security: list[str] | None = None,
) -> dict:
    return {
        "operation_id": op_id,
        "method": method,
        "path": path,
        "body_schema": body,
        "params": params or [],
        "security": security or [],
        "response_schema": response,
        "description": "",
    }


def doc(method: str, path: str, body: dict, **extra: dict) -> dict:
    return {
        "route": {"method": method, "path": path},
        "body": body,
        "query": {},
        "header": {},
        **extra,
    }


USER = obj({"id": STR, "name": STR, "email": STR})
IDEM = param("idempotency-key", "header", STR, required=False)

GET_USER = make_op("get_user", "POST", "/users/lookup", obj({"user_id": STR}), USER)
UPDATE_EMAIL = make_op(
    "update_email",
    "PATCH",
    "/users/email",
    obj({"user_id": STR, "email": STR}),
    obj({"id": STR, "email": STR}),
)
SET_MANAGER = make_op(
    "set_manager",
    "POST",
    "/users/manager",
    obj(
        {
            "user_id": {"type": "string", "description": "ID of the user"},
            "manager_id": {"type": "string", "description": "ID of the manager"},
        }
    ),
    obj({"id": STR, "manager_id": STR}),
)
CREATE_TICKET = make_op(
    "create_ticket",
    "POST",
    "/tickets",
    obj({"user_id": STR, "title": STR}),
    obj({"ticket_id": STR, "user_id": STR, "title": STR}),
    params=[IDEM],
)

GET_USER_DOC = doc("POST", "/users/lookup", {"user_id": "123"})
UPDATE_EMAIL_DOC = doc(
    "PATCH", "/users/email", {"user_id": "123", "email": "new@example.com"}
)
SET_MANAGER_DOC = doc("POST", "/users/manager", {"user_id": "123", "manager_id": "456"})
CREATE_TICKET_DOC = doc(
    "POST", "/tickets", {"user_id": "123", "title": "Email changed"}
)

# mutation id -> (v1 operation, mutated operation, base request document)
MUTATIONS: dict[str, tuple[dict, dict, dict]] = {
    "M1": (
        GET_USER,
        make_op("get_user", "POST", "/users/lookup", obj({"customer_id": STR}), USER),
        GET_USER_DOC,
    ),
    "M2": (
        UPDATE_EMAIL,
        make_op(
            "update_email",
            "PATCH",
            "/users/email",
            obj({"user_id": INT, "email": STR}),
            obj({"id": STR, "email": STR}),
        ),
        UPDATE_EMAIL_DOC,
    ),
    "M3": (
        GET_USER,
        make_op(
            "get_user",
            "POST",
            "/users/lookup",
            obj({"user_id": STR}),
            obj({"data": USER}),
        ),
        GET_USER_DOC,
    ),
    "M4": (
        CREATE_TICKET,
        make_op(
            "create_ticket",
            "POST",
            "/tickets",
            CREATE_TICKET["body_schema"],
            CREATE_TICKET["response_schema"],
            params=[IDEM],
            security=["bearer"],
        ),
        CREATE_TICKET_DOC,
    ),
    "M5": (
        GET_USER,
        make_op(
            "get_user",
            "POST",
            "/users/lookup",
            obj({"target": obj({"id": INT})}),
            USER,
            params=[param("x-tenant-id", "header")],
        ),
        GET_USER_DOC,
    ),
    "M6": (
        SET_MANAGER,
        make_op(
            "set_manager",
            "POST",
            "/users/manager",
            obj(
                {
                    "subject": {
                        "type": "string",
                        "description": "ID of the user whose manager is being set",
                    },
                    "supervisor": {
                        "type": "string",
                        "description": "User ID of the new manager",
                    },
                }
            ),
            SET_MANAGER["response_schema"],
        ),
        SET_MANAGER_DOC,
    ),
    "M7": (
        UPDATE_EMAIL,
        make_op(
            "update_email",
            "PATCH",
            "/users/email",
            obj(
                {
                    "user_id": STR,
                    "email_address": {"anyOf": [STR, {"type": "null"}]},
                },
                required=["user_id"],
            ),
            UPDATE_EMAIL["response_schema"],
        ),
        UPDATE_EMAIL_DOC,
    ),
    "M8": (
        CREATE_TICKET,
        make_op(
            "create_ticket",
            "POST",
            "/tickets",
            obj(
                {
                    "user_id": STR,
                    "title": STR,
                    "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                }
            ),
            CREATE_TICKET["response_schema"],
            params=[IDEM],
        ),
        CREATE_TICKET_DOC,
    ),
}
