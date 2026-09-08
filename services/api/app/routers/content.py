from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CommonError, Drill, TipArticle
from app.schemas import CommonErrorOut, DrillOut, TipArticleOut

router = APIRouter(tags=["content"])


@router.get("/drills", response_model=list[DrillOut])
def list_drills(
    skill_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    q = db.query(Drill)
    if skill_id is not None:
        q = q.filter(Drill.skill_id == skill_id)
    return [DrillOut.model_validate(d) for d in q.order_by(Drill.id).all()]


@router.get("/errors", response_model=list[CommonErrorOut])
def list_errors(
    skill_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    q = db.query(CommonError)
    if skill_id is not None:
        q = q.filter(CommonError.skill_id == skill_id)
    return [CommonErrorOut.model_validate(e) for e in q.order_by(CommonError.id).all()]


@router.get("/tips", response_model=list[TipArticleOut])
def list_tips(db: Session = Depends(get_db)):
    rows = db.query(TipArticle).order_by(TipArticle.id.desc()).all()
    return [TipArticleOut.model_validate(t) for t in rows]
