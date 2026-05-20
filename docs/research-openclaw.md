# OpenClaw 分析报告：Sisyphus 进化参考

**分析日期**: 2026-05-20
**来源**: github.com/openclaw/openclaw (37 万星)

## 概述

OpenClaw 是一个个人 AI 助手框架，local-first 架构，支持 20+ 消息通道。
TypeScript 实现，MIT 许可。

## 值得学习的

### 1. 层次化 AGENTS.md

每个核心模块有独立的 AGENTS.md 定义边界规则：

```
repo-root/AGENTS.md          ← 全局约定
extensions/AGENTS.md         ← 插件/扩展边界
src/channels/AGENTS.md       ← 通道层规则
src/plugin-sdk/AGENTS.md     ← SDK 合约
src/plugins/AGENTS.md        ← 插件加载/注册
src/gateway/protocol/AGENTS.md ← 网关协议
```

**对 Sisyphus 的启发**: 随着项目增长，不同模块（memory / skill / channel）应有自己的边界文档。

### 2. Gateway 架构

单一控制面管理所有 session、channel、tool、event。客户端通过 WebSocket 连接，gateway 负责路由。

### 3. Plugin SDK

- `src/plugin-sdk/` 定义了公开插件合约
- 第三方扩展通过 SDK 接入，不需改核心
- Bundled plugins 在 `extensions/` 目录

### 4. Skills 平台

- Bundled / managed / workspace 三级 skill
- ClawHub 技能市场
- 安装时有权限提示

### 5. 多通道设计

支持 WhatsApp / Telegram / Discord / Slack / WeChat / QQ 等 20+ 平台。
核心通道逻辑在 `src/channels/`，插件化加载。

## 不适用于 Sisyphus 的

- TypeScript 技术栈（Sisyphus 用 Python，更轻量）
- 多通道现在是过度设计（Sisyphus 目前只有微信）
- Gateway + Node 架构太重

## 关键收获

> AGENTS.md 的层次化边界定义 + 插件 SDK 设计——等 Sisyphus 长大后再学。
> 现在最需要的是 memory，不是 multi-channel。
