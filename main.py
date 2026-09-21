"""
Musikin — backend FastAPI
Search & stream audio dari YouTube pakai yt-dlp, plus riwayat & playlist.
Storage sederhana pakai file JSON (db.json) — cocok buat single-user / demo.
"""
import json
import os
import threading
import uuid
import hashlib
import secrets
from typing import Optional

import httpx
import yt_dlp
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Musikin API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Storage sederhana (file JSON) — history & playlist
# ---------------------------------------------------------------------------
DB_PATH = os.path.join(os.path.dirname(__file__), "db.json")
_db_lock = threading.Lock()


def _load_db() -> dict:
    if not os.path.exists(DB_PATH):
        return {"history": [], "playlists": []}
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_db(data: dict) -> None:
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------
class Track(BaseModel):
    id: str
    title: str
    artist: str = ""
    thumbnail: str = ""
    duration: int = 0  # detik


class PlaylistCreate(BaseModel):
    name: str


class PlaylistRename(BaseModel):
    name: str


class AddTrackToPlaylist(BaseModel):
    track: Track


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenRequest(BaseModel):
    token: str


# ---------------------------------------------------------------------------
# yt-dlp helper
# ---------------------------------------------------------------------------
YDL_SEARCH_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "extract_flat": "in_playlist",
    "skip_download": True,
    "default_search": "ytsearch",
}

YDL_STREAM_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "format": "bestaudio/best",
    "noplaylist": True,
}


def _search_youtube(query: str, limit: int = 20) -> list[dict]:
    with yt_dlp.YoutubeDL(YDL_SEARCH_OPTS) as ydl:
        info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
    results = []
    for entry in info.get("entries", []) or []:
        if not entry:
            continue
        results.append(
            {
                "id": entry.get("id"),
                "title": entry.get("title") or "Tanpa judul",
                "artist": entry.get("uploader") or entry.get("channel") or "",
                "thumbnail": (entry.get("thumbnails") or [{}])[-1].get("url", ""),
                "duration": int(entry.get("duration") or 0),
            }
        )
    return results


def _get_audio_stream_url(video_id: str) -> tuple[str, dict, str]:
    with yt_dlp.YoutubeDL(YDL_STREAM_OPTS) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
    url = info["url"]
    headers = info.get("http_headers", {}) or {}
    ext = info.get("ext") or "m4a"
    return url, headers, ext


# yt-dlp sering ngambil audio terbaik dalam format webm/opus, bukan cuma
# mp4/m4a — kalau Content-Type yang dikirim gak sesuai format aslinya,
# player di app (just_audio/ExoPlayer) gagal baca ("Source error").
_AUDIO_MIME_BY_EXT = {
    "m4a": "audio/mp4",
    "mp4": "audio/mp4",
    "webm": "audio/webm",
    "opus": "audio/ogg",
    "ogg": "audio/ogg",
    "mp3": "audio/mpeg",
}


