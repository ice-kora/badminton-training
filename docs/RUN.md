# 本地运行说明

## 前置

- Python 3.10+
- （可选）微信开发者工具，用于打开小程序

默认使用 **SQLite**，无需 Docker。

## 启动 API（:8000）

```bash
cd /workspace/badminton-ai-coach   # 或仓库根目录
make install
make run
```

等价脚本：

```bash
./scripts/dev.sh
```

手动步骤：

```bash
cd services/api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
mkdir -p data
export DATABASE_URL=sqlite:///./data/app.db
export ALLOW_DEV_LOGIN=true
python -m app.seed
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

健康检查：`curl http://127.0.0.1:8000/health`

开发登录：`curl -X POST http://127.0.0.1:8000/auth/dev-login -H 'Content-Type: application/json' -d '{"openid":"dev","nickname":"测试"}'`

## 测试

```bash
make test
# 或
cd services/api && source .venv/bin/activate && pytest -q
```

## 小程序

1. 用微信开发者工具打开目录 `apps/miniprogram`
2. 详情 → 本地设置 → **不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书**
3. 确认 `utils/config.js` 中 `baseUrl: 'http://127.0.0.1:8000'`
4. 真机预览需改成电脑局域网 IP，并同样关闭域名校验（仅开发）

## 可选：Postgres / Redis / MinIO

```bash
docker compose -f infra/docker-compose.yml up -d
# 然后将 DATABASE_URL 改为 postgresql+psycopg://badminton:badminton@127.0.0.1:5432/badminton
# （需自行安装 psycopg 驱动；MVP 演示用 SQLite 即可）
```

## 数据库策略

MVP 使用 SQLAlchemy `create_all` + `python -m app.seed`。**本轮仍跳过完整 Alembic。**

> **切 Postgres 生产库前必须先接入 Alembic 迁移**（`create_all` 不足以作为生产 schema 管理）。在 cutover 前补齐迁移与评审，勿直接对生产 Postgres 依赖 `create_all`。

## 拍摄预检 + 上传（V1）

```bash
# 登录拿 token
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/auth/dev-login   -H 'Content-Type: application/json'   -d '{"openid":"dev","nickname":"测试"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 上传（需真实/测试 mp4）
curl -X POST http://127.0.0.1:8000/videos/upload   -H "Authorization: Bearer $TOKEN"   -F skill_id=1   -F 'client_checklist_json={"full_body":true,"distance_ok":true,"racket_visible":true}'   -F file=@/path/to/clip.mp4
```

本地文件落在 `services/api/data/uploads/`（已 gitignore 内容）。

亮度门禁默认 mean luminance ≥ 40（`PRECHECK_MIN_BRIGHTNESS`）。暗场馆可在仅亮度失败时带
`force_upload=true` + `precheck_override=brightness`（或 `accept_quality_risk=true`）上传；
时长/分辨率/朝向仍硬失败。朝向本地放宽：`PRECHECK_RELAX_ORIENTATION=true`。

## 视频 / 任务历史

```bash
# 列表（需 Authorization）
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/videos
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/analysis/jobs
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/videos/1
```

上传成功后 `analysis_job.status=queued`（默认**不**在上传请求内提取），`scoring_status=blocked`，`error_code=ANALYSIS_NOT_IMPLEMENTED`（评分侧）。关键点 JSON：`data/uploads/pose/{video_id}.json`。

### 关键点队列 worker（SQLite，无需 Redis）

本地 demo 两终端：

```bash
make run      # 终端 1：API :8000
make worker   # 终端 2：DB 队列提取（无需 Redis）
```

Windows：可用 Git Bash / WSL 跑 `make`；或在 `services/api` 激活 `.venv` 后执行  
`python -m app.worker extract --loop`（cmd / PowerShell 均可）。

