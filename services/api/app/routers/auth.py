from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.config import get_settings
from app.database import get_db
from app.models import User
from app.schemas import DevLoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/dev-login", response_model=TokenResponse)
def dev_login(body: DevLoginRequest, db: Session = Depends(get_db)):
    settings = get_settings()
    if not settings.allow_dev_login:
        raise HTTPException(status_code=403, detail="dev-login 已关闭")
    user = db.query(User).filter(User.openid == body.openid).first()
    if not user:
        user = User(openid=body.openid, nickname=body.nickname)
        db.add(user)
        db.commit()
        db.refresh(user)
    elif body.nickname and user.nickname != body.nickname:
        user.nickname = body.nickname
        db.commit()
        db.refresh(user)
    token = create_access_token(user.id, user.openid)
    return TokenResponse(
        access_token=token, user_id=user.id, nickname=user.nickname
    )
