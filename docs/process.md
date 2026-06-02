# Cross Chat — 开发流程记录 (Development Process)

> 最后更新: 2026-06-03

---

## 开发环境

| 项目 | 详情 |
|------|------|
| OS | Windows 10 Pro 10.0.19045 |
| Shell | PowerShell + Git Bash |
| Python | 3.14.5 (winget 安装) |
| 虚拟环境 | `venv/` (项目根目录) |
| 包管理器 | pip 26.1.1 |
| IDE | VS Code |

### 环境初始化命令

```powershell
# 1. 安装 Python 3.14
winget install Python.Python.3.14

# 2. 创建虚拟环境
cd d:\code_space\cross_chat
py -m venv venv

# 3. 激活 + 安装依赖
venv\Scripts\activate
pip install -r backend\requirements.txt

# 4. 升级 brotli (修复 aiohttp 3.14 兼容)
pip install --force-reinstall brotli==1.2.0
```

---

## 开发日志

### 2026-06-02: 初始搭建

- 创建项目结构 (`backend/`, `frontend/`, `docs/`)
- 编写所有 Python 模块和前端模块
- 激活虚拟环境，安装依赖
- 验证所有模块导入和语法

### 2026-06-03: 问题修复 + 方案调整

**上午 — Python 3.14 兼容性修复**
- 修复 `mvp_backend.py`: Python 3.14 禁用 `global` 在变量使用之后声明
- 修复 `danmu_client.py`: blivedm 使用 Handler 模式而非继承重写
- 升级 `brotli` 1.0.9 → 1.2.0 修复 aiohttp 3.14 的 brotli 解压兼容
- 实现 WBI 签名绕过 B站 `-352` 风控错误

**下午 — 前端连接问题**
- 发现 `file://` 协议下 WebSocket 被浏览器安全策略阻断
- 改用 `python -m http.server 8080` 提供 HTTP 访问
- 排查 WebSocket 反复断连问题（仍在处理中）

**晚间 — 方案评估**
- 用户提出使用 `bililive_dm` (copyliu/B站弹幕姬) 替代 `blivedm`
- 初步调研 bililive_dm API 能力和插件系统
- 创建 `task.md` 和 `process.md` 记录方向调整

---

## 遇到的问题 & 解决方案

### 问题 1: Python 3.14 `global` 声明限制

**现象**:
```
SyntaxError: name 'SUBTITLE_FILE' is used prior to global declaration
```

**原因**: Python 3.14 要求 `global` 声明必须出现在任何变量引用之前。原代码在函数签名 `default=SUBTITLE_FILE` 处引用了变量，但 `global SUBTITLE_FILE` 出现在函数体内部之后。

