from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Path, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr

from .auth import (
    create_access_token,
    get_current_user_id,
    hash_password,
    verify_password,
)
from .database import get_db, init_db
from .email_service import send_edit_notification
from . import models

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(title="Perde API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class RegisterBody(BaseModel):
    email: EmailStr
    password: str
    display_name: str


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class StoryCreateBody(BaseModel):
    title: str


class StoryTitleBody(BaseModel):
    title: str


class CommitBody(BaseModel):
    content: str
    base_commit_id: Optional[int] = None


class ContributorBody(BaseModel):
    email: EmailStr


# ── Auth routes ───────────────────────────────────────────────────────────────

@app.post("/auth/register", status_code=201)
def register(body: RegisterBody):
    with get_db() as conn:
        if models.get_user_by_email(conn, body.email):
            raise HTTPException(status_code=409, detail="Email already registered")
        if len(body.password) < 6:
            raise HTTPException(status_code=422, detail="Password must be at least 6 characters")
        user = models.create_user(conn, body.email, hash_password(body.password), body.display_name)
        token = create_access_token(user["id"])
        return {"token": token, "user": _public_user(user)}


@app.post("/auth/login")
def login(body: LoginBody):
    with get_db() as conn:
        user = models.get_user_by_email(conn, body.email)
        if not user or not verify_password(body.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        token = create_access_token(user["id"])
        return {"token": token, "user": _public_user(user)}


@app.post("/auth/logout")
def logout():
    # JWT is stateless; client just discards the token
    return {"ok": True}


@app.get("/auth/me")
def me(user_id: int = Depends(get_current_user_id)):
    with get_db() as conn:
        user = models.get_user_by_id(conn, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return _public_user(user)


# ── Stories routes ────────────────────────────────────────────────────────────

@app.get("/stories")
def list_stories(user_id: int = Depends(get_current_user_id)):
    with get_db() as conn:
        return models.get_stories_for_user(conn, user_id)


@app.post("/stories", status_code=201)
def create_story(body: StoryCreateBody, user_id: int = Depends(get_current_user_id)):
    if not body.title.strip():
        raise HTTPException(status_code=422, detail="Title is required")
    with get_db() as conn:
        return models.create_story(conn, body.title.strip(), user_id)


@app.get("/stories/{story_id}")
def get_story(story_id: int, user_id: int = Depends(get_current_user_id)):
    with get_db() as conn:
        _assert_contributor(conn, story_id, user_id)
        story = models.get_story_by_id(conn, story_id, user_id)
        if not story:
            raise HTTPException(status_code=404, detail="Story not found")
        return story


@app.patch("/stories/{story_id}")
def update_story(story_id: int, body: StoryTitleBody, user_id: int = Depends(get_current_user_id)):
    with get_db() as conn:
        _assert_contributor(conn, story_id, user_id)
        if not body.title.strip():
            raise HTTPException(status_code=422, detail="Title is required")
        models.update_story_title(conn, story_id, body.title.strip())
        return models.get_story_by_id(conn, story_id, user_id)


@app.delete("/stories/{story_id}", status_code=204)
def delete_story(story_id: int, user_id: int = Depends(get_current_user_id)):
    with get_db() as conn:
        story = models.get_story_by_id(conn, story_id, user_id)
        if not story:
            raise HTTPException(status_code=404, detail="Story not found")
        if story["created_by"] != user_id:
            raise HTTPException(status_code=403, detail="Only the story creator can delete it")
        models.delete_story(conn, story_id)


# ── Commits routes ────────────────────────────────────────────────────────────

@app.get("/stories/{story_id}/commits")
def list_commits(story_id: int, user_id: int = Depends(get_current_user_id)):
    with get_db() as conn:
        _assert_contributor(conn, story_id, user_id)
        return models.get_commits(conn, story_id)


@app.post("/stories/{story_id}/commits", status_code=201)
async def create_commit(
    story_id: int,
    body: CommitBody,
    user_id: int = Depends(get_current_user_id),
):
    with get_db() as conn:
        _assert_contributor(conn, story_id, user_id)
        story = models.get_story_by_id(conn, story_id, user_id)
        if not story:
            raise HTTPException(status_code=404, detail="Story not found")

        latest_id = models.get_latest_commit_id(conn, story_id)
        if body.base_commit_id is not None and latest_id != body.base_commit_id:
            raise HTTPException(status_code=409, detail="Conflict: story was edited after you loaded it")

        commit = models.create_commit(conn, story_id, user_id, body.content)

        # Release any lock held by this user
        models.release_lock(conn, story_id, user_id)

        # Gather recipients for notification (all contributors except the editor)
        contributors = models.get_story_contributors(conn, story_id)
        editor = models.get_user_by_id(conn, user_id)
        recipients = [c for c in contributors if c["id"] != user_id]

    # Send notifications outside the DB transaction
    if recipients and editor:
        await send_edit_notification(
            story_id=story_id,
            story_title=story["title"],
            editor_name=editor["display_name"],
            recipients=recipients,
            content_preview=body.content,
            timestamp=commit["created_at"],
        )

    return commit


# ── Contributors routes ───────────────────────────────────────────────────────

@app.post("/stories/{story_id}/contributors", status_code=201)
def add_contributor(
    story_id: int,
    body: ContributorBody,
    user_id: int = Depends(get_current_user_id),
):
    with get_db() as conn:
        _assert_contributor(conn, story_id, user_id)
        new_user = models.get_user_by_email(conn, body.email)
        if not new_user:
            raise HTTPException(status_code=404, detail="No user found with that email")
        models.add_contributor(conn, story_id, new_user["id"])
        return _public_user(new_user)


@app.delete("/stories/{story_id}/contributors/{target_user_id}", status_code=204)
def remove_contributor(
    story_id: int,
    target_user_id: int,
    user_id: int = Depends(get_current_user_id),
):
    with get_db() as conn:
        _assert_contributor(conn, story_id, user_id)
        models.remove_contributor(conn, story_id, target_user_id)


# ── Edit lock routes ──────────────────────────────────────────────────────────

@app.get("/stories/{story_id}/lock")
def get_lock(story_id: int, user_id: int = Depends(get_current_user_id)):
    with get_db() as conn:
        _assert_contributor(conn, story_id, user_id)
        lock = models.get_lock(conn, story_id)
        return lock or {}


@app.post("/stories/{story_id}/lock", status_code=201)
def acquire_lock(story_id: int, user_id: int = Depends(get_current_user_id)):
    with get_db() as conn:
        _assert_contributor(conn, story_id, user_id)
        models.acquire_lock(conn, story_id, user_id)
        return {"ok": True}


@app.delete("/stories/{story_id}/lock", status_code=204)
def release_lock(story_id: int, user_id: int = Depends(get_current_user_id)):
    with get_db() as conn:
        _assert_contributor(conn, story_id, user_id)
        models.release_lock(conn, story_id, user_id)


# ── Static frontend serving ───────────────────────────────────────────────────

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def root():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    @app.get("/{page}.html")
    def serve_page(page: str):
        path = os.path.join(FRONTEND_DIR, f"{page}.html")
        if os.path.isfile(path):
            return FileResponse(path)
        raise HTTPException(status_code=404, detail="Page not found")

    @app.get("/style.css")
    def serve_css():
        return FileResponse(os.path.join(FRONTEND_DIR, "style.css"))

    @app.get("/app.js")
    def serve_js():
        return FileResponse(os.path.join(FRONTEND_DIR, "app.js"))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "created_at": user["created_at"],
    }


def _assert_contributor(conn, story_id: int, user_id: int):
    if not models.is_contributor(conn, story_id, user_id):
        raise HTTPException(status_code=403, detail="Access denied")
