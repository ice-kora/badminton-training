"""Rule-based training plans (not AI pose)."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import BadmintonSkill, Drill, TrainingPlan, TrainingPlanDay, User
from app.schemas import LevelTestRequest, PlanDayOut, PlanOut

router = APIRouter(prefix="/plans", tags=["plans"])

VALID_LEVELS = {"beginner", "intermediate", "advanced"}

# Rule templates: day_index -> (focus, skill_codes, drill_name_contains)
LEVEL_TEMPLATES: dict[str, list[tuple[str, list[str], str | None]]] = {
    "beginner": [
        ("热身 + 正手高远球基础架拍", ["forehand_clear"], "高远"),
        ("正手高远球挥拍节奏", ["forehand_clear"], "节奏"),
        ("休息日：技术回顾与拉伸", [], None),
        ("网前搓球接触点与手感", ["net_tumble"], "搓球"),
        ("正手杀球引拍与发力顺序（轻杀）", ["forehand_smash"], "杀球"),
        ("组合：高远→网前过渡", ["forehand_clear", "net_tumble"], None),
        ("复盘日：打卡回顾与薄弱点巩固", ["forehand_clear"], None),
    ],
    "intermediate": [
        ("正手高远球落点控制", ["forehand_clear"], "落点"),
        ("正手杀球节奏与 stepoff", ["forehand_smash"], "杀球"),
        ("网前搓球变线", ["net_tumble"], "搓球"),
        ("高远与杀球衔接", ["forehand_clear", "forehand_smash"], None),
        ("休息日：录像自查（仅拍摄引导，无姿态评分）", [], None),
        ("网前抢点与搓球质量", ["net_tumble"], "搓球"),
        ("综合复习与打卡总结", ["forehand_clear", "forehand_smash", "net_tumble"], None),
    ],
    "advanced": [
        ("高远球压迫落点与节奏变化", ["forehand_clear"], "落点"),
        ("杀球 stepoff 与 stepoff 后衔接", ["forehand_smash"], "杀球"),
        ("网前搓球假动作与节奏", ["net_tumble"], "搓球"),
        ("高远→杀球连续进攻组合", ["forehand_clear", "forehand_smash"], None),
        ("网前攻防转换", ["net_tumble"], "搓球"),
        ("技术薄弱点针对性 Drill", ["forehand_smash", "net_tumble"], None),
        ("周复盘与下周目标设定", [], None),
    ],
}


def _csv_ids(ids: list[int]) -> str:
    return ",".join(str(i) for i in ids)


def _parse_csv(s: str | None) -> list[int]:
    if not s:
        return []
    return [int(x) for x in s.split(",") if x.strip().isdigit()]


def _plan_to_out(plan: TrainingPlan) -> PlanOut:
    days = []
    for d in plan.days:
        days.append(
            PlanDayOut(
                id=d.id,
                day_index=d.day_index,
                focus=d.focus,
                drill_ids=_parse_csv(d.drill_ids_csv),
                skill_ids=_parse_csv(d.skill_ids_csv),
                notes=d.notes,
                duration_minutes=d.duration_minutes,
            )
        )
    return PlanOut(
        id=plan.id,
        title=plan.title,
        level=plan.level,
        start_date=plan.start_date,
        end_date=plan.end_date,
        status=plan.status,
        rationale=plan.rationale,
        days=days,
    )


@router.post("/level-test", response_model=PlanOut)
def level_test(
    body: LevelTestRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    level = body.level.strip().lower()
    if level not in VALID_LEVELS:
        raise HTTPException(
            status_code=400,
            detail=f"level 必须是 {sorted(VALID_LEVELS)} 之一",
        )

    # Deactivate previous active plans
    for p in db.query(TrainingPlan).filter(
        TrainingPlan.user_id == user.id, TrainingPlan.status == "active"
    ):
        p.status = "archived"

    user.level = level
    template = LEVEL_TEMPLATES[level]
    start = date.today()
    end = start + timedelta(days=6)

    skills_by_code = {
        s.code: s for s in db.query(BadmintonSkill).all()
    }
    drills = db.query(Drill).all()

    plan = TrainingPlan(
        user_id=user.id,
        title=f"7日{ {'beginner':'入门','intermediate':'进阶','advanced':'提高'}[level] }训练计划",
        level=level,
        start_date=start,
        end_date=end,
        status="active",
        rationale=(
            "规则引擎根据水平测试档位生成的 7 日模板计划；"
            "不是姿态分析或 AI 评分结果。内容块多为 draft_unverified，请结合教练指导。"
        ),
    )
    db.add(plan)
    db.flush()

    for idx, (focus, skill_codes, drill_kw) in enumerate(template, start=1):
        skill_ids = [
            skills_by_code[c].id for c in skill_codes if c in skills_by_code
        ]
        # Prefer preferred skills if provided
        for code in body.preferred_skill_codes:
            if code in skills_by_code and skills_by_code[code].id not in skill_ids:
                skill_ids.append(skills_by_code[code].id)

        drill_ids: list[int] = []
        if drill_kw:
            for d in drills:
                if drill_kw in d.name or (d.goal and drill_kw in d.goal):
                    if not skill_ids or d.skill_id in skill_ids or d.skill_id is None:
                        drill_ids.append(d.id)
            drill_ids = drill_ids[:3]
        elif skill_ids:
            drill_ids = [d.id for d in drills if d.skill_id in skill_ids][:2]

        day = TrainingPlanDay(
            plan_id=plan.id,
            day_index=idx,
            focus=focus,
            skill_ids_csv=_csv_ids(skill_ids) or None,
            drill_ids_csv=_csv_ids(drill_ids) or None,
            notes="按自身体能调整组数；动作以教练/已验证内容为准。",
            duration_minutes=25 if idx == 3 and level == "beginner" else 35,
        )
        db.add(day)

    db.commit()
    plan = (
        db.query(TrainingPlan)
        .options(joinedload(TrainingPlan.days))
        .filter(TrainingPlan.id == plan.id)
        .one()
    )
    return _plan_to_out(plan)


@router.get("/current", response_model=PlanOut)
def current_plan(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    plan = (
        db.query(TrainingPlan)
        .options(joinedload(TrainingPlan.days))
        .filter(TrainingPlan.user_id == user.id, TrainingPlan.status == "active")
        .order_by(TrainingPlan.id.desc())
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="暂无进行中的训练计划，请先完成水平测试")
    return _plan_to_out(plan)
