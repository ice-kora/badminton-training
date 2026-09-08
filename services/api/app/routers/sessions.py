from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import TrainingSession, User
from app.schemas import CheckInRequest, SessionOut

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/check-in", response_model=SessionOut)
def check_in(
    body: CheckInRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session_date = body.session_date or date.today()
    existing = (
        db.query(TrainingSession)
        .filter(
            TrainingSession.user_id == user.id,
            TrainingSession.session_date == session_date,
            TrainingSession.plan_day_id == body.plan_day_id,
        )
        .first()
    )
    if existing:
        existing.completed = 1
        existing.notes = body.notes or existing.notes
        existing.rating = body.rating if body.rating is not None else existing.rating
        if body.plan_id is not None:
            existing.plan_id = body.plan_id
        db.commit()
        db.refresh(existing)
        return SessionOut(
            id=existing.id,
            session_date=existing.session_date,
            plan_id=existing.plan_id,
            plan_day_id=existing.plan_day_id,
            completed=bool(existing.completed),
            notes=existing.notes,
            rating=existing.rating,
            created_at=existing.created_at,
        )

    row = TrainingSession(
        user_id=user.id,
        plan_id=body.plan_id,
        plan_day_id=body.plan_day_id,
        session_date=session_date,
        completed=1,
        notes=body.notes,
        rating=body.rating,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return SessionOut(
        id=row.id,
        session_date=row.session_date,
        plan_id=row.plan_id,
        plan_day_id=row.plan_day_id,
        completed=bool(row.completed),
        notes=row.notes,
        rating=row.rating,
        created_at=row.created_at,
    )


@router.get("", response_model=list[SessionOut])
def list_sessions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (
        db.query(TrainingSession)
        .filter(TrainingSession.user_id == user.id)
        .order_by(TrainingSession.session_date.desc(), TrainingSession.id.desc())
        .limit(100)
        .all()
    )
    return [
        SessionOut(
            id=r.id,
            session_date=r.session_date,
            plan_id=r.plan_id,
            plan_day_id=r.plan_day_id,
            completed=bool(r.completed),
            notes=r.notes,
            rating=r.rating,
            created_at=r.created_at,
        )
        for r in rows
    ]
