"""Read-only Motion Benchmark endpoints."""
from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import BadmintonSkill, BenchmarkVersion, MotionBenchmark
from app.schemas import (
    BenchmarkListItemOut,
    BenchmarkMetricOut,
    BenchmarkStageOut,
    BenchmarkVersionOut,
    BenchmarkDetailOut,
)

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


def _parse_json(raw: Optional[str]) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _version_out(ver: BenchmarkVersion) -> BenchmarkVersionOut:
    return BenchmarkVersionOut(
        id=ver.id,
        version_label=ver.version_label,
        status=ver.status,
        verification_status=ver.verification_status,
        source=ver.source,
        change_log=ver.change_log,
        published_at=ver.published_at,
        created_at=ver.created_at,
        stages=[
            BenchmarkStageOut(
                code=s.code, name=s.name, sort_order=s.sort_order
            )
            for s in (ver.stages or [])
        ],
        metrics=[
            BenchmarkMetricOut(
                id=m.metric_id,
                name=m.name,
                unit=m.unit,
                stage_code=m.stage_code,
                range_min=m.range_min,
                range_max=m.range_max,
                notes=m.notes,
            )
            for m in (ver.metrics or [])
        ],
        package=_parse_json(ver.package_json),
    )


@router.get("", response_model=list[BenchmarkListItemOut])
def list_benchmarks(db: Session = Depends(get_db)):
    rows = (
        db.query(MotionBenchmark)
        .options(joinedload(MotionBenchmark.skill), joinedload(MotionBenchmark.versions))
        .all()
    )
    out: list[BenchmarkListItemOut] = []
    for bm in rows:
        published = [v for v in bm.versions if v.status == "published"]
        latest = max(bm.versions, key=lambda v: v.id) if bm.versions else None
        out.append(
            BenchmarkListItemOut(
                skill_id=bm.skill_id,
                skill_code=bm.skill.code if bm.skill else "",
                skill_name=bm.skill.name if bm.skill else bm.name,
                benchmark_id=bm.id,
                name=bm.name,
                handedness=bm.handedness,
                camera_view=bm.camera_view,
                verification_status=bm.verification_status,
                source=bm.source,
                has_published_version=bool(published),
                published_version_label=published[0].version_label if published else None,
                latest_version_label=latest.version_label if latest else None,
                latest_version_status=latest.status if latest else None,
            )
        )
    out.sort(key=lambda x: x.skill_code)
    return out


@router.get("/{skill_code}", response_model=BenchmarkDetailOut)
def get_benchmark(skill_code: str, db: Session = Depends(get_db)):
    skill = (
        db.query(BadmintonSkill).filter(BadmintonSkill.code == skill_code).one_or_none()
    )
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")
    bm = (
        db.query(MotionBenchmark)
        .options(
            joinedload(MotionBenchmark.versions).joinedload(BenchmarkVersion.stages),
            joinedload(MotionBenchmark.versions).joinedload(BenchmarkVersion.metrics),
        )
        .filter(MotionBenchmark.skill_id == skill.id)
        .one_or_none()
    )
    if not bm:
        raise HTTPException(status_code=404, detail="尚无 motion_benchmark")

    published = next((v for v in bm.versions if v.status == "published"), None)
    # Prefer showing published package; else latest draft (honest about status)
    focus = published or (max(bm.versions, key=lambda v: v.id) if bm.versions else None)
    return BenchmarkDetailOut(
        skill_id=skill.id,
        skill_code=skill.code,
        skill_name=skill.name,
        benchmark_id=bm.id,
        name=bm.name,
        handedness=bm.handedness,
        camera_view=bm.camera_view,
        notes=bm.notes,
        verification_status=bm.verification_status,
        source=bm.source,
        has_published_version=published is not None,
        current=(_version_out(focus) if focus else None),
        notice=(
            "当前无已发布标准库版本；分析仍返回 ANALYSIS_NOT_IMPLEMENTED，不返回分数。"
            if published is None
            else "已发布版本仅供只读查阅；姿态评分流水线尚未接入。"
        ),
    )


@router.get("/{skill_code}/versions", response_model=list[BenchmarkVersionOut])
def list_versions(skill_code: str, db: Session = Depends(get_db)):
    skill = (
        db.query(BadmintonSkill).filter(BadmintonSkill.code == skill_code).one_or_none()
    )
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")
    bm = (
        db.query(MotionBenchmark)
        .options(
            joinedload(MotionBenchmark.versions).joinedload(BenchmarkVersion.stages),
            joinedload(MotionBenchmark.versions).joinedload(BenchmarkVersion.metrics),
        )
        .filter(MotionBenchmark.skill_id == skill.id)
        .one_or_none()
    )
    if not bm:
        raise HTTPException(status_code=404, detail="尚无 motion_benchmark")
    versions = sorted(bm.versions, key=lambda v: v.id, reverse=True)
    return [_version_out(v) for v in versions]
