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
