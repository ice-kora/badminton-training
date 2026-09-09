"""Motion benchmark package load / validate / DB helpers.

Hard rule: do not invent verified joint-angle ranges.
Numeric range_* with verification_status=draft_unverified fails unless allowed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

REQUIRED_TOP = (
    "skill_code",
    "version",
    "handedness",
    "camera_view",
    "stages",
    "keyframes",
    "metrics",
    "common_error_refs",
    "linked_drill_codes",
    "verification_status",
    "source",
)

ALLOWED_STATUS = frozenset({"draft_unverified", "expert_pending", "verified"})
ALLOWED_HANDEDNESS = frozenset({"left", "right", "either", None})


class BenchmarkValidationError(ValueError):
    """Package failed structural or policy validation."""


def load_package(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    raw = p.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise BenchmarkValidationError("package root must be a JSON object")
    return data


def _has_numeric_range(metric: dict[str, Any]) -> bool:
    for key in ("range_min", "range_max"):
        val = metric.get(key, None)
        if val is not None:
            return True
    return False


def validate_package(
    data: dict[str, Any],
    *,
    allow_unverified_numbers: bool = False,
) -> list[str]:
    """
    Validate package. Returns list of warnings (empty if clean).
    Raises BenchmarkValidationError on hard failures.
    """
    errors: list[str] = []
    warnings: list[str] = []

    for key in REQUIRED_TOP:
        if key not in data:
            errors.append(f"missing required field: {key}")
    if errors:
        raise BenchmarkValidationError("; ".join(errors))

    status = data.get("verification_status")
    if status not in ALLOWED_STATUS:
        errors.append(f"invalid verification_status: {status!r}")

    if not isinstance(data.get("skill_code"), str) or not data["skill_code"]:
        errors.append("skill_code must be non-empty string")
    if not isinstance(data.get("version"), str) or not data["version"]:
        errors.append("version must be non-empty string")
    if not isinstance(data.get("source"), str) or not data["source"]:
        errors.append("source must be non-empty string")

    handed = data.get("handedness")
    if handed not in ALLOWED_HANDEDNESS:
        errors.append(f"handedness must be left|right|either|null, got {handed!r}")

    for list_key in ("stages", "keyframes", "metrics", "common_error_refs", "linked_drill_codes"):
        if not isinstance(data.get(list_key), list):
            errors.append(f"{list_key} must be an array")

    if errors:
        raise BenchmarkValidationError("; ".join(errors))

    for i, st in enumerate(data["stages"]):
        if not isinstance(st, dict) or not st.get("code") or not st.get("name"):
            errors.append(f"stages[{i}] needs code and name")

    for i, kf in enumerate(data["keyframes"]):
        if not isinstance(kf, dict) or not kf.get("code") or not kf.get("name"):
            errors.append(f"keyframes[{i}] needs code and name")

    for i, ref in enumerate(data["common_error_refs"]):
        if not isinstance(ref, dict) or not ref.get("id"):
            errors.append(f"common_error_refs[{i}] needs id")

    for i, code in enumerate(data["linked_drill_codes"]):
        if not isinstance(code, str) or not code:
            errors.append(f"linked_drill_codes[{i}] must be non-empty string")

    numeric_hits: list[str] = []
    for i, m in enumerate(data["metrics"]):
        if not isinstance(m, dict) or not m.get("id") or not m.get("name"):
            errors.append(f"metrics[{i}] needs id and name")
            continue
        if _has_numeric_range(m):
            numeric_hits.append(str(m.get("id")))

    if numeric_hits and status == "draft_unverified" and not allow_unverified_numbers:
        errors.append(
            "numeric range_min/range_max present while verification_status="
            "draft_unverified (ids: "
            + ", ".join(numeric_hits)
            + "). Keep ranges null, raise status to expert_pending/verified, "
            "or pass --allow-unverified-numbers."
        )
    elif numeric_hits and status == "draft_unverified" and allow_unverified_numbers:
        warnings.append(
            "allowing unverified numeric ranges under draft_unverified "
            f"(ids: {', '.join(numeric_hits)})"
        )
    elif numeric_hits and status == "expert_pending":
        warnings.append(
            "numeric ranges present with expert_pending — not publishable as verified yet"
        )

    if errors:
        raise BenchmarkValidationError("; ".join(errors))
    return warnings


def publish_allowed(
    verification_status: str,
    *,
    force_allow_draft: bool = False,
    force_allow_expert_pending: bool = False,
) -> tuple[bool, str]:
    """Return (ok, reason). Default: only verified may publish; draft always blocked."""
    if verification_status == "verified":
        return True, "verified"
    if verification_status == "expert_pending" and force_allow_expert_pending:
        return True, "forced expert_pending"
    if verification_status == "draft_unverified":
        if force_allow_draft:
            return True, "forced draft_unverified (dangerous)"
        return False, (
            "publish blocked: verification_status=draft_unverified "
            "(--force-draft-forbidden is the default policy)"
        )
    if verification_status == "expert_pending":
        return False, (
            "publish blocked: verification_status=expert_pending "
            "(use --force-expert-pending only after expert review workflow)"
        )
    return False, f"publish blocked: unknown status {verification_status!r}"


def assert_refs_exist_in_db(db, data: dict[str, Any]) -> None:
    """Ensure common_error_refs / linked_drill_codes match seeded codes (no invented refs)."""
    from app.models import CommonError, Drill

    err_codes = {
        c for (c,) in db.query(CommonError.code).filter(CommonError.code.isnot(None)).all()
    }
    drill_codes = {
        c for (c,) in db.query(Drill.code).filter(Drill.code.isnot(None)).all()
    }
    missing_err = []
    for i, ref in enumerate(data.get("common_error_refs") or []):
        rid = ref.get("id") if isinstance(ref, dict) else None
        if not rid or rid not in err_codes:
            missing_err.append(f"common_error_refs[{i}].id={rid!r}")
    missing_drill = []
    for i, code in enumerate(data.get("linked_drill_codes") or []):
        if not isinstance(code, str) or code not in drill_codes:
            missing_drill.append(f"linked_drill_codes[{i}]={code!r}")
    problems = missing_err + missing_drill
    if problems:
        raise BenchmarkValidationError(
            "package refs must use existing seed codes: " + "; ".join(problems)
        )


def import_package_to_db(db, data: dict[str, Any], *, change_log: Optional[str] = None):
    """Insert/update MotionBenchmark + draft BenchmarkVersion + stage/metric rows."""
    from app.models import (
        BadmintonSkill,
        BenchmarkMetric,
        BenchmarkStage,
        BenchmarkVersion,
        MotionBenchmark,
    )

    skill = (
        db.query(BadmintonSkill)
        .filter(BadmintonSkill.code == data["skill_code"])
        .one_or_none()
    )
    if skill is None:
        raise BenchmarkValidationError(
            f"skill_code {data['skill_code']!r} not found in badminton_skills"
        )
    assert_refs_exist_in_db(db, data)

    bm = (
        db.query(MotionBenchmark)
        .filter(MotionBenchmark.skill_id == skill.id)
        .one_or_none()
    )
    if bm is None:
        bm = MotionBenchmark(
            skill_id=skill.id,
            name=data.get("skill_name") or f"{data['skill_code']} benchmark",
            handedness=data.get("handedness"),
            camera_view=data.get("camera_view"),
            notes=data.get("notes"),
            metric_table_json=None,
            source=data.get("source") or "placeholder_shell",
            verification_status=data.get("verification_status") or "draft_unverified",
        )
        db.add(bm)
        db.flush()
    else:
        bm.handedness = data.get("handedness")
        bm.camera_view = data.get("camera_view")
        if data.get("notes"):
            bm.notes = data["notes"]
        bm.source = data.get("source") or bm.source
        bm.verification_status = data.get("verification_status") or bm.verification_status

    version_label = data["version"]
    existing = (
        db.query(BenchmarkVersion)
        .filter(
            BenchmarkVersion.benchmark_id == bm.id,
            BenchmarkVersion.version_label == version_label,
        )
        .one_or_none()
    )
    if existing is not None:
        if existing.status == "published":
            raise BenchmarkValidationError(
                f"version {version_label} already published; bump version to re-import"
            )
        ver = existing
        # replace children
        for row in list(ver.stages):
            db.delete(row)
        for row in list(ver.metrics):
            db.delete(row)
        db.flush()
    else:
        ver = BenchmarkVersion(benchmark_id=bm.id, version_label=version_label)
        db.add(ver)
        db.flush()

    ver.status = "draft"
    ver.verification_status = data["verification_status"]
    ver.source = data["source"]
    ver.package_json = json.dumps(data, ensure_ascii=False)
    ver.metrics_json = json.dumps(data.get("metrics") or [], ensure_ascii=False)
    ver.change_log = change_log or f"import package {data['skill_code']}@{version_label}"
    ver.published_at = None

    for st in data.get("stages") or []:
        db.add(
            BenchmarkStage(
                version_id=ver.id,
                code=st["code"],
                name=st["name"],
                sort_order=int(st.get("sort_order") or 0),
            )
        )
    for m in data.get("metrics") or []:
        db.add(
            BenchmarkMetric(
                version_id=ver.id,
                metric_id=m["id"],
                name=m["name"],
                unit=m.get("unit"),
                stage_code=m.get("stage_code"),
                range_min=m.get("range_min"),
                range_max=m.get("range_max"),
                notes=m.get("notes"),
            )
        )
    db.flush()
    return bm, ver


def find_published_version(db, skill_id: int):
    from app.models import BenchmarkVersion, MotionBenchmark

    return (
        db.query(BenchmarkVersion)
        .join(MotionBenchmark, BenchmarkVersion.benchmark_id == MotionBenchmark.id)
        .filter(
            MotionBenchmark.skill_id == skill_id,
            BenchmarkVersion.status == "published",
        )
        .order_by(BenchmarkVersion.published_at.desc(), BenchmarkVersion.id.desc())
        .first()
    )


def repo_root_from_here() -> Path:
    # services/api/app/services/benchmark_pkg.py -> repo root
    return Path(__file__).resolve().parents[4]


def default_schema_path() -> Path:
    return repo_root_from_here() / "docs" / "benchmark" / "schema.json"
