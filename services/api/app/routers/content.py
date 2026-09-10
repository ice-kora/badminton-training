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



@router.get("/drills/{code}", response_model=DrillOut)
def get_drill(code: str, db: Session = Depends(get_db)):
    row = db.query(Drill).filter(Drill.code == code).one_or_none()
    if row is None:
        # fallback by numeric id
        if code.isdigit():
            row = db.query(Drill).filter(Drill.id == int(code)).one_or_none()
    if row is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="drill_not_found")
    return DrillOut.model_validate(row)


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


# Static coaching-adjacent micro-tips for analysis wait UI (not scores).
WAIT_TIPS = [
    {"id": "wait_full_body", "text": "击球瞬间尽量全身入画，肩髋转体才便于图像平面测量。"},
    {"id": "wait_elbow_lead", "text": "高远球引拍时肘领先于拍头，避免「甩臂」代偿。"},
    {"id": "wait_recover", "text": "杀球落地后尽快回中，复测时对比脚步是否更稳。"},
    {"id": "wait_angle", "text": "竖屏、腰高、后斜约 45°——机位比「贴地仰拍」更利于肩胸识别。"},
    {"id": "wait_light", "text": "灯光均匀比分辨率更重要：暗球馆易漏关键点。"},
    {"id": "wait_one_focus", "text": "一次只练一个纠错点，两周后再拍对比，进步更清晰。"},
    {"id": "wait_hand_side", "text": "持拍手侧同向后斜放置手机，左手用户请镜像机位。"},
    {"id": "wait_short_clip", "text": "短视频 5–15 秒含一次完整击球即可，不必录整场。"},
]


@router.get("/tips/wait")
def wait_tips():
    """Short factual tips while analysis is polling — no fake scores."""
    return {"tips": WAIT_TIPS}