**修复**: [mvp_backend.py](../backend/mvp_backend.py#L37-L38)
- 将 `subtitle_file` 改为 `CrossChatApp.__init__` 的构造参数
- 消除 `global` 声明，完全通过实例变量传递

---

### 问题 2: blivedm API 调用方式错误

**现象**: `DanmuClient` 继承 `BLiveClient` 并重写 `on_danmaku()`，但回调从未被触发。

**原因**: blivedm 库使用 **Handler 注册模式**，而非继承重写模式:
- 正确的用法: 继承 `BaseHandler` → 重写 `_on_danmaku(self, client, message)` → 通过 `add_handler()` 注册
- 错误的用法: 继承 `BLiveClient` → 重写 `on_danmaku()` (不存在的回调)

**修复**: [danmu_client.py](../backend/danmu_client.py)
- `DanmuClient` 改为继承 `BaseHandler`
- 重写 `_on_danmaku(self, client, message)` 方法
- 内部组合 `BLiveClient` 实例，通过 `add_handler(self)` 注册

**教训**: 使用第三方库前必须阅读其源码和示例，不能凭经验猜测 API 模式。

---

### 问题 3: aiohttp 3.14 + brotli 1.0.9 不兼容

**现象**:
```
TypeError: process() takes exactly 1 argument (2 given)
aiohttp.http_exceptions.ContentEncodingError: Can not decode content-encoding: br
```

**原因**: `blivedm` 依赖 `brotli==1.0.9`（2019年发布），其 C 扩展 `BrotliDecompressor.process()` 方法签名与 aiohttp 3.14 期望的不兼容。aiohttp 3.14 调用 `process(data, max_length)` 但旧版 brotli 只接受 `process(data)`。

**修复**:
```powershell
pip install --force-reinstall brotli==1.2.0
```
brotli 1.2.0 向后兼容 1.0.9 的序列化格式，同时支持新的方法签名。

---

### 问题 4: B站 API `-352` 风控错误

**现象**:
```
room=13619077 _init_room_id_and_owner() failed, message=-352
blivedm.client.InitError: init_room() failed
```

**原因**: B站对未登录、无签名的 API 请求返回 `-352`（风险控制）。blivedm (2021) 未实现 WBI (Web Behavior Identification) 签名机制。

**修复**: [danmu_client.py](../backend/danmu_client.py)
- 实现 `_fetch_wbi_keys()`: 从 B站 nav 接口获取 `img_key` + `sub_key`
- 实现 `_sign_params()`: 为 API 请求添加 `wts`(时间戳) + `w_rid`(MD5签名)
- 创建 `_PatchedBLiveClient` 子类，重写 `_init_room_id_and_owner()` 和 `_init_host_server()` 使用签名请求

**关键细节**:
- WBI 混合表前 32 项（非 64 项）→ 生成 32 位签名密钥
- `img_key` (32 hex) + `sub_key` (32 hex) = 64 字符，取前 32 个映射 → 32 字符 mixin_key
- 签名算法: `MD5(sorted_query_string + mixin_key)`

---

### 问题 5: WebSocket 反复断连 (部分解决)

**现象**:
```
[WsBridge] Client connected (total=1)
[WsBridge] Client connected (total=2)
[WsBridge] Client disconnected (total=1)
[WsBridge] Client connected (total=2)   ← 不断重复
```

**原因分析**:

1. **`file://` 协议限制** (已修复): 浏览器将 `file://` 视为独立安全源，WebSocket 连接立即被阻断。改用 HTTP 服务器 (`python -m http.server 8080`) 后连接成功建立。

2. **websockets 16.0 兼容性** (待确认): 
   - 原使用 `async for _ in ws: pass` 保持连接
   - 尝试改用 `ws.wait_closed()` — 问题仍存在
   - 尝试改用 Event 阻塞 — 问题仍存在
   - 日志显示 "Connection closed normally"，说明连接被正常关闭（非异常断开）

3. **多客户端竞争**: OBS Browser Source + 浏览器标签页可能同时连接，造成竞争。

**当前状态**: 
- `file://` 问题已解决
- 前端通过 `http://localhost:8080` 正常加载
- 连接仍不稳定，弹幕只能间歇显示
- 需要进一步排查 `onclose` 的 `event.code` 确定关闭原因

---

### 问题 6: PowerShell 执行策略限制

**现象**: `activate.ps1` 无法运行，提示 "禁止运行脚本"。

**解决方案**:
1. **临时方案**: 使用 `activate.bat` 代替 `activate.ps1`（`.bat` 不受执行策略限制）
2. **永久方案**: `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`
3. **自动化方案**: 创建 `.bat` 启动脚本 (`start_backend.bat`, `start_frontend.bat`)

---

## 架构变更历史

### v0.1 — 初始架构 (2026-06-02)

```
B站 WS → blivedm (Python) → Python Backend → ws://localhost:8765 → OBS Browser Source
```

### v0.2 — 计划中 (2026-06-03)

```
B站 WS → bililive_dm (C# 桌面端) → [桥接层] → Python Backend → ws://localhost:8765 → OBS Browser Source
```

**变更原因**: bililive_dm 弹幕抓取更稳定（25万+ 主播验证），B站协议适配由作者维护。

---

## 开发注意事项

1. **Python 3.14 限制**: 
   - `global` 声明必须在变量引用之前
   - `aiohttp.ClientSession()` 需要运行中的事件循环
   - 某些旧 C 扩展可能不兼容

2. **B站 API 限制**:
   - 需要 WBI 签名绕过风控
   - 未登录用户弹幕用户名和 UID 会被脱敏
   - API 可能随时变更，需关注上游库更新

3. **WebSocket 调试**:
   - 始终使用 `http://` 而非 `file://` 加载前端
   - 在 `onclose` 事件中打印 `event.code` 帮助定位关闭原因
   - websockets 库大版本间可能有 breaking changes

4. **前端开发**:
   - OBS Browser Source 基于 Chromium，基本兼容 Chrome DevTools
   - 使用浏览器 F12 调试时，先用 `http://localhost` 而非 OBS 内嵌
   - CSS 动画在 OBS 内嵌 Chromium 中性能表现可能不同
