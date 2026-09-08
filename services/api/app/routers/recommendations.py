"""Rule-based recommendations — explicitly NOT pose/AI analysis."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import TrainingPlan, TrainingSession, User
from app.schemas import RecommendationOut

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


def _parse_csv(s: str | None) -> list[int]:
    if not s:
        return []
    return [int(x) for x in s.split(",") if x.strip().isdigit()]


@router.get("/what-to-practice-now", response_model=RecommendationOut)
def what_to_practice_now(
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
    sessions = (
        db.query(TrainingSession)
        .filter(TrainingSession.user_id == user.id)
        .order_by(TrainingSession.session_date.desc())
        .limit(30)
        .all()
    )
    checked_day_ids = {s.plan_day_id for s in sessions if s.plan_day_id}

    if not plan:
        return RecommendationOut(
            title="先完成水平测试",
            reason="尚无进行中的计划。请前往「训练」页完成水平测试，生成 7 日规则计划。",
            focus_today="完成水平测试",
            extras={"has_plan": False, "checkin_count": len(sessions)},
        )

    # Pick first unchecked plan day, else today's index by calendar
    days = sorted(plan.days, key=lambda d: d.day_index)
    target = None
    for d in days:
        if d.id not in checked_day_ids:
            target = d
            break
    if target is None:
        # All days checked — suggest review of last day
        target = days[-1] if days else None
        title = "本周计划已打卡完成"
        reason = (
            f"计划「{plan.title}」各日均已打卡。"
            "建议回顾薄弱技能内容块，或重新做水平测试生成下一周计划。"
            "说明：此推荐来自打卡规则，不是姿态评分。"
        )
    else:
        day_offset = (date.today() - plan.start_date).days + 1
        title = f"今日建议：{target.focus}"
        reason = (
            f"根据计划第 {target.day_index} 日（日历约第 {max(day_offset,1)} 日）"
            f"与已打卡 {len(checked_day_ids)} 次记录，规则引擎选出下一个未完成日。"
            "这不是 AI 姿态分析，也不产生动作分数。"
        )

    skill_ids = _parse_csv(target.skill_ids_csv) if target else []
    drill_ids = _parse_csv(target.drill_ids_csv) if target else []

    return RecommendationOut(
        title=title,
        reason=reason,
        skill_ids=skill_ids,
        drill_ids=drill_ids,
        focus_today=target.focus if target else None,
        extras={
            "has_plan": True,
            "plan_id": plan.id,
            "plan_day_id": target.id if target else None,
            "day_index": target.day_index if target else None,
            "checkin_count": len(sessions),
            "unchecked_days": sum(1 for d in days if d.id not in checked_day_ids),
        },
    )
