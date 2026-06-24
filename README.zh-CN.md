# DevPet（claude-buddy）

**[English README](README.md)**

用手机养一只「开发桌宠」：写代码时伙伴会醒来，有权限待审批时会提醒你，**在手机上就能批准或拒绝危险命令**，不必反复切回 IDE。

**DevPet** 是本仓库 [`app/`](app/) 目录下的 **Expo 手机应用**。电脑端运行本地 **Bridge** 和 **Hooks**（Cursor / Claude Code），与手机处于同一 Wi‑Fi。会话快照、宠物状态、审批指令等协议，**参考并延续**了仓库内 ESP32 固件的设计；手机通过 **局域网 WebSocket** 连接，不使用 BLE。

> 设计说明：[`docs/superpowers/specs/2026-06-17-mobile-buddy-design.md`](docs/superpowers/specs/2026-06-17-mobile-buddy-design.md)

## 手机端功能（DevPet）

| 模块 | 说明 |
| --- | --- |
| **首页** | 七种状态的桌宠动画、会话横幅、统计、一键重连 |
| **审批** | 任意 Tab 全局弹窗 — 允许一次 / 拒绝 Shell 命令与选项题 |
| **会话** | 活跃与近期会话列表，点击 **切换焦点**，待办队列与动态流 |
| **自定义 GIF** | 从相册为每个状态选 GIF（≤ 5MB），未设置则用占位图 |
| **音效** | 审批提示音（`expo-audio`），设置中可静音 |
| **通知** | iOS / dev build 支持锁屏；Android Expo Go 仅应用内音效 |
| **设置** | 局域网 IP、端口、伙伴名称、语言、音效开关 |
| **安装引导** | 首次启动 Bridge 安装向导，设置中可再次打开 |
| **帮助** | 设置页底部 FAQ，默认折叠，涵盖连接、端口、Hooks 等 |
| **多语言** | 中文、English、한국어、Русский |

### 宠物状态

| 状态 | 触发时机 |
| --- | --- |
| `sleep` | 未连接 Bridge |
| `idle` | 已连接，无紧急事项 |
| `busy` | 有会话在运行 |
| `attention` | 有待审批或选择 |
| `celebrate` | 会话结束 |
| `heart` | 5 秒内完成审批 |
| `dizzy` | 预留（仅固件 IMU） |

### 自定义 GIF

**设置 → 自定义 GIF** 可为 sleep / idle / busy 等状态分别选图，文件仅存手机本地，Bridge 不会上传你的素材。

## 工作原理

```text
┌──────────────── 电脑（同一 Wi‑Fi）─────────────────┐
│  Cursor / Claude Code  →  hooks/  →  bridge/      │
│                          HTTP 9876    WS 9877      │
└──────────────────────────┬─────────────────────────┘
                           │ WebSocket 快照
                           ▼
┌──────────────── 手机 — DevPet（Expo）──────────────┐
│  桌宠 · 会话 · 审批 · 设置 · 帮助                  │
└────────────────────────────────────────────────────┘
```

| 组件 | 职责 |
| --- | --- |
| **App** | 界面、桌宠、GIF、通知、本地偏好 |
| **Bridge** | 会话状态、待办决策、向手机推送心跳 |
| **Hooks** | 把 Cursor / Claude Code 事件转成 Bridge 协议 |

心跳字段、`permission` / `answer` / `focus` 等指令与 [ESP32 固件参考](firmware/README.md) 一致；手机走 **Wi‑Fi**，不走 BLE。

## 安装

手机与电脑须 **同一 Wi‑Fi**。

### 环境要求

