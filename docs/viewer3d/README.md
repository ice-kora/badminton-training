# V3 · 3D 标准动作查看（演示壳）

**非实时。** 无摄像头纠错。数据默认 `synthetic_demo`，须展示横幅：**工程演示基准（非教练标定）**。

## 技术选型（已交付）

**主路径 Option A（微信可跑）**：原生小程序 `canvas`（type=2d）+ **程序化骨架**，由 `GET /benchmarks/{skill_code}/viewer3d` 返回的 demo 关键点序列驱动。支持拖动轨道旋转、双指缩放、0.25/0.5/1x 播放、阶段跳转、角度 HUD 占位。

**未选用 threejs-miniprogram 作为主依赖**：避免小程序 npm 构建与体积阻塞验收；骨架序列已够演示。

**次路径 Option B（冒烟）**：API 静态页 `/static/viewer3d/index.html`（Three.js CDN）可在浏览器或配置合法域名后的 web-view 打开；同读上述 manifest。

## 资产

- `stick_figure.synthetic_demo.glb`：极简静态 stick-figure（LINES），extras 标 `synthetic_demo`，**非 mocap**。
- 动画以 JSON 关键点帧为主；GLB 供后续替换/加载试验。

## 入口

技能详情 → **「3D 标准动作（演示）」** → `pages/viewer3d/index`。

## 前端冒烟（文档）

1. `make run` 后 `curl http://127.0.0.1:8000/benchmarks/forehand_clear/viewer3d | head`
2. 浏览器打开 `http://127.0.0.1:8000/static/viewer3d/index.html?skill_code=forehand_clear`
3. 微信开发者工具打开小程序，技术库 → 技能 → 3D 标准动作（演示）