# ---------------------------------------------------------------------------
# Routes — search & stream
# ---------------------------------------------------------------------------
@app.get("/api/search")
def search(q: str, limit: int = 20):
    if not q.strip():
        raise HTTPException(400, "Query kosong")
    try:
        return {"results": _search_youtube(q, limit)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Gagal search: {e}") from e


@app.get("/api/stream/{video_id}")
async def stream(video_id: str):
    try:
        url, extra_headers, ext = _get_audio_stream_url(video_id)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Gagal ambil stream: {e}") from e

    headers = {"User-Agent": "Mozilla/5.0"}
    headers.update(extra_headers)

    media_type = _AUDIO_MIME_BY_EXT.get(ext, "audio/mp4")

    async def proxy():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", url, headers=headers) as resp:
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    yield chunk

    return StreamingResponse(proxy(), media_type=media_type)


# ---------------------------------------------------------------------------
# Routes — riwayat ("Baru diputar")
# ---------------------------------------------------------------------------
@app.get("/api/history")
def get_history():
    db = _load_db()
    return {"history": db.get("history", [])}


@app.post("/api/history")
def add_history(track: Track):
    with _db_lock:
        db = _load_db()
        history = [t for t in db.get("history", []) if t["id"] != track.id]
        history.insert(0, track.model_dump())
        db["history"] = history[:50]
        _save_db(db)
    return {"history": db["history"]}


@app.delete("/api/history")
def clear_history():
    with _db_lock:
        db = _load_db()
        db["history"] = []
        _save_db(db)
    return {"history": []}


# ---------------------------------------------------------------------------
# Routes — playlist
# ---------------------------------------------------------------------------
@app.get("/api/playlists")
def list_playlists():
    db = _load_db()
    return {"playlists": db.get("playlists", [])}


@app.post("/api/playlists")
def create_playlist(body: PlaylistCreate):
    with _db_lock:
        db = _load_db()
        playlist = {"id": str(uuid.uuid4()), "name": body.name, "tracks": []}
        db.setdefault("playlists", []).append(playlist)
        _save_db(db)
    return playlist


@app.put("/api/playlists/{playlist_id}")
def rename_playlist(playlist_id: str, body: PlaylistRename):
    with _db_lock:
        db = _load_db()
        for p in db.get("playlists", []):
            if p["id"] == playlist_id:
                p["name"] = body.name
                _save_db(db)
                return p
    raise HTTPException(404, "Playlist tidak ditemukan")


@app.delete("/api/playlists/{playlist_id}")
def delete_playlist(playlist_id: str):
    with _db_lock:
        db = _load_db()
        db["playlists"] = [p for p in db.get("playlists", []) if p["id"] != playlist_id]
        _save_db(db)
    return {"ok": True}


@app.post("/api/playlists/{playlist_id}/tracks")
def add_track_to_playlist(playlist_id: str, body: AddTrackToPlaylist):
    with _db_lock:
        db = _load_db()
        for p in db.get("playlists", []):
            if p["id"] == playlist_id:
                if not any(t["id"] == body.track.id for t in p["tracks"]):
                    p["tracks"].append(body.track.model_dump())
                _save_db(db)
                return p
    raise HTTPException(404, "Playlist tidak ditemukan")


@app.delete("/api/playlists/{playlist_id}/tracks/{track_id}")
def remove_track_from_playlist(playlist_id: str, track_id: str):
    with _db_lock:
        db = _load_db()
        for p in db.get("playlists", []):
            if p["id"] == playlist_id:
                p["tracks"] = [t for t in p["tracks"] if t["id"] != track_id]
                _save_db(db)
                return p
    raise HTTPException(404, "Playlist tidak ditemukan")


# ---------------------------------------------------------------------------
# Auth — akun (Nama + Sandi) disimpan di db.json yang sama, jadi TIDAK
# hilang lagi walau app di-uninstall / ganti HP. Sandi disimpan sebagai
# hash (PBKDF2-SHA256 + salt per akun), bukan plain text.
# ---------------------------------------------------------------------------
def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), 100_000
    ).hex()


def _normalize_username(username: str) -> str:
    return username.strip().lower()


@app.post("/api/auth/register")
def register(body: RegisterRequest):
    username = body.username.strip()
    key = _normalize_username(username)
    password = body.password

    if not key:
        raise HTTPException(400, "Nama tidak boleh kosong")
    if len(password) < 4:
        raise HTTPException(400, "Sandi minimal 4 karakter")

    with _db_lock:
        db = _load_db()
        users = db.setdefault("users", {})
        if key in users:
            raise HTTPException(409, f'Nama "{username}" sudah dipakai. Coba nama lain.')

        salt = secrets.token_hex(16)
        token = secrets.token_hex(24)
        users[key] = {
            "username": username,
            "salt": salt,
            "hash": _hash_password(password, salt),
        }
        db.setdefault("sessions", {})[token] = key
        _save_db(db)

    return {"username": username, "token": token}


@app.post("/api/auth/login")
def login(body: LoginRequest):
    key = _normalize_username(body.username)

    with _db_lock:
        db = _load_db()
        user = db.get("users", {}).get(key)
        if not user or _hash_password(body.password, user["salt"]) != user["hash"]:
            raise HTTPException(401, "Nama atau sandi salah")

        token = secrets.token_hex(24)
        db.setdefault("sessions", {})[token] = key
        _save_db(db)

    return {"username": user["username"], "token": token}


@app.get("/api/auth/me")
def auth_me(token: str):
    db = _load_db()
    key = db.get("sessions", {}).get(token)
    user = db.get("users", {}).get(key) if key else None
    if not user:
        raise HTTPException(401, "Sesi tidak valid, silakan masuk lagi")
    return {"username": user["username"]}


@app.post("/api/auth/logout")
def logout(body: TokenRequest):
    with _db_lock:
        db = _load_db()
        db.get("sessions", {}).pop(body.token, None)
        _save_db(db)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Static frontend (harus di-mount PALING TERAKHIR biar ga nimpa /api/*)
# ---------------------------------------------------------------------------
app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True), name="static")
