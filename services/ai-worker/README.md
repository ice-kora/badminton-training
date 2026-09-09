# AI Worker

姿态**关键点提取**由 `services/api` 内的 `python -m app.worker extract` /
`scripts/run_pose_extract.py` 执行。本目录保留状态约定与「禁止打分」stub。

## 状态约定

| 字段 | 典型值 |
|------|--------|
| `status` | `queued` → `pose_extracted`（或 `pose_failed`） |
| `scoring_status` | `blocked` |
| `error_code` | `ANALYSIS_NOT_IMPLEMENTED`（评分侧） |

- **禁止**：随机分数、伪 AI 报告、捏造关节角标准
- 有 published benchmark 时仍可提取关键点；打分继续 blocked

## 本地提取

```bash
cd services/api && source .venv/bin/activate
python -m app.worker extract --limit 10
# 或
python ../../scripts/run_pose_extract.py
```
