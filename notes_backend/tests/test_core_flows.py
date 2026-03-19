import os

# Configure env BEFORE importing the app/settings.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DB_AUTO_CREATE"] = "true"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["CORS_ALLOW_ORIGINS"] = "http://localhost:3000"

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app


@pytest.mark.anyio
async def test_auth_and_notes_crud_and_tags():
    transport = ASGITransport(app=app, lifespan="on")
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register
        reg = await client.post(
            "/auth/register",
            json={"email": "alice@example.com", "password": "secret123"},
        )
        assert reg.status_code == 201, reg.text
        reg_payload = reg.json()
        assert "token" in reg_payload
        token = reg_payload["token"]

        headers = {"Authorization": f"Bearer {token}"}

        # Me
        me = await client.get("/auth/me", headers=headers)
        assert me.status_code == 200, me.text
        me_payload = me.json()
        assert me_payload["email"] == "alice@example.com"
        assert "id" in me_payload

        # Create note
        created = await client.post(
            "/notes",
            headers=headers,
            json={
                "title": "First",
                "content": "# Hello\n\nworld",
                "tags": ["Work", "urgent", "work"],
                "pinned": True,
                "favorite": False,
            },
        )
        assert created.status_code == 201, created.text
        note = created.json()
        assert note["title"] == "First"
        assert note["pinned"] is True
        assert set(note["tags"]) == {"work", "urgent"}
        note_id = note["id"]

        # List notes
        listed = await client.get("/notes", headers=headers)
        assert listed.status_code == 200, listed.text
        notes = listed.json()
        assert isinstance(notes, list)
        assert len(notes) == 1
        assert notes[0]["id"] == note_id

        # Search notes
        searched = await client.get("/notes", headers=headers, params={"q": "hello"})
        assert searched.status_code == 200
        assert len(searched.json()) == 1

        # Patch note (autosave-friendly)
        patched = await client.patch(
            f"/notes/{note_id}",
            headers=headers,
            json={"favorite": True, "tags": ["personal"]},
        )
        assert patched.status_code == 200, patched.text
        patched_note = patched.json()
        assert patched_note["favorite"] is True
        assert patched_note["tags"] == ["personal"]

        # Tags summary
        tags = await client.get("/tags", headers=headers)
        assert tags.status_code == 200, tags.text
        tags_payload = tags.json()
        assert {"name": "personal", "count": 1} in tags_payload

        # Delete note
        deleted = await client.delete(f"/notes/{note_id}", headers=headers)
        assert deleted.status_code == 204, deleted.text

        # List notes empty
        listed2 = await client.get("/notes", headers=headers)
        assert listed2.status_code == 200
        assert listed2.json() == []
