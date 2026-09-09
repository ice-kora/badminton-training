"""Seed categories, 3 skills, stages, content, drills, errors, tips, filming guides, benchmark shells."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow `python -m app.seed` from services/api
_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine, init_db
from app.models import (
    AnalysisJob,
    BadmintonSkill,
    BenchmarkMetric,
    BenchmarkStage,
    BenchmarkVersion,
    CommonError,
    Drill,
    FilmingGuide,
    MotionBenchmark,
    ProblemToDrill,
    SkillCategory,
    SkillContentBlock,
    SkillStage,
    TipArticle,
    TrainingVideo,
)

DRAFT = "draft_unverified"
SRC = "editorial_draft"


def _clear(db: Session) -> None:
    """Idempotent re-seed: refresh schema + wipe content (MVP local)."""
    try:
        db.commit()
    except Exception:
        db.rollback()
    db.close()
    engine.dispose()
    # Recreate tables so FilmingGuide precheck columns / new models exist
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def seed(db: Session | None = None) -> None:
    own = db is None
    if own:
        init_db()
        db = SessionLocal()
    assert db is not None
    try:
        if own:
            _clear(db)
            db = SessionLocal()
        else:
            # Test path: tables already created by init_db; just wipe content rows
            for model in (
                AnalysisJob,
                TrainingVideo,
                ProblemToDrill,
                BenchmarkMetric,
                BenchmarkStage,
                BenchmarkVersion,
                MotionBenchmark,
                FilmingGuide,
                SkillContentBlock,
                SkillStage,
                CommonError,
                Drill,
                TipArticle,
                BadmintonSkill,
                SkillCategory,
            ):
                db.query(model).delete()
            db.commit()

        # Categories
        cat_rear = SkillCategory(
            code="rear_court",
            name="后场技术",
            sort_order=1,
            description="后场高远、杀球等进攻与过渡技术",
        )
        cat_net = SkillCategory(
            code="net_play",
            name="网前技术",
            sort_order=2,
            description="网前搓球、勾对角、推球等",
        )
        db.add_all([cat_rear, cat_net])
        db.flush()

        # Skills
        clear = BadmintonSkill(
            category_id=cat_rear.id,
            code="forehand_clear",
            name="正手高远球",
            summary="将球打到对方后场底线附近，争取时间与压迫落点。",
            difficulty="beginner",
            sort_order=1,
            source=SRC,
            verification_status=DRAFT,
        )
        smash = BadmintonSkill(
            category_id=cat_rear.id,
            code="forehand_smash",
            name="正手杀球",
            summary="后场下压进攻技术，强调引拍、击球点与发力顺序。",
            difficulty="intermediate",
            sort_order=2,
            source=SRC,
            verification_status=DRAFT,
        )
        tumble = BadmintonSkill(
            category_id=cat_net.id,
            code="net_tumble",
            name="网前搓球",
            summary="网前轻放，制造球翻滚过网，压制对方起高。",
            difficulty="beginner",
            sort_order=1,
            source=SRC,
            verification_status=DRAFT,
        )
        db.add_all([clear, smash, tumble])
        db.flush()

        # Stages
        stages = [
            (clear, [("准备架拍", "侧身、非持拍手指向来球，拍面抬起。"),
                     ("引拍", "肘带动、拍头下落蓄力。"),
                     ("击球", "高点击球，鞭打发力。"),
                     ("随挥回收", "随挥后快速回动到中心。")]),
            (smash, [("准备与并步", "后场并步到位，侧身对网。"),
                     ("引拍蓄力", "充分转体引拍。"),
                     ("击球下压", "击球点靠前上方，拍面下压。"),
                     ("落地缓冲与回动", "落地缓冲，准备下一拍。")]),
            (tumble, [("上网步伐", "前交叉或并步上网。"),
                      ("引拍与接触点", "拍面平行球网前上方接触。"),
                      ("搓切动作", "轻切球托使球翻滚过网。"),
                      ("还原", "快速回中准备。")]),
        ]
        for skill, items in stages:
            for i, (name, desc) in enumerate(items, start=1):
                db.add(
                    SkillStage(
                        skill_id=skill.id,
                        name=name,
                        description=desc,
                        sort_order=i,
                        source=SRC,
                        verification_status=DRAFT,
                    )
                )

        # Content blocks
        blocks = [
            (clear, "overview", "技术概述",
             "正手高远球是后场基本技术，用于过渡与调动对方。以下要点为编辑草稿，未经专家核验。"),
            (clear, "key_points", "关键要点",
             "1) 侧身到位；2) 高点击球；3) 鞭打发力而非硬砸；4) 落点尽量贴近底线。角度数值需专家标注，此处不给出伪标准。"),
            (clear, "cues", "口令提示",
             "侧身—抬肘—高点—鞭打—回动。"),
            (smash, "overview", "技术概述",
             "正手杀球是主要进攻手段。练习应循序渐进，先轻杀再重杀。内容为 draft_unverified。"),
            (smash, "key_points", "关键要点",
             "1) 并步到位；2) 转体引拍；3) 击球点靠前；4) 下肢与核心参与发力。禁止将未经验证的关节角当作事实。"),
            (smash, "cues", "口令提示",
             "到位—转体—高点下压—缓冲回动。"),
            (tumble, "overview", "技术概述",
             "网前搓球追求贴网翻滚，强调手感与接触点，而非大力。"),
            (tumble, "key_points", "关键要点",
             "1) 上网步伐稳定；2) 拍面控制；3) 轻切而非推；4) 眼睛盯球托。"),
            (tumble, "cues", "口令提示",
             "上网—举拍—轻切—还原。"),
        ]
        for i, (skill, btype, title, body) in enumerate(blocks):
            db.add(
                SkillContentBlock(
                    skill_id=skill.id,
                    block_type=btype,
                    title=title,
                    body=body,
                    sort_order=i,
                    source=SRC,
                    verification_status=DRAFT,
                )
            )

        # Filming guides (UX + V1 engineering precheck policy)
        precheck_policy = {
            "duration_range_sec": [5, 60],
            "min_short_side": 720,
            "orientation": "portrait",
            "min_brightness": 40,
            "required_checks": ["duration", "resolution", "brightness", "orientation"],
            "client_checklist_items": ["full_body", "distance_ok", "racket_visible"],
            "deferred_checks": ["full_body", "distance"],
        }
        guides = [
            (clear,
             "场地侧后方约 45°（持拍手异侧略偏后）",
             "约 3–5 米，全身入镜",
             "手机高度约腰至胸",
             ["全身入画", "球拍可见", "光线充足、背景简洁", "竖屏拍摄", "击球全程在画面中", "时长约 5–60 秒"]),
            (smash,
             "侧后方约 30–45°，能看清引拍与下压",
             "约 3–5 米",
             "手机高度约腰部",
             ["全身入画", "并步与击球可见", "球拍轨迹清晰", "避免逆光", "竖屏拍摄", "时长约 5–60 秒"]),
            (tumble,
             "网前侧面或略偏后侧",
             "约 2–3 米，聚焦网前区域",
             "手机高度约网高附近",
             ["上半身与拍面清晰", "球过网过程可见", "尽量避免遮挡", "竖屏拍摄", "时长约 5–60 秒"]),
        ]
        for skill, angle, dist, height, checklist in guides:
            db.add(
                FilmingGuide(
                    skill_id=skill.id,
                    camera_angle=angle,
                    distance_hint=dist,
                    height_hint=height,
                    orientation="portrait",
                    full_body_required=1 if skill is not tumble else 0,
                    racket_visible=1,
                    lighting_notes="避免逆光；室内尽量均匀照明。此为产品拍摄 UX 指引，非关节角标准。",
                    checklist_json=json.dumps(checklist, ensure_ascii=False),
                    duration_min_sec=5,
                    duration_max_sec=60,
                    min_short_side=720,
                    min_brightness=40,
                    precheck_policy_json=json.dumps(precheck_policy, ensure_ascii=False),
                    source="product_ux_guideline",
                    verification_status=DRAFT,
                )
            )

        # Motion benchmark shells — metrics NULL
        for skill, name in [
            (clear, "正手高远球标准库壳"),
            (smash, "正手杀球标准库壳"),
            (tumble, "网前搓球标准库壳"),
        ]:
            bm = MotionBenchmark(
                skill_id=skill.id,
                name=name,
                handedness="right",
                notes=(
                    "metric_table_json / metrics_json 刻意为空。"
                    "关节角与时序区间须由专家标注后写入，禁止编造数值标准。"
                ),
                metric_table_json=None,
                source="placeholder_shell",
                verification_status=DRAFT,
            )
            db.add(bm)
            db.flush()
            db.add(
                BenchmarkVersion(
                    benchmark_id=bm.id,
                    version_label="v0-shell",
                    status="draft",
                    verification_status=DRAFT,
                    source="placeholder_shell",
                    package_json=None,
                    metrics_json=None,
                    change_log="初始空壳版本，等待专家标注。",
                )
            )

        # Drills
        drills_data = [
            (clear, "clear_stance_hold", "高远球架拍定型", "建立稳定准备姿势",
             "1. 侧身架拍静止 3 秒\n2. 慢速挥拍 10 次\n3. 完整挥拍 15 次", 10, "low"),
            (clear, "clear_rhythm_breakdown", "高远球节奏分解", "改善引拍-击球节奏",
             "1. 口令：引—打—收\n2. 每组 12 拍，共 3 组", 12, "medium"),
            (clear, "clear_placement", "高远球落点练习", "控制落点靠近底线",
             "1. 对墙或陪练打高远\n2. 目标区域贴地标\n3. 记录落点分布（主观）", 15, "medium"),
            (smash, "smash_power_chain", "轻杀发力顺序", "先掌握发力链再加重杀",
             "1. 无球转体引拍\n2. 轻杀 20 拍\n3. 注意落地缓冲", 12, "medium"),
            (smash, "smash_footwork", "杀球并步到位", "提高后场移动到位率",
             "1. 中心→后场并步\n2. 空挥杀球\n3. 回中，重复 10 次", 10, "high"),
            (tumble, "tumble_touch", "网前搓球手感", "培养轻切手感",
             "1. 近网抛球自搓 20 次\n2. 强调球翻滚\n3. 记录贴网次数（主观）", 10, "low"),
            (tumble, "tumble_approach", "搓球上网步伐", "步伐与手法衔接",
             "1. 中心启动上网\n2. 搓球\n3. 回中，左右交替各 8 次", 12, "medium"),
        ]
        drill_objs: list[Drill] = []
        for skill, code, name, goal, steps, mins, intensity in drills_data:
            d = Drill(
                skill_id=skill.id,
                code=code,
                name=name,
                goal=goal,
                steps=steps,
                duration_minutes=mins,
                intensity=intensity,
                source=SRC,
                verification_status=DRAFT,
            )
            db.add(d)
            drill_objs.append(d)
        db.flush()

        # Common errors
        errors_data = [
            (clear, "击球点过低", "击球时拍头偏低，球容易下网或不够远。",
             "强调高点击球；可对镜慢动作检查，不以伪角度数值为准。"),
            (clear, "正面硬挥无侧身", "未侧身导致发力不足、落点偏前。",
             "先练侧身架拍定型 Drill。"),
            (smash, "杀球发力只用手臂", "缺少转体与下肢，杀球无力且易伤肩。",
             "练轻杀发力顺序，强调转体。"),
            (smash, "击球点太后", "球到身后才打，无法下压。",
             "提前判断，并步更积极。"),
            (tumble, "搓球变推球", "发力过大把球推高，给对方进攻机会。",
             "减小发力，练习轻切手感。"),
            (tumble, "拍面角度不稳", "球不过网或出界。",
             "固定网前举拍高度，慢速重复。"),
        ]
        error_objs: list[CommonError] = []
        for skill, title, desc, fix in errors_data:
            e = CommonError(
                skill_id=skill.id,
                title=title,
                description=desc,
                how_to_fix=fix,
                source=SRC,
                verification_status=DRAFT,
            )
            db.add(e)
            error_objs.append(e)
        db.flush()

        # problem -> drill links (by name matching)
        name_to_drill = {d.name: d for d in drill_objs}
        links = [
            ("击球点过低", "高远球架拍定型"),
            ("正面硬挥无侧身", "高远球架拍定型"),
            ("杀球发力只用手臂", "轻杀发力顺序"),
            ("击球点太后", "杀球并步到位"),
            ("搓球变推球", "网前搓球手感"),
            ("拍面角度不稳", "网前搓球手感"),
        ]
        err_by_title = {e.title: e for e in error_objs}
        for et, dn in links:
            if et in err_by_title and dn in name_to_drill:
                db.add(
                    ProblemToDrill(
                        error_id=err_by_title[et].id,
                        drill_id=name_to_drill[dn].id,
                        note="规则映射草稿，待专家确认。",
                    )
                )

        # Tips
        tips = [
            ("新手训练前热身清单", "降低受伤风险",
             "慢跑 3–5 分钟，肩腕踝动态拉伸，无球挥拍。内容为编辑草稿。", "热身,入门"),
            ("如何安排一周羽毛球训练", "计划节奏建议",
             "建议技术日与对抗日交替，至少安排一日恢复。规则计划可在小程序生成。", "计划,恢复"),
            ("为什么本阶段不做实时纠错", "产品原则说明",
             "实时纠错依赖稳定的姿态与标准库。在专家标注完成前，我们只提供内容、计划与拍摄引导，不输出模拟分数。",
             "产品,原则"),
        ]
        for title, summary, body, tags in tips:
            db.add(
                TipArticle(
                    title=title,
                    summary=summary,
                    body=body,
                    tags=tags,
                    source=SRC,
                    verification_status=DRAFT,
                )
            )

        db.commit()
        print("Seed OK: categories=2, skills=3, drills/errors/tips/filming/benchmarks loaded.")
    finally:
        if own:
            db.close()


if __name__ == "__main__":
    seed()
