# 羽毛球 AI 学习训练助手（Phase-2 / V3 3D 标准动作演示壳）

微信小程序 + FastAPI 内容/计划 MVP。  
目标仓库：https://github.com/ice-kora/badminton-training.git

> **硬约束**：**禁止**实时摄像头纠错；**禁止**把 LLM/工程合成关节区间当作专家标准。  
> 评分仅在存在 **published** Motion Benchmark 时开放。生产评分优先使用 `literature_cited`（`--allow-literature-cited`，横幅：**文献科研参考标准（非教练现场标定）**）。`synthetic_demo` 仍须 `--allow-synthetic-demo` 并展示合成横幅。无 published 时仍为 `ANALYSIS_NOT_IMPLEMENTED` / `awaiting_published_benchmark`。

## 结构

```
apps/miniprogram/     原生微信小程序（中文 UI）
services/api/         FastAPI + SQLAlchemy 2 + SQLite
services/ai-worker/   状态约定 stub（打分仍禁用）
infra/docker-compose.yml   可选 postgres/redis/minio
docs/                 设计、RUN、内容政策、benchmark 模板
scripts/              seed / pose extract / benchmark_validate|import|publish / dev.sh
                       DB 队列：python -m app.worker extract --once|--loop（无需 Redis）
                       worker 循环内嵌 TTL 原片清理（VIDEO_PURGE_INTERVAL_SECONDS，默认每小时）
```

## 快速开始

```bash
make install
make run          # 终端 1：API http://127.0.0.1:8000
make worker       # 终端 2：pose 提取队列（DB，无需 Redis；内含 7 天 TTL 原片清理）
make test         # pytest 须全绿
```

Windows：`make` 可用 Git Bash/WSL；或在 `services/api` 激活 `.venv` 后跑 `python -m app.worker extract --loop`。

详见 [docs/RUN.md](docs/RUN.md)、[docs/CONTENT_POLICY.md](docs/CONTENT_POLICY.md)。

## 验收步骤

1. **API 启动**：仓库根目录执行 `make install && make run`，浏览器或 curl 访问 `http://127.0.0.1:8000/health` 返回 `{"status":"ok",...}`。
2. **种子数据**：启动日志出现 `Seed OK`；`GET /skills/tree` 含「正手高远球」「正手杀球」「网前搓球」。
3. **pytest**：`make test` 全部通过（含 analysis 返回 `ANALYSIS_NOT_IMPLEMENTED`）。
4. **水平测试计划**：`POST /auth/dev-login` 取 token → `POST /plans/level-test` `{"level":"beginner"}` → 得到 7 日计划。
5. **推荐非 AI 姿态**：`GET /recommendations/what-to-practice-now` 的 `method` 为 `rule_based_from_plan_and_checkins`。
6. **分析诚实失败**：`POST /analysis/jobs` 返回 HTTP 501，body.code = `ANALYSIS_NOT_IMPLEMENTED`。
7. **小程序**：微信开发者工具打开 `apps/miniprogram`，勾选「不校验合法域名」，首页可拉技能树与计划入口。


## 体验步骤（拍摄预检 + 上传）

1. `make install && make run` 启动 API（:8000）。
2. 微信开发者工具打开 `apps/miniprogram`，不校验合法域名；`touristappid`。
3. 技术库 → 选技能（如正手高远球）→ **查看拍摄引导** → **开始录制 / 选择视频**。
4. 对照剪影勾选清单（全身/距离等为客户端门禁）→ `chooseMedia` 选视频（工具里比 camera 稳）。
5. 上传：服务端预检时长/分辨率/亮度/方向；失败展示原因并提示重拍。
6. 通过后返回 `video_id` + `analysis_job`（默认 `queued`；另开终端 `make worker` 或 `python -m app.worker extract --loop` → `extracting`→`pose_extracted`；卡死 extracting 超 `POSE_EXTRACT_STALE_SECONDS` 会回收为 queued；`scoring_status=blocked` / `ANALYSIS_NOT_IMPLEMENTED`）。
7. 「我的」详情分别显示「关键点已提取/未提取」与「评分未开放」；已提取时可滑帧「骨架预览」（仅关键点可视化，非评分）。
8. **复测对比（仅骨架）**：详情点「针对此视频复测」→ 拍摄页带 `baseline_video_id` 上传 → 复测详情在双方均 `pose_extracted` 后显示左右并排骨架滑帧（`GET /videos/{id}/retest-compare`）；**无分数、无正确性判断**。
9. **V2**：`pose_extracted`/`scored` 后详情展示阶段时间轴与「标准 vs 用户」叠加（绿/蓝，标 **非评分叠加**）；`GET /videos/{id}/stage-timeline`、`GET /videos/{id}/pose/overlay`。
10. **V3**：技术库 → 技能详情 → **3D 标准动作（演示）**；旋转/缩放/倍速/阶段跳转/HUD 占位；横幅 synthetic_demo；**禁止实时**。

