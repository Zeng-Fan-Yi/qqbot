# 部署指南

## 一、本地跑通（开发调试）

1. **Python 3.12** + venv：
   ```bash
   python -m venv .venv
   .venv/Scripts/pip install -r requirements.txt   # Windows；Linux 用 .venv/bin/pip
   ```
2. 配密钥：`cp .env.example .env`，填 `DEEPSEEK_API_KEY` / `QWEN_API_KEY`。
3. 配身份：`cp config/persona.example.json config/persona.json`，填目标人物信息。
4. 准备数据：放 `data/chat.txt`，跑 `python -m scripts.extract_pairs` → `build_style` → `build_memory`。
5. 启动 bot：`python bot.py`（监听 `127.0.0.1:8080`）。
6. 启动 SnowLuma（注入桌面版 QQ），扫码登录小号；在 WebUI 配反向 WebSocket：
   `ws://127.0.0.1:8080/onebot/v11/ws`
7. 群里 @ 小号测试。

> 反向 WS 路径以 NoneBot2 启动日志 / OneBot 适配器为准，通常是 `/onebot/v11/ws`。

## 二、云服务器部署（7×24）

1. 买一台 **2C2G Linux VPS**（Ubuntu 22.04/24.04；无 GPU、无本地模型，配置不用高）。
2. 装 Docker + docker compose。
3. 上传项目（git 或 scp），准备 `.env`、`config/persona.json`。
4. `docker compose up -d --build`（拉起 bot + SnowLuma 两个容器）。
5. SnowLuma 容器首次启动：进 noVNC（`:6081`）扫码登录小号；OneBot 反向 WS 已指向 `ws://nonebot:8080/onebot/v11/ws`。
6. 群里 @ 小号验证。

## 三、风控注意（重要）

- **小号先养号**：加几个好友/进几个群、正常聊几天，别一上来就高频发言。
- 云服务器**异地登录**易触发风控：用已养熟的小号、登录后别频繁切 IP/换设备。
- 协议端选 SnowLuma（注入桌面版 QQ + 虚拟屏），比无头版 QQ 更不容易被风控。

## 四、可调参数

| 位置 | 参数 | 说明 |
|---|---|---|
| `config/persona.json` | `name` / `nicknames` / `address_words` / `other_names` / `groups` / `chat_senders` | 身份与群白名单 |
| `src/plugins/qq_persona/__init__.py` | `PROVIDER` | 默认模型 `deepseek` / `qwen` |
| 同上 | `LEARN_COOLDOWN` | 动态学习节流（秒） |
| `.env` | `HOST` / `PORT` | NoneBot2 监听地址 |
| `.env` | `DEEPSEEK_*` / `QWEN_*` | 模型与密钥 |
