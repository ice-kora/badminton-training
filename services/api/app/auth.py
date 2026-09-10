"""JWT helpers and optional Bearer dependency."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User

security = HTTPBearer(auto_error=False)


def create_access_token(user_id: int, openid: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "openid": openid, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_video_file_token(user_id: int, video_id: int) -> str:
    """Short-lived dedicated token for /videos/{id}/file?token= (not session JWT)."""
    settings = get_settings()
    minutes = max(1, int(settings.video_file_token_expire_minutes))
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {
        "sub": str(user_id),
        "vid": int(video_id),
        "purpose": "video_file",
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="无效或过期的令牌"
        ) from exc


def decode_video_file_token(token: str, *, video_id: int) -> dict:
    """Accept only purpose=video_file tokens bound to the given video_id."""
    payload = decode_token(token)
    if payload.get("purpose") != "video_file":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="视频文件需要短时专用令牌（不可使用会话 JWT 作为 query token）",
        )
    try:
        token_vid = int(payload.get("vid", -1))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的视频文件令牌"
        ) from exc
    if token_vid != int(video_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="视频文件令牌与资源不匹配"
        )
    return payload


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="需要登录（Authorization Bearer）"
        )
    payload = decode_token(creds.credentials)
    user_id = int(payload.get("sub", 0))
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


def get_optional_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if creds is None or not creds.credentials:
        return None
    try:
        payload = decode_token(creds.credentials)
        return db.get(User, int(payload.get("sub", 0)))
    except HTTPException:
        return None
