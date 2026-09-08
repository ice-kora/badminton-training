# AI Worker（占位）

本包为 Phase-2 **占位 stub**。

## 状态

- **视频姿态分析：未实现**（`ANALYSIS_NOT_IMPLEMENTED`）
- **禁止**：返回随机分数、伪 AI 报告、MediaPipe 实时纠错
- 待 `MotionBenchmark` 经专家标注入库、关键点流水线就绪后，再实现离线分析 Job 消费

## 约定

API `POST /analysis/jobs` 当前直接返回结构化错误：

```json
{
  "code": "ANALYSIS_NOT_IMPLEMENTED",
  "message": "视频姿态分析尚未实现。..."
}
```

Worker 进程暂不消费队列；`app/worker.py` 仅文档化入口。

## 本地

```bash
cd services/ai-worker
python -c "from app.worker import describe; print(describe())"
```
