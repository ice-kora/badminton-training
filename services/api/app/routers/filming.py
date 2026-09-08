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
        policy: dict = {}
        if g.precheck_policy_json:
            try:
                policy = json.loads(g.precheck_policy_json)
            except json.JSONDecodeError:
                policy = {}
        duration_range = policy.get(
            "duration_range_sec",
            [g.duration_min_sec or 5, g.duration_max_sec or 15],
        )
        required = policy.get(
            "required_checks",
            ["duration", "resolution", "brightness", "orientation"],
        )
        deferred = policy.get("deferred_checks", ["full_body", "distance"])
        client_items = policy.get(
            "client_checklist_items",
            ["full_body", "distance_ok", "racket_visible"],
        )
        min_short = policy.get("min_short_side", g.min_short_side or 720)
        min_bri = float(policy.get("min_brightness", g.min_brightness or 40))
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
                duration_range_sec=list(duration_range),
                min_resolution={"min_short_side": int(min_short)},
                brightness_policy={"min_mean_luminance": min_bri},
                required_checks=list(required),
                deferred_checks=list(deferred),
                client_checklist_items=list(client_items),
                source=g.source,
                verification_status=g.verification_status,
            )
        )
    return result
