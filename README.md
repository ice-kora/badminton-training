# 羽毛球 AI 学习训练助手（Phase-2 / V1 拍摄预检）

微信小程序 + FastAPI 内容/计划 MVP。  
目标仓库：https://github.com/ice-kora/badminton-training.git

> **硬约束**：无姿态评分、无 MediaPipe、无随机分数、无实时纠错。  
> 分析接口返回 `ANALYSIS_NOT_IMPLEMENTED`。内容带 `source` + `verification_status`。

## 结构

```
apps/miniprogram/     原生微信小程序（中文 UI）
services/api/         FastAPI + SQLAlchemy 2 + SQLite
services/ai-worker/   分析占位 stub
infra/docker-compose.yml   可选 postgres/redis/minio
docs/                 设计、RUN、内容政策、benchmark 模板
scripts/              seed / benchmark_validate|import|publish / dev.sh
```

## 快速开始

```bash
make install
make run          # http://127.0.0.1:8000
make test         # pytest 须全绿
```

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
6. 通过后返回 `video_id` + `analysis_job`（`not_implemented` / `ANALYSIS_NOT_IMPLEMENTED`），页面提示「姿态分析尚未开放，不返回分数」。
7. 「我的」页可看上传历史；点进详情看预检与任务状态。

**真预检**：duration / resolution / brightness / orientation（OpenCV 探测）。  
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
| POST | /videos/upload | 预检+入库+创建 analysis_job |
| GET | /videos | 当前用户视频列表（含最新任务摘要） |
| GET | /videos/{id} | 视频详情 + 预检 + 关联任务 |
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

## Motion Benchmark（数据资产壳）

- 文档：`docs/BENCHMARK_ANNOTATION.md`，schema：`docs/benchmark/schema.json`
- 空模板（数值全 null）：`docs/benchmark/templates/*.v0.json`
- 校验 / 导入 draft / 发布：`scripts/benchmark_*.py`（`draft_unverified` 默认不可发布）
- 分析仍为 `ANALYSIS_NOT_IMPLEMENTED`，无分数；无 published 版本时 message 含 `awaiting_published_benchmark`

## License

Private / TBD
