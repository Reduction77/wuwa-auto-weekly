# 开发说明

## 模块

- `garden/ui.py`：账号队列、任务线程与运行历史。
- `garden/widgets.py`：Windows 蓝主题、圆角按钮和卡片。
- `garden/core.py`：队列、暂停/停止、身份绑定及 SQLite 存储。
- `garden/windows.py`：Windows 窗口发现、后台截图与输入。
- `garden/vision.py`：截图识别、登录、周常和返回登录的执行流程。
- `garden/cn_login.py`、`weekly.py`、`play.py`、`return_login.py`：页面判定和动作决策。

用户界面仅保留日常执行功能，开发时的单步诊断、采集指南、乐园入口验证、试运行与单独返回登录按钮已移除。

## 验证

从项目根目录运行测试：

```powershell
python -m unittest discover -s tests
```

可选只读截图验证工具（不会点击游戏）：

```powershell
python -m tools.verify_login_images path/to/login.png
python -m tools.verify_guide_images path/to/guide.png
```

使用虚拟环境时，将 `python` 换为 `.\.venv\Scripts\python.exe`。自动测试无需运行游戏，但 Windows 输入模块依赖 Windows。页面样本位于 `tests/fixtures/`，请仅提交脱敏的 OCR 文字与坐标，不提交含有账号或 UID 的原始截图。

## 修改原则

先观察页面，再发出动作；页面未转移时不得假定操作成功。重试必须有上限，并支持停止。修改登录流程时保留身份绑定检查，修改周常流程时保留实际进度复核。

提交修改时说明触发场景、修复行为、测试结果和实机验证范围。失败截图和诊断只放在 `data/`。不要将游戏凭据、个人账号信息、第三方模型缓存或虚拟环境加入仓库。
