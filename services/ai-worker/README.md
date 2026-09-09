# AI Worker

姿态**关键点提取**由 `services/api` 内的 DB 队列 worker 执行（无需 Redis）：

```bash
cd services/api && source .venv/bin/activate
python -m app.worker extract --once          # 处理一批 queued
python -m app.worker extract --loop          # 轮询（POSE_EXTRACT_POLL_INTERVAL，默认 2s）
# 或可选：API 进程内守护线程 POSE_EXTRACT_BACKGROUND=true
```

本目录保留状态约定与「禁止打分」stub。

## 状态约定

| 字段 | 典型值 |
|------|--------|
| `status` | `queued` → `extracting` → `pose_extracted` \| `failed` |
| `scoring_status` | `blocked` |
| `error_code` | `ANALYSIS_NOT_IMPLEMENTED`（评分侧） |

- **禁止**：随机分数、伪 AI 报告、捏造关节角标准
- 有 published benchmark 时仍可提取关键点；打分继续 blocked
