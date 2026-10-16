from __future__ import annotations


async def test_normal_update_email_issues_no_readback(api, make_registry):
    registry = await make_registry()
    result = await registry.call(
        "update_email", {"user_id": "123", "email": "ada.new@example.com"}
    )
    assert not result.get("error")
    assert api.state()["users"]["123"]["email"] == "ada.new@example.com"
    # Read-back only runs for healed writes (AC-28 zero healthy-path overhead).
    # On a normal healthy write, only PATCH /users/email is issued, no /users/lookup read-back.
    lookups = [req for req in api.requests if req["path"] == "/users/lookup"]
    assert lookups == []
