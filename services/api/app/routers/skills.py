from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import BadmintonSkill, SkillCategory
from app.schemas import CategoryTreeOut, SkillBriefOut, SkillDetailOut, SkillTreeOut

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("/tree", response_model=SkillTreeOut)
def skill_tree(db: Session = Depends(get_db)):
    cats = (
        db.query(SkillCategory)
        .options(joinedload(SkillCategory.skills))
        .order_by(SkillCategory.sort_order)
        .all()
    )
    out = []
    for c in cats:
        skills = sorted(c.skills, key=lambda s: s.sort_order)
        out.append(
            CategoryTreeOut(
                id=c.id,
                code=c.code,
                name=c.name,
                description=c.description,
                sort_order=c.sort_order,
                skills=[SkillBriefOut.model_validate(s) for s in skills],
            )
        )
    return SkillTreeOut(categories=out)


@router.get("/{skill_id}", response_model=SkillDetailOut)
def skill_detail(skill_id: int, db: Session = Depends(get_db)):
    skill = (
        db.query(BadmintonSkill)
        .options(
            joinedload(BadmintonSkill.stages),
            joinedload(BadmintonSkill.content_blocks),
        )
        .filter(BadmintonSkill.id == skill_id)
        .first()
    )
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")
    return SkillDetailOut.model_validate(skill)
