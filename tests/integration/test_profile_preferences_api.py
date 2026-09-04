"""Integration tests for self-service Profile and Preferences persistence.

Covers:
- authentication (401 without token)
- profile display_name update + cross-request persistence
- strict request schemas (extra fields rejected, invalid theme rejected)
- preferences persist across requests/sessions
- roles/email are NOT editable through these endpoints
- /me reflects persisted preferences
"""

import pytest


@pytest.mark.asyncio
async def test_me_returns_safe_identity_with_default_preferences(async_client, auth_headers):
    res = await async_client.get("/api/v1/auth/me", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["email"] == "test_auth@example.com"
    assert body["roles"] == ["OPERATOR"]
    # Preferences are an additive safe field; default is empty/system
    assert "preferences" in body
    assert body["preferences"].get("theme", "system") == "system"
    # No secrets or authorization internals
    assert "password_hash" not in body
    assert "credential_version" not in body


@pytest.mark.asyncio
async def test_profile_endpoint_requires_authentication(async_client):
    res = await async_client.patch(
        "/api/v1/auth/profile",
        json={"display_name": "Hacker"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_update_profile_display_name_persists_across_requests(async_client, auth_headers):
    res = await async_client.patch(
        "/api/v1/auth/profile",
        json={"display_name": "Renamed Operator"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["display_name"] == "Renamed Operator"
    assert body["email"] == "test_auth@example.com"
    assert body["roles"] == ["OPERATOR"]

    # Separate request — must reflect the committed change
    me = await async_client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    assert me.json()["display_name"] == "Renamed Operator"


@pytest.mark.asyncio
async def test_update_profile_rejects_empty_name_and_extra_fields(async_client, auth_headers):
    res = await async_client.patch(
        "/api/v1/auth/profile",
        json={"display_name": ""},
        headers=auth_headers,
    )
    assert res.status_code == 422

    # Attempting to change roles/email through the profile endpoint is rejected
    res = await async_client.patch(
        "/api/v1/auth/profile",
        json={"display_name": "Fine Name", "roles": ["ADMIN"], "email": "evil@example.com"},
        headers=auth_headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_preferences_require_authentication(async_client):
    res = await async_client.get("/api/v1/auth/preferences")
    assert res.status_code == 401
    res = await async_client.put("/api/v1/auth/preferences", json={"theme": "dark"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_preferences_persist_across_requests(async_client, auth_headers):
    res = await async_client.put(
        "/api/v1/auth/preferences",
        json={"theme": "dark"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["theme"] == "dark"

    # Separate request
    res = await async_client.get("/api/v1/auth/preferences", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["theme"] == "dark"

    # /me also reflects the persisted preference (used by the frontend to
    # apply the theme on login)
    me = await async_client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.json()["preferences"]["theme"] == "dark"

    # Update again — server-authoritative write wins
    res = await async_client.put(
        "/api/v1/auth/preferences",
        json={"theme": "light"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    me = await async_client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.json()["preferences"]["theme"] == "light"


@pytest.mark.asyncio
async def test_preferences_reject_invalid_theme_and_extra_fields(async_client, auth_headers):
    res = await async_client.put(
        "/api/v1/auth/preferences",
        json={"theme": "neon"},
        headers=auth_headers,
    )
    assert res.status_code == 422

    res = await async_client.put(
        "/api/v1/auth/preferences",
        json={"theme": "dark", "role": "ADMIN"},
        headers=auth_headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_preferences_do_not_affect_roles(async_client, auth_headers):
    res = await async_client.put(
        "/api/v1/auth/preferences",
        json={"theme": "system"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    me = await async_client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.json()["roles"] == ["OPERATOR"]
    assert "ADMIN" not in me.json()["permissions"]