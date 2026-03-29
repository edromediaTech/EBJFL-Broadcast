"""Système d'authentification et d'autorisation pour EBJFL-Broadcast.

Rôles:
  - admin: Accès complet (import, suppression, config OBS, gestion users)
  - operator: Projection, chants, LT, planning, media, sous-titres
  - guest: Upload uniquement (page QR code)

Le desktop PyQt6 bypass l'auth (accès local direct).
"""

import hashlib
import hmac
import json
import time
from functools import wraps

from fastapi import Request, HTTPException, Depends, WebSocket
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from core.db.models import get_db

# ── Secret key for JWT-like tokens ──
SECRET_KEY = "ebjfl-broadcast-2026-secret-key"
TOKEN_EXPIRY = 86400 * 7  # 7 jours

security = HTTPBearer(auto_error=False)


# ── Password hashing ──

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed


# ── Token generation (simple HMAC-based, no external deps) ──

def create_token(user_id: int, username: str, role: str) -> str:
    payload = {
        "uid": user_id,
        "user": username,
        "role": role,
        "exp": int(time.time()) + TOKEN_EXPIRY,
    }
    data = json.dumps(payload, separators=(",", ":"))
    sig = hmac.new(SECRET_KEY.encode(), data.encode(), hashlib.sha256).hexdigest()[:16]
    # Simple base64-like encoding (no padding issues)
    import base64
    token = base64.urlsafe_b64encode(data.encode()).decode() + "." + sig
    return token


def decode_token(token: str) -> dict | None:
    try:
        parts = token.rsplit(".", 1)
        if len(parts) != 2:
            return None
        import base64
        data = base64.urlsafe_b64decode(parts[0]).decode()
        sig = hmac.new(SECRET_KEY.encode(), data.encode(), hashlib.sha256).hexdigest()[:16]
        if sig != parts[1]:
            return None
        payload = json.loads(data)
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


# ── User CRUD ──

def authenticate_user(username: str, password: str) -> dict | None:
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ? AND is_active = 1", (username,)
    ).fetchone()
    conn.close()
    if not user:
        return None
    if verify_password(password, user["password_hash"]):
        return dict(user)
    return None


def authenticate_by_pin(pin: str) -> dict | None:
    conn = get_db()
    pin_hash = hash_password(pin)
    user = conn.execute(
        "SELECT * FROM users WHERE pin = ? AND is_active = 1", (pin_hash,)
    ).fetchone()
    conn.close()
    if user:
        return dict(user)
    return None


def get_user(user_id: int) -> dict | None:
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None


