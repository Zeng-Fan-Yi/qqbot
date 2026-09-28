# QQ 分身机器人

一个**模仿你朋友聊天风格**的 QQ 群机器人框架：把一个人的聊天记录蒸馏成它的「人格 + 记忆」，让 bot 在群里用 TA 的口气说话。

- 风格 100% 来自导出语料（不用你手写提示词）
- DeepSeek / Qwen 双模型可切换
- 静态 + 动态记忆（纯标准库字符 n-gram TF-IDF 检索，无本地模型、无 GPU）
- 魔法指令：`/on` `/off` `/memory` `/help` `/status` `/model` `/reset` `/ping`

技术栈：**Python + NoneBot2 + SnowLuma（OneBot v11 协议端）**。

## 三步蒸馏你自己的机器人

> 隐私数据（聊天记录、蒸馏产物、身份配置）都放在不入库的 `data/` 和 `config/persona.json` 里，不会进 git。

### 第 0 步：准备

1. 装依赖：`pip install -r requirements.txt`（Python 3.12）
2. 配密钥：`cp .env.example .env`，填 `DEEPSEEK_API_KEY` / `QWEN_API_KEY`
3. 配身份：`cp config/persona.example.json config/persona.json`，填你朋友的信息：

```json
{
  "name": "TA 的名字",
  "nicknames": ["外号"],
  "address_words": ["名字", "昵称"],
  "other_names": ["群友A", "群友B"],
  "groups": [123456789],
  "chat_senders": ["TA 在聊天记录导出里的发送人名字"]
}
```

4. 导出聊天记录，保存为 `data/chat.txt`（QQ 电脑端「消息管理器」导出的 .txt 格式）。

### 第 1 步：提取对话对

```bash
python -m scripts.extract_pairs
# 产出 data/pairs.jsonl（「对方消息 → TA 回复」）
```

### 第 2 步：构建风格索引 + 蒸馏记忆

```bash
python -m scripts.build_style     # 产出 data/style/（few-shot + 动态检索索引）
python -m scripts.build_memory    # 蒸馏 data/memory/（记忆事实 + 索引，需 LLM key）
```

### 第 3 步：启动

```bash
python bot.py
```

再用 SnowLuma（或 NapCat）扫码登录小号，把 OneBot v11 反向 WebSocket 指向 bot（NoneBot2 默认监听 `HOST/PORT`，见 `.env`）。

## 云服务器部署

```bash
docker compose up -d
```

`docker-compose.yml` 含 bot + SnowLuma 两个服务；SnowLuma 首次启动访问 noVNC（`:6081`）扫码登录小号，OneBot 反向 WS 已指向 `nonebot:8080`。

## 魔法指令（群里 @ 它）

| 指令 | 作用 |
|---|---|
| `/on` / `/off` | 开启 / 关闭 |
| `/memory 内容` | 加一条记忆 |
| `/memory list` | 列出额外学的记忆 |
| `/memory del 词` | 删含关键词的记忆 |
| `/help` | 列出所有指令 |
| `/status` | 看状态（开关/模型/记忆条数） |
| `/model deepseek` / `/model qwen` | 切模型 |
| `/reset` | 清空当前群上下文 |
| `/ping` | 健康检查 |

## 离线评测

```bash
python -m src.eval_style       # 20 条 × 两模型，看像不像 + 多样性
python -m src.eval_vs_real     # 抽真实对话对，逐条对比 bot vs 真人
python -m src.eval_swear       # 抽骂人/怼人样本，看对不对味
```

## 目录结构

```
bot.py / pyproject.toml / Dockerfile / docker-compose.yml / requirements.txt
config/
  persona.example.json   身份配置模板（复制成 persona.json 填你自己的）
scripts/
  extract_pairs.py       第 1 步：聊天记录 → 对话对
  build_style.py         第 2 步：对话对 → 风格索引
  build_memory.py        第 2 步：对话对 → 记忆事实
src/
  retrieval.py   纯标准库字符 n-gram TF-IDF
  llm.py         统一 LLM 客户端（DeepSeek/Qwen，工具调用 + 降级）
  guard.py       输出软护栏
  config.py      加载 config/persona.json
  persona.py     人格层（提示词 + few-shot + 动态检索 + recall_memory）
  memory.py      记忆存储（静态 + 动态学习 + 召回）
  learner.py     动态学习：从群聊抽稳定事实
  plugins/qq_persona/   NoneBot2 插件（@必回 + 主动接话 + 学习 + 魔法指令）
data/            不入库：语料、聊天记录、蒸馏产物（chat.txt 放这里）
```

## 隐私说明

- `.env`（API key）、`config/persona.json`（身份）、`data/`（聊天记录+蒸馏产物）、`tools/`（部署脚本）都不入库；
- 其余代码完全通用，换一个人只需换 `data/chat.txt` + `config/persona.json`，重跑三步即可。
