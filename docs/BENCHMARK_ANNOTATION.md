# Motion Benchmark 标注与发布（短版）

> 目标：把「标准动作库」做成可版本化的**数据资产流水线**。  
> 硬规则：**禁止编造关节角 / 时序数值并当作已验证标准**。未核验数值须保持 `null`，或显式标记 `draft_unverified` / `expert_pending`（且校验器会拒绝「有数值却仍标 draft」的默认路径）。

## 1. 采集（capture）

1. 按该技能的 **FilmingGuide**（产品 UX，非关节标准）拍摄参考视频：竖屏、时长 **5–60s**、全身/拍面可见。
2. 记录元数据占位：`handedness`（left|right|either）、`camera_view`（如 side_rear_45）。
3. 原始视频与标注包分目录存放；包内只存引用路径，不把大文件塞进 Git。

## 2. 标注（annotate）

| 层 | 内容 | 谁填 | 数值？ |
|----|------|------|--------|
| stages | 阶段名 / 顺序（可与教学内容对齐） | 编辑可草稿 | 无数值 |
| keyframes | 关键帧标签与时间戳占位 | 编辑可草稿 | 时间戳可空 |
| metrics | 指标 id / 名称 / 单位 | 编辑列壳 | **range_* 默认 null** |
| common_error_refs | 错误 id 引用 | 编辑可空 | — |
| linked_drill_codes | 已有 Drill code | 编辑 | — |

**专家稍后必须填写**：各 metric 的合理区间、关键帧判定说明、与错误的映射、`verification_status=verified` 与 `source`（专家署名 / 文献）。

## 3. 存储与版本

- 包文件：`docs/benchmark/templates/{skill_code}.v{N}.json`（或导入后的 DB 行）。
- Schema：`docs/benchmark/schema.json`。
- DB：`motion_benchmarks`（按技能一条壳）+ `benchmark_versions`（每次导入一版）+ `benchmark_stages` / `benchmark_metrics`（从包展开）。
- `status`：`draft` →（核验后）`published`；分析只应消费 **published**。

## 4. 校验 / 导入 / 发布

```bash
# 仓库根目录
python scripts/benchmark_validate.py docs/benchmark/templates/forehand_clear.v0.json
python scripts/benchmark_import.py docs/benchmark/templates/forehand_clear.v0.json
# 默认拒绝 draft_unverified 发布
python scripts/benchmark_publish.py forehand_clear --version 0.1.0
```

- **validate**：对照 schema；若存在非 null 数值区间且 `verification_status=draft_unverified` → **失败**（除非 `--allow-unverified-numbers`）。
- **import**：写入 DB 为 **draft** 版本，不自动 published。
- **publish**：仅 `verified`（或策略允许的状态）可发布；`draft_unverified` 默认拦截（`--force-draft-forbidden` 为默认策略说明；覆盖需显式危险开关）。

## 5. API（只读）

- `GET /benchmarks` — 列表（含是否有已发布版本）
- `GET /benchmarks/{skill_code}` — 当前可见包摘要
- `GET /benchmarks/{skill_code}/versions` — 版本历史

无公开写接口。

## 6. 与分析的关系

- 有 **published** Motion Benchmark：`pose_extracted` 后运行 `PoseScorer`，任务进入 `scored`，写入多维分数 / 至多 3 条问题 / 练习推荐。
- 无 published：保持 `ANALYSIS_NOT_IMPLEMENTED`，`message` 含 `awaiting_published_benchmark`，**不捏造分数**。
- `synthetic_demo` 评分结果全链路必须展示横幅「工程演示基准（非教练标定）」。


## 7. synthetic_demo（流水线演示，非专家标准）

工程可提供 `verification_status=synthetic_demo`、`source=engineering_synthetic_demo` 的演示包（见 `docs/benchmark/demo/`），数值区间必须标注 `range_kind=synthetic_demo`。

```bash
python scripts/benchmark_validate.py docs/benchmark/demo/forehand_clear.synthetic_demo.json --allow-synthetic-demo
python scripts/benchmark_import.py docs/benchmark/demo/forehand_clear.synthetic_demo.json --allow-synthetic-demo
python scripts/benchmark_publish.py forehand_clear --version 0.2.0-synthetic --allow-synthetic-demo
```

**UI/API 必须展示**：工程演示基准（非教练标定）。禁止把合成区间描述为教练标准。

## 8. literature_cited（文献抽取，非教练现场标定）

用同行评审 / 会议生物力学来源的抽取区间替代 `synthetic_demo` 数值依赖。详见 `docs/BENCHMARK_LITERATURE.md`。

- `verification_status=literature_cited`，`source=peer_reviewed_literature`
- 横幅：**文献科研参考标准（非教练现场标定）**
- 每个有数值的指标必须带 `citations` 与 `range_kind` ∈ {`literature_mean_sd`, `literature_point_tolerance`, `literature_proxy_related_stroke`}
- 发布：`--allow-literature-cited`（或 `scripts/benchmark_publish_literature.sh`）
- **不是** `verified` 教练签核；单目 MediaPipe ≠ 实验室动作捕捉。

