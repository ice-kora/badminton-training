# AI Worker（占位）

本包为 Phase-2 / V1 **占位 stub**。

## 状态约定

上传成功后 API 直接创建 `analysis_job`：

| 字段 | 值 |
|------|-----|
| `status` | `not_implemented` |
| `error_code` | `ANALYSIS_NOT_IMPLEMENTED` |

可选状态全集：`pending` / `rejected_precheck` / `queued` / `not_implemented` / `failed`。

- **禁止**：返回随机分数、伪 AI 报告、MediaPipe 实时纠错
- 待 `MotionBenchmark` 经专家标注入库后再实现真正的离线分析消费

## Worker 行为

`app/worker.py`：

- `describe()` / `analyze()` — 文档化 stub，永不产出分数
- `claim_pending_jobs(jobs)` — 对传入的 `pending` 任务诚实标为 `not_implemented`（**无分数**）
- 正常上传路径已写入 `not_implemented`，worker 对常见情况为 **no-op**

## 本地

```bash
cd services/ai-worker
python -c "from app.worker import describe; print(describe())"
```
