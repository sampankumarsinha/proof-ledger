"""JWT auth (Bearer token), bcrypt hashing, RBAC, multi-tenant scoping."""
import os
import uuid
from datetime import datetime, timezone, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request

from .db import get_db

JWT_ALGORITHM = "HS256"
ACCESS_TTL_HOURS = 12

# Role hierarchy for permission checks
ROLE_LEVEL = {"VIEWER": 1, "ANALYST": 2, "ADMIN": 3, "OWNER": 4}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _secret() -> str:
    return os.environ["JWT_SECRET"]


def create_access_token(user_id: str, email: str, org_id: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "org": org_id,
        "role": role,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(hours=ACCESS_TTL_HOURS),
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


async def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else None
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session token.")
    db = get_db()
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_role(min_role: str):
    """Dependency factory enforcing a minimum RBAC level (server-side)."""
    async def checker(user: dict = Depends(get_current_user)) -> dict:
        if ROLE_LEVEL.get(user.get("role", "VIEWER"), 0) < ROLE_LEVEL[min_role]:
            raise HTTPException(
                status_code=403,
                detail=f"Requires {min_role} role. Your role: {user.get('role')}",
            )
        return user
    return checker


def new_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