```bash
cd services/api && source .venv/bin/activate
# 推荐：另开终端跑 worker
python -m app.worker extract --once --limit 5   # 处理一批
python -m app.worker extract --loop             # 轮询，间隔 POSE_EXTRACT_POLL_INTERVAL（默认 2s）
# 或
python ../../scripts/run_pose_extract.py --loop

# 卡死 reclaim：extracting 超过 POSE_EXTRACT_STALE_SECONDS（默认 600）→ 回收为 queued
# 可选：API 进程内守护线程（测试请保持 false）
# POSE_EXTRACT_BACKGROUND=true uvicorn ...
# 调试同步：POSE_EXTRACT_INLINE=true 时上传内联提取
# 手动/同步触发仍可用：
curl -X POST -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/videos/1/extract-pose
```

状态：`queued` → `extracting` → `pose_extracted` | `failed`（stale `extracting` → `queued`，`attempt_count` 累加；达到 `POSE_EXTRACT_MAX_ATTEMPTS`（默认 3）→ `failed`）。

```bash
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/videos/1/pose
# 骨架预览（JSON，小程序 canvas；仅可视化非评分）
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8000/videos/1/pose/preview?frame=0"
# 调试 PNG
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8000/videos/1/pose/preview?format=png&frame=0" -o /tmp/pose_preview.png
```

测试默认 `POSE_EXTRACTOR=fake`、`POSE_EXTRACT_INLINE=false`。真实 MediaPipe 需安装 `mediapipe` 并下载 lite `.task` 模型（首次提取自动下载）。

## Motion Benchmark 包

```bash
python scripts/benchmark_validate.py docs/benchmark/templates/forehand_clear.v0.json
python scripts/benchmark_import.py docs/benchmark/templates/forehand_clear.v0.json
python scripts/benchmark_publish.py forehand_clear --version 0.1.0   # draft 默认失败
curl http://127.0.0.1:8000/benchmarks
```

## 原视频 TTL 清理（VIDEO_TTL_DAYS）

默认 **7 天**后删除（unlink）**原始视频文件**，并写入 `training_videos.file_purged_at`。  
**保留** `pose_analyses` 关键点 JSON、`analysis_jobs`、`training_scores` / 问题行。回放原片接口在清理后返回 **410**。

```bash
# 环境变量（可选）
export VIDEO_TTL_DAYS=7

# 执行一批清理
make purge-videos
# 或
cd services/api && source .venv/bin/activate
python -m app.worker purge-videos --once
python -m app.worker purge-videos --once --dry-run          # 只统计
python -m app.worker purge-videos --once --ttl-days 3       # 临时覆盖
# 周期性：
python -m app.worker purge-videos --loop --poll-interval 3600
# 仓库脚本：
python ../../scripts/purge_videos.py --once
```

选择条件：`file_purged_at IS NULL` 且 `created_at < now - VIDEO_TTL_DAYS`。

## 安全与运维要点

### 生产启动 fail-fast

当 `APP_ENV` / `ENV` / `ENVIRONMENT` 为 `production`（或 `prod`）时，启动会拒绝不安全默认值并直接报错：

- `JWT_SECRET` 不得为默认 / 弱口令
- `ALLOW_DEV_LOGIN` 必须为 `false`
- `DEBUG` 必须为 `false`

本地开发可继续使用便捷默认值。

### 上传大小

- `UPLOAD_MAX_BYTES` 默认 **200MB**
- 先检查 `Content-Length`，再流式写入并截断；超限返回 **HTTP 413**

### CORS

- 通过 `CORS_ORIGINS`（逗号分隔白名单）配置
- **禁止** `allow_origins=*` 且 `allow_credentials=True`（若配置了 `*`，凭证自动关闭）

### 视频文件 URL 令牌

`<video>` 标签无法方便带 Bearer 头时，先：

```bash
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/videos/1/file-token
```

返回的短时专用 token（默认约 10 分钟，`VIDEO_FILE_TOKEN_EXPIRE_MINUTES`）用于 `GET /videos/{id}/file?token=...`。**不要**把 7 天会话 JWT 放进 query。

### 小程序登录（共享开发账号）

`apps/miniprogram/utils/request.js` 在 **401** 时会清 token → `ensureLogin` → **仅重试一次**。

开发登录固定 openid：`mp-dev-user`（昵称「小程序体验用户」）。本地多台设备 / 开发者工具会话会**共享同一用户数据**；正式微信登录上线后应替换。