**真预检**：duration / resolution / brightness / orientation（OpenCV 探测）。亮度阈值 `PRECHECK_MIN_BRIGHTNESS`（默认 40）；仅亮度失败可 `precheck_override=brightness` / `force_upload` 放行并记入元数据，其它硬门不跳过。  
**占位**：full_body / distance → `deferred_to_pose` 或客户端清单确认（非姿态 AI）。

## API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /health | 健康检查 |
| POST | /auth/dev-login | 本地 JWT |
| GET | /skills/tree | 技能树 |
| GET | /skills/{id} | 技能详情 |
| GET | /filming-guides/{skill_id} | 拍摄引导（含预检策略） |
| POST | /videos/precheck | 仅预检（multipart，需登录） |
| POST | /videos/upload | 预检+入库+创建 analysis_job（可选 form `baseline_video_id` 同用户同技能复测） |
| GET | /videos | 当前用户视频列表（`?skill_id=` 可选过滤） |
| GET | /videos/{id} | 视频详情 + 预检 + 关联任务；有复测链时含 `baseline` 摘要 |
| GET | /videos/{id}/retest-compare | 基准 vs 当前双骨架预览（`?frame=`）；双方均需已提取；仅可视化非评分 |
| GET | /videos/{id}/stage-timeline | V2 阶段时间轴（启发式切分；可选相对模板 Δt） |
| GET | /videos/{id}/pose/overlay | V2 标准(绿) vs 用户骨架叠加（`?frame=` 同步 scrub；非评分叠加） |
| GET | /videos/{id}/pose | 关键点元数据（无分数） |
| GET | /videos/{id}/pose/preview | 骨架预览 JSON（`?frame=`）；`?format=png` 调试图；仅可视化非评分 |
| POST | /videos/{id}/extract-pose | 触发离线关键点提取 |
| GET | /analysis/jobs | 当前用户分析任务列表 |
| GET | /analysis/jobs/{id} | 任务状态（无分数） |
| POST | /plans/level-test | 规则 7 日计划 |
| GET | /plans/current | 当前计划 |
| POST | /sessions/check-in | 打卡 |
| GET | /sessions | 打卡记录 |
| GET | /drills /errors /tips | 内容列表 |
| GET | /recommendations/what-to-practice-now | 规则推荐 |
| POST | /analysis/jobs | 未实现（501） |
| GET | /benchmarks | Motion Benchmark 列表（只读） |
| GET | /benchmarks/{skill_code} | 某技能标准库摘要 |
| GET | /benchmarks/{skill_code}/versions | 版本历史 |
| GET | /benchmarks/{skill_code}/viewer3d | V3 3D 标准动作 manifest（阶段/关键点/HUD，synthetic_demo） |
| GET | /static/viewer3d/* | V3 静态 GLB + Three.js 冒烟页（Option B） |

## Motion Benchmark + V1 评分 + V2 可视化

- 文档：`docs/BENCHMARK_ANNOTATION.md`，schema：`docs/benchmark/schema.json`
- 空模板（数值全 null）：`docs/benchmark/templates/*.v0.json`
- **合成演示包**：`docs/benchmark/demo/*.synthetic_demo.json`（`verification_status=synthetic_demo`，`source=engineering_synthetic_demo`）
- **文献抽取包（生产评分）**：`docs/benchmark/literature/*.literature_v1.json`（`verification_status=literature_cited`，`source=peer_reviewed_literature`）；说明见 `docs/BENCHMARK_LITERATURE.md`
- 校验 / 导入 / 发布：`scripts/benchmark_*.py`；一键：`scripts/benchmark_publish_literature.sh`
  - `draft_unverified` 默认不可发布
  - `synthetic_demo` 仅 `--allow-synthetic-demo` 可发布
  - `literature_cited` 仅 `--allow-literature-cited` 可发布（须 citations + range_kind）
- Worker：`pose_extracted` 后若有 published → `PoseScorer` → `scored`（结果写入 `training_scores` / `pose_problems`）
- 无 published：保持 `ANALYSIS_NOT_IMPLEMENTED` + `awaiting_published_benchmark`
- **V2 阶段时间轴**：用 demo `stages` / `keyframes` 相对时序启发式切分用户关键点序列，边界写入 `pose_analyses.stage_timeline_json`；有模板时序则返回 `delta_ms`
- **V2 骨架叠加**：绿=标准（包内 `synthetic_keypoint_template`，否则生成 `synthetic_demo` 序列），蓝=用户；接口与详情页均标 **非评分叠加** / synthetic_demo 横幅；**禁止实时**
- **V3 3D 标准动作（演示）**：技能详情入口；小程序 canvas 程序化骨架（Option A）；`GET /benchmarks/{code}/viewer3d`；静态 GLB + `/static/viewer3d/index.html`（Option B 冒烟）。详见 [docs/viewer3d/README.md](docs/viewer3d/README.md)

## License

Private / TBD
