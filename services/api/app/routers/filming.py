import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import FilmingGuide
from app.schemas import FilmingGuideOut

router = APIRouter(prefix="/filming-guides", tags=["filming"])


@router.get("/{skill_id}", response_model=list[FilmingGuideOut])
def get_filming_guides(skill_id: int, db: Session = Depends(get_db)):
    guides = (
        db.query(FilmingGuide).filter(FilmingGuide.skill_id == skill_id).all()
    )
    if not guides:
        raise HTTPException(status_code=404, detail="该技能暂无拍摄引导")
    result = []
    for g in guides:
        checklist: list[str] = []
        if g.checklist_json:
            try:
                checklist = json.loads(g.checklist_json)
            except json.JSONDecodeError:
                checklist = []
        result.append(
            FilmingGuideOut(
                id=g.id,
                skill_id=g.skill_id,
                camera_angle=g.camera_angle,
                distance_hint=g.distance_hint,
                height_hint=g.height_hint,
                orientation=g.orientation,
                full_body_required=bool(g.full_body_required),
                racket_visible=bool(g.racket_visible),
                lighting_notes=g.lighting_notes,
                checklist=checklist,
                source=g.source,
                verification_status=g.verification_status,
            )
        )
    return result