def list_users() -> list[dict]:
    conn = get_db()
    rows = conn.execute("SELECT id, username, display_name, role, is_active, created_at, last_login FROM users ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_user(username: str, display_name: str, password: str, role: str = "operator", pin: str = "") -> int:
    if role not in ("admin", "operator", "presenter", "guest"):
        raise ValueError(f"Rôle invalide: {role}")
    conn = get_db()
    pwd_hash = hash_password(password)
    pin_hash = hash_password(pin) if pin else ""
    conn.execute(
        "INSERT INTO users (username, display_name, password_hash, pin, role) VALUES (?, ?, ?, ?, ?)",
        (username, display_name, pwd_hash, pin_hash, role)
    )
    uid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    return uid


def update_user(user_id: int, **fields) -> bool:
    conn = get_db()
    updates = {}
    if "display_name" in fields:
        updates["display_name"] = fields["display_name"]
    if "role" in fields and fields["role"] in ("admin", "operator", "presenter", "guest"):
        updates["role"] = fields["role"]
    if "is_active" in fields:
        updates["is_active"] = 1 if fields["is_active"] else 0
    if "password" in fields and fields["password"]:
        updates["password_hash"] = hash_password(fields["password"])
    if "pin" in fields:
        updates["pin"] = hash_password(fields["pin"]) if fields["pin"] else ""
    if not updates:
        return False
    sql = "UPDATE users SET " + ", ".join(f"{k}=?" for k in updates) + " WHERE id=?"
    conn.execute(sql, [*updates.values(), user_id])
    conn.commit()
    conn.close()
    return True


def delete_user(user_id: int) -> bool:
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id = ? AND role != 'admin'", (user_id,))
    conn.commit()
    conn.close()
    return True


def update_last_login(user_id: int):
    conn = get_db()
    conn.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


# ── FastAPI Dependencies ──

def _extract_token(request: Request) -> dict | None:
    """Extrait et decode le token depuis le header ou le cookie."""
    # Header Authorization: Bearer <token>
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return decode_token(auth[7:])
    # Cookie fallback
    token = request.cookies.get("ebjfl_token")
    if token:
        return decode_token(token)
    # Query param fallback (for WebSocket)
    token = request.query_params.get("token")
    if token:
        return decode_token(token)
    return None


def _is_local_request(request: Request) -> bool:
    """Vérifie si la requête vient du PC local (desktop PyQt6)."""
    client = request.client
    if not client:
        return False
    host = client.host
    return host in ("127.0.0.1", "::1", "localhost")


async def get_current_user(request: Request) -> dict:
    """Dépendance FastAPI : retourne l'utilisateur courant ou lève 401.
    Les requêtes locales (127.0.0.1) sont automatiquement admin.
    """
    # Desktop bypass : requêtes locales = admin
    if _is_local_request(request):
        return {"id": 0, "username": "local", "role": "admin", "display_name": "PC Régie"}

    payload = _extract_token(request)
    if not payload:
        raise HTTPException(status_code=401, detail="Non authentifié")
    return {"id": payload["uid"], "username": payload["user"], "role": payload["role"]}


async def get_optional_user(request: Request) -> dict | None:
    """Comme get_current_user mais retourne None au lieu de 401."""
    if _is_local_request(request):
        return {"id": 0, "username": "local", "role": "admin", "display_name": "PC Régie"}
    payload = _extract_token(request)
    if payload:
        return {"id": payload["uid"], "username": payload["user"], "role": payload["role"]}
    return None


def require_role(*roles):
    """Dépendance FastAPI : vérifie que l'utilisateur a le bon rôle."""
    async def checker(user: dict = Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail=f"Rôle requis: {', '.join(roles)}")
        return user
    return checker


# Shortcuts
require_admin = require_role("admin")
require_operator = require_role("admin", "operator")
require_presenter = require_role("admin", "operator", "presenter")
require_any = require_role("admin", "operator", "guest")


# ── WebSocket Auth ──

async def authenticate_ws(websocket: WebSocket) -> dict | None:
    """Authentifie une connexion WebSocket.
    Local = admin. Sinon, check token en query param.
    """
    client = websocket.client
    if client and client.host in ("127.0.0.1", "::1", "localhost"):
        return {"id": 0, "username": "local", "role": "admin"}

    token = websocket.query_params.get("token")
    if token:
        payload = decode_token(token)
        if payload:
            return {"id": payload["uid"], "username": payload["user"], "role": payload["role"]}

    # Allow unauthenticated WebSocket for now (read-only overlay)
    return {"id": -1, "username": "anonymous", "role": "guest"}


# ── Permissions par endpoint ──

ROLE_PERMISSIONS = {
    "admin": "*",  # tout
    "operator": {
        # Projection
        "projection", "obs", "subtitles", "songs", "bible", "lower-thirds",
        "services", "texts", "themes", "screens", "media", "upload-media",
        "background", "alert", "clock", "songbooks", "status",
    },
    "presenter": {
        # Présentateur/invité : navigation slides, upload, projection limitée
        "media", "upload-media", "projection", "status",
    },
    "guest": {
        "upload-media", "status",
    },
}


def has_permission(role: str, endpoint_path: str) -> bool:
    """Vérifie si un rôle a accès à un endpoint."""
    perms = ROLE_PERMISSIONS.get(role)
    if perms == "*":
        return True
    if isinstance(perms, set):
        # Check if any permission keyword matches the path
        path_clean = endpoint_path.strip("/").split("/")[0]
        return path_clean in perms
    return False
