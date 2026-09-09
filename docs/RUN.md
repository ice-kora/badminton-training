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

MVP 使用 SQLAlchemy `create_all` + `python -m app.seed`。未强制 Alembic；后续切 Postgres 生产库时再补迁移。

## 拍摄预检 + 上传（V1）

```bash
# 登录拿 token
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/auth/dev-login   -H 'Content-Type: application/json'   -d '{"openid":"dev","nickname":"测试"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 上传（需真实/测试 mp4）
curl -X POST http://127.0.0.1:8000/videos/upload   -H "Authorization: Bearer $TOKEN"   -F skill_id=1   -F 'client_checklist_json={"full_body":true,"distance_ok":true,"racket_visible":true}'   -F file=@/path/to/clip.mp4
```

本地文件落在 `services/api/data/uploads/`（已 gitignore 内容）。

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

状态：`queued` → `extracting` → `pose_extracted` | `failed`（stale `extracting` → `queued`）。

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
