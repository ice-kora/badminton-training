"""Motion benchmark package load / validate / DB helpers.

Hard rule: do not invent verified joint-angle ranges.
Numeric range_* with verification_status=draft_unverified fails unless allowed.
synthetic_demo packages may carry explicitly labeled synthetic ranges and publish
only with --allow-synthetic-demo.
literature_cited packages carry peer-reviewed extracted ranges (with citations)
and publish only with --allow-literature-cited — NOT coach sign-off.
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

ALLOWED_STATUS = frozenset(
    {
        "draft_unverified",
        "expert_pending",
        "verified",
        "synthetic_demo",
        "literature_cited",
    }
)
ALLOWED_HANDEDNESS = frozenset({"left", "right", "either", None})

SYNTHETIC_SOURCE = "engineering_synthetic_demo"
SYNTHETIC_BANNER = "非专家验证，仅供流水线演示"

LITERATURE_SOURCE = "peer_reviewed_literature"
LITERATURE_BANNER = "文献抽取区间（非教练现场标定）；用于替代 synthetic_demo 演示"
LITERATURE_RANGE_KINDS = frozenset(
    {
        "literature_mean_sd",
        "literature_point_tolerance",
        "literature_proxy_related_stroke",
    }
)


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


def is_synthetic_demo(data_or_status: Any) -> bool:
    if isinstance(data_or_status, dict):
        return data_or_status.get("verification_status") == "synthetic_demo"
    return data_or_status == "synthetic_demo"


def is_literature_cited(data_or_status: Any) -> bool:
    if isinstance(data_or_status, dict):
        return data_or_status.get("verification_status") == "literature_cited"
    return data_or_status == "literature_cited"


def benchmark_kind_for_status(verification_status: str) -> str:
    if verification_status == "synthetic_demo":
        return "synthetic_demo"
    if verification_status == "literature_cited":
        return "literature_cited"
    if verification_status == "verified":
        return "verified"
    return verification_status or "unknown"


def validate_package(
    data: dict[str, Any],
    *,
    allow_unverified_numbers: bool = False,
    allow_synthetic_demo: bool = False,
    allow_literature_cited: bool = False,
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

    for list_key in (
        "stages",
        "keyframes",
        "metrics",
        "common_error_refs",
        "linked_drill_codes",
    ):
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

    if status == "synthetic_demo":
        if not allow_synthetic_demo:
            errors.append(
                "verification_status=synthetic_demo requires --allow-synthetic-demo"
            )
        if data.get("source") != SYNTHETIC_SOURCE:
            errors.append(
                f"synthetic_demo source must be {SYNTHETIC_SOURCE!r}, "
                f"got {data.get('source')!r}"
            )
        banner = data.get("banner") or ""
        if SYNTHETIC_BANNER not in str(banner):
            warnings.append(
                f"synthetic_demo should set banner containing {SYNTHETIC_BANNER!r}"
            )

    if status == "literature_cited":
        if not allow_literature_cited:
            errors.append(
                "verification_status=literature_cited requires --allow-literature-cited"
            )
        if data.get("source") != LITERATURE_SOURCE:
            errors.append(
                f"literature_cited source must be {LITERATURE_SOURCE!r}, "
                f"got {data.get('source')!r}"
            )
        banner = data.get("banner") or ""
        if LITERATURE_BANNER not in str(banner):
            errors.append(
                f"literature_cited must set banner containing {LITERATURE_BANNER!r}"
            )

    numeric_hits: list[str] = []
    synthetic_range_ok: list[str] = []
    literature_range_ok: list[str] = []
    for i, m in enumerate(data["metrics"]):
        if not isinstance(m, dict) or not m.get("id") or not m.get("name"):
            errors.append(f"metrics[{i}] needs id and name")
            continue
        if _has_numeric_range(m):
            numeric_hits.append(str(m.get("id")))
            if status == "synthetic_demo":
                kind = m.get("range_kind")
                notes = str(m.get("notes") or "")
                if kind != "synthetic_demo" and "SYNTHETIC" not in notes.upper():
                    errors.append(
                        f"metrics[{i}] id={m.get('id')}: synthetic_demo package "
                        "numeric ranges must set range_kind=synthetic_demo "
                        "or notes containing SYNTHETIC"
                    )
                else:
                    synthetic_range_ok.append(str(m.get("id")))
            elif status == "literature_cited":
                kind = m.get("range_kind")
                if kind not in LITERATURE_RANGE_KINDS:
                    errors.append(
                        f"metrics[{i}] id={m.get('id')}: literature_cited numeric "
                        f"ranges require range_kind in {sorted(LITERATURE_RANGE_KINDS)}, "
                        f"got {kind!r}"
                    )
                cites = m.get("citations")
                if not isinstance(cites, list) or not cites:
                    errors.append(
                        f"metrics[{i}] id={m.get('id')}: literature_cited numeric "
                        "ranges require non-empty citations "
                        "[{title, doi_or_url, extracted, year}]"
                    )
                else:
                    cite_ok = True
                    for j, c in enumerate(cites):
                        if not isinstance(c, dict):
                            errors.append(
                                f"metrics[{i}].citations[{j}] must be an object"
                            )
                            cite_ok = False
                            continue
                        for req in ("title", "doi_or_url", "extracted", "year"):
                            if c.get(req) in (None, ""):
                                errors.append(
                                    f"metrics[{i}].citations[{j}] missing {req}"
                                )
                                cite_ok = False
                    if cite_ok and kind in LITERATURE_RANGE_KINDS:
                        literature_range_ok.append(str(m.get("id")))

    if status == "synthetic_demo" and not numeric_hits:
        warnings.append("synthetic_demo package has no numeric ranges")

    if numeric_hits and status == "draft_unverified" and not allow_unverified_numbers:
        errors.append(
            "numeric range_min/range_max present while verification_status="
            "draft_unverified (ids: "
            + ", ".join(numeric_hits)
            + "). Keep ranges null, raise status to expert_pending/verified, "
            "use synthetic_demo + --allow-synthetic-demo, "
            "literature_cited + --allow-literature-cited, "
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
    elif numeric_hits and status == "synthetic_demo" and allow_synthetic_demo:
        warnings.append(
            "synthetic_demo ranges accepted for pipeline demo only "
            f"(ids: {', '.join(synthetic_range_ok or numeric_hits)}); "
            + SYNTHETIC_BANNER
        )
    elif numeric_hits and status == "literature_cited" and allow_literature_cited:
        warnings.append(
            "literature_cited ranges accepted (not coach-verified) "
            f"(ids: {', '.join(literature_range_ok or numeric_hits)}); "
            + LITERATURE_BANNER
        )

    if errors:
        raise BenchmarkValidationError("; ".join(errors))
    return warnings


def publish_allowed(
    verification_status: str,
    *,
    force_allow_draft: bool = False,
    force_allow_expert_pending: bool = False,
    allow_synthetic_demo: bool = False,
    allow_literature_cited: bool = False,
) -> tuple[bool, str]:
    """Return (ok, reason). Default: only verified; demo/lit need flags; draft blocked."""
    if verification_status == "verified":
        return True, "verified"
    if verification_status == "synthetic_demo":
        if allow_synthetic_demo:
            return True, "synthetic_demo with --allow-synthetic-demo"
        return False, (
            "publish blocked: verification_status=synthetic_demo "
            "(pass --allow-synthetic-demo to publish demo package)"
        )
    if verification_status == "literature_cited":
        if allow_literature_cited:
            return True, "literature_cited with --allow-literature-cited"
        return False, (
            "publish blocked: verification_status=literature_cited "
            "(pass --allow-literature-cited to publish literature package)"
        )
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
        notes = m.get("notes")
        if m.get("range_kind"):
            extra = f"[range_kind={m['range_kind']}]"
            notes = f"{notes} {extra}".strip() if notes else extra
        if m.get("linked_error_id"):
            extra = f"[linked_error_id={m['linked_error_id']}]"
            notes = f"{notes} {extra}".strip() if notes else extra
        if m.get("citations"):
            extra = f"[citations={json.dumps(m['citations'], ensure_ascii=False)}]"
            notes = f"{notes} {extra}".strip() if notes else extra
        db.add(
            BenchmarkMetric(
                version_id=ver.id,
                metric_id=m["id"],
                name=m["name"],
                unit=m.get("unit"),
                stage_code=m.get("stage_code"),
                range_min=m.get("range_min"),
                range_max=m.get("range_max"),
                notes=notes,
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


def package_dict_from_version(ver) -> dict[str, Any]:
    if ver.package_json:
        try:
            data = json.loads(ver.package_json)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return {
        "skill_code": None,
        "version": ver.version_label,
        "verification_status": ver.verification_status,
        "source": ver.source,
        "metrics": json.loads(ver.metrics_json) if ver.metrics_json else [],
        "common_error_refs": [],
        "linked_drill_codes": [],
        "stages": [],
        "keyframes": [],
        "handedness": None,
        "camera_view": None,
    }


def repo_root_from_here() -> Path:
    return Path(__file__).resolve().parents[4]


def default_schema_path() -> Path:
    return repo_root_from_here() / "docs" / "benchmark" / "schema.json"