| 项目 | 说明 |
| --- | --- |
| Python 3.10+ | Bridge 与 Hooks |
| Node.js 18+ | 可选，安装 `devpet-bridge` 全局命令 |
| Git | 克隆仓库以安装 Hooks（必需） |
| Cursor 或 Claude Code | Hook 集成 |
| 手机 | [Expo Go](https://expo.dev/go) 或 dev build |

| 端口 | 协议 | 用途 |
| --- | --- | --- |
| `9876` | HTTP POST | Hooks |
| `9877` | WebSocket | 手机 App |

### 1. 克隆与电脑端一次性配置

```bash
git clone https://github.com/weikunzl/ai-code-buddy.git
cd ai-code-buddy
./tools/install-desktop.sh    # 安装 bridge + Cursor/Claude Hooks
```

建议使用虚拟环境：`python3 -m venv .venv && source .venv/bin/activate`

### 2. Bridge CLI（可选）

```bash
npm install -g github:weikunzl/ai-code-buddy#feat/mobile-buddy
devpet-bridge restart    # 清理旧进程，启动 HTTP + WebSocket
```

Hooks 仍须 **git 克隆**（步骤 1）；CLI 只负责启动 Bridge。

### 3. 启动 Bridge

```bash
devpet-bridge restart
# 或：./tools/restart_bridge.sh
```

Hooks 在 Bridge 未运行时也会 **自动后台启动**（`BUDDY_BRIDGE_AUTOSTART=1`，默认）。

### 4. 手机 App

```bash
cd app && npm install && npm start
```

1. Expo Go 扫描 QR（与电脑同一 Wi‑Fi）。
2. 首次打开会进入 **Bridge 安装引导**（设置里可随时再看）。
3. 填入电脑 **局域网 IP** → `ws://<IP>:9877` → **连接**。

### 5. 验证

```bash
python3 tools/push_test_prompt.py   # 手机应弹出审批
cd app && npm test
```

**连不上？** 确认 IP 为局域网地址（非 `127.0.0.1`）、同一 Wi‑Fi、`devpet-bridge restart`；或展开设置页 **帮助** FAQ。

### 命令速查

```bash
./tools/install-desktop.sh
npm install -g github:weikunzl/ai-code-buddy#feat/mobile-buddy
devpet-bridge restart
cd app && npm start
```

## Cursor 集成

[`hooks/cursor/hook.py`](hooks/cursor/hook.py) 对接 [Cursor Agent Hooks](https://cursor.com/docs/hooks)。安装：

```bash
python3 hooks/cursor/install.py
```

| `CURSOR_BUDDY_APPROVE` | 行为 |
| --- | --- |
| `risky`（默认） | 危险 / 网络类 Shell 命令需在手机审批 |
| `all` | 所有 Shell 命令都等待 |
| `off` | 仅观察，不拦截 |

默认 25 秒超时后 **放行**，由 Cursor 原有提示接管。

## 仓库结构

```text
claude-buddy/
├── app/                   # DevPet 手机应用（主产品）
├── bridge/                # Python：HTTP、WebSocket、mDNS
├── hooks/                 # Cursor / Claude Code 适配
├── packages/protocol/     # 共享协议类型
├── firmware/              # ESP32 参考实现（可选）→ firmware/README.md
├── docs/                  # 设计与协议文档
├── package.json           # devpet-cli（devpet-bridge 命令）
└── tools/                 # 安装脚本与冒烟测试
```

## 协议文档

| 文档 | 说明 |
| --- | --- |
| [`docs/protocol/mobile-bridge.md`](docs/protocol/mobile-bridge.md) | 手机 WebSocket 帧格式 |
| [`docs/superpowers/specs/2026-06-17-mobile-buddy-design.md`](docs/superpowers/specs/2026-06-17-mobile-buddy-design.md) | 架构设计 |
| [`firmware/README.md`](firmware/README.md) | 固件 / BLE（参考） |
| [`REFERENCE.md`](REFERENCE.md) | BLE 线缆协议 |

已结束会话在 App 中保留 **24 小时**；顶部统计的 `total` 仅计运行中 / 等待中会话。

## 开发

```bash
devpet-bridge restart
python3 tools/test_bridge_http.py
python3 tools/test_cursor_hook.py
cd app && npm test
```

贡献规范见 [`AGENTS.md`](AGENTS.md)、[`CONTRIBUTING.md`](CONTRIBUTING.md)。

## 固件参考（可选）

[`firmware/`](firmware/) 目录保留 **ESP32 硬件桌宠**参考实现（M5StickC / StickS3，BLE + Claude Desktop）。**手机用户无需刷固件。**

本项目的 Bridge 与 App 协议 **在固件协议基础上扩展**（相同宠物状态与设备指令），属于软件移植而非替代关系。

→ 编译烧录与 BLE 说明见 **[firmware/README.md](firmware/README.md)**

## 路线图

| 阶段 | 状态 |
| --- | --- |
| M1–M4 | 已完成 — 手机 App、Bridge、Hooks、WebSocket |
| 下一步 | mDNS 自动配对、dev build 通知、可选手机端 preToolUse |

## 赞助支持

DevPet 从固件参考、Bridge、Hooks 到手机 App，都是业余时间一点点打磨出来的。  
如果这个工具帮你省了来回切屏、让写代码时多了一点陪伴感，欢迎请我喝杯咖啡 ☕️  
**创作不易，感谢每一份支持！**

| 支付宝 | 微信 |
| --- | --- |
| <img src="docs/sponsor/alipay.png" alt="支付宝收款码" width="220"> | <img src="docs/sponsor/wechat.png" alt="微信赞赏码" width="220"> |

也欢迎通过 [GitHub Sponsors](https://github.com/sponsors/weikunzl) 支持（配置中）。

## 说明

Hook + Bridge + 手机路径为 **本地、自愿开启的开发者工具**（MVP 设计下数据仅在局域网传输）。Claude Desktop 的 BLE Hardware Buddy 面向硬件玩家，与手机 App 相互独立，见 [`firmware/README.md`](firmware/README.md)。
