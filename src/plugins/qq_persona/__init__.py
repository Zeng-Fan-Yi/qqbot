# -*- coding: utf-8 -*-
"""QQ 群机器人插件：模仿指定人物的聊天风格。

- 通读群消息，维护每群最近 50 条上下文。
- 每条群消息都交给 LLM 判断：被 @ / 点名 → 必回；否则由模型自己决定回不回（[SILENT] 潜水）。
- 不设时间冷却/次数上限——回不回完全交给模型判断。
- 回复走 persona.reply_group（含动态 few-shot + recall_memory 记忆召回）。
"""

import asyncio
import random
import re
import time
from collections import defaultdict, deque

from nonebot import on_message
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageSegment
from nonebot.plugin import PluginMetadata

from src.config import load_persona
from src.learner import learn_from_text
from src.memory import MemoryStore
from src.persona import Persona

_PERSONA = load_persona()
_NAME = _PERSONA['name']

__plugin_meta__ = PluginMetadata(
    name="QQ 分身",
    description="模仿指定人物风格的 QQ 群机器人",
    usage="群里 @ 它即回复；正常聊天时由它自己判断要不要接话",
)

# 运行时配置（后续可挪到 .env）
PROVIDER = 'deepseek'
LEARN_COOLDOWN = 300    # 每群动态学习最小间隔（秒）——只控制"学习"频率，不影响回复
ADDRESS_WORDS = tuple(_PERSONA.get('address_words', []))  # 群里点名这些词 = 在跟他说话，等同 @ 必回
GROUP_WHITELIST = tuple(_PERSONA.get('groups', []))       # 只在指定群回话，其他群全部沉默
BARE_ACK = {'哦', '嗯', '好', '行', '哈哈', '哈哈哈', '确实', '对', '是的', '好的', '嗯嗯', '666', '。', '。。', '。。。', '...', '..'}  # 纯结束语/语气词，不回
OTHER_NAMES = tuple(_PERSONA.get('other_names', []))      # 群里提到这些人/角色而没提到自己 → 不回

enabled = True  # 开关：@bot /off 关闭、/on 开启（关闭后只响应 /on）

persona = Persona(PROVIDER)
memory = MemoryStore()

contexts = defaultdict(lambda: deque(maxlen=50))   # group_id -> [(sender, text)]
last_learn = {}                                    # group_id -> 上次学习时间戳
_tasks = set()                                     # 持有后台学习任务的引用，防止被 GC

matcher = on_message(priority=10, block=False)


def _sender_name(event: GroupMessageEvent) -> str:
    try:
        return event.sender.card or event.sender.nickname or str(event.user_id)
    except Exception:
        return str(event.user_id)


_SILENT_CORES = {'SILENT', '无视', '沉默', '不回', '不回复', '不插嘴'}


def _is_silent(reply: str) -> bool:
    """判断模型输出是否表示「不回复」。兼容 [SILENT] / 【无视】/ 无视 等写法。"""
    r = (reply or '').strip().replace('【', '[').replace('】', ']')
    core = r.strip('[]').strip().upper()
    return core == '' or core in _SILENT_CORES


def _has_other_at(event: GroupMessageEvent) -> bool:
    """消息是否 @ 了别人（非 bot 自己）→ 这种是别人在点名别人，不插嘴。"""
    try:
        for seg in event.get_message():
            if seg.type == 'at' and str(seg.data.get('qq', '')) != str(event.self_id):
                return True
    except Exception:
        pass
    for m in re.finditer(r'\[at:qq=(\d+)\]', str(event.original_message)):
        if m.group(1) != str(event.self_id):
            return True
    return False


async def _learn(gid):
    """动态学习：抽最近群聊里的稳定事实，追加进记忆（线程池跑，避免阻塞事件循环）。"""
    now = time.time()
    if now - last_learn.get(gid, 0.0) < LEARN_COOLDOWN:
        return
    last_learn[gid] = now
    ctx = list(contexts[gid])
    if len(ctx) < 3:
        return
    text = '\n'.join(f'{s}: {t}' for s, t in ctx if s != _NAME)  # 排除 bot 自己说过的话
    loop = asyncio.get_running_loop()
    try:
        added = await loop.run_in_executor(None, learn_from_text, memory, text)
        if added:
            logger.info(f'[动态学习] 群 {gid} 新增 {added} 条记忆')
    except Exception as e:
        logger.warning(f'[动态学习] 群 {gid} 失败: {e}')


@matcher.handle()
async def handle(bot: Bot, event: GroupMessageEvent):
    global enabled
    if not isinstance(event, GroupMessageEvent):
        return
    gid = event.group_id
    # 群白名单：非指定群直接忽略（不回复、不学习）
    if gid not in GROUP_WHITELIST:
        return
    text = (event.get_plaintext() or '').strip()

    # 被 @ 或群里点名（address_words 里的词）→ 必回
    is_at = bool(getattr(event, 'is_tome', lambda: False)()) or any(w in text for w in ADDRESS_WORDS)

    # 魔法指令：@bot /memory 内容（加）/ del 关键词（删）/ list（列出额外学的记忆）
    if is_at and text.startswith('/memory'):
        arg = text[len('/memory'):].strip()
        if arg in ('list', '列表'):
            learned = [f for f in memory.facts if f.get('src') != 'curated']
            if not learned:
                await matcher.send(MessageSegment.text('还没有额外学的记忆'))
            else:
                lines = [f['fact'] for f in learned]
                for i in range(0, len(lines), 15):
                    await matcher.send(MessageSegment.text('\n'.join(lines[i:i + 15])))
        elif arg.startswith('del ') or arg.startswith('删 '):
            kw = arg[4:].strip() if arg.startswith('del ') else arg[2:].strip()
            n = memory.remove_facts(kw)
            await matcher.send(MessageSegment.text('记忆修改成功' if n else f'没找到含「{kw}」的记忆'))
        elif arg:
            memory.add_fact(arg, '人工修正', src='manual')
            memory.rebuild()
            await matcher.send(MessageSegment.text('记忆修改成功'))
        else:
            await matcher.send(MessageSegment.text('用法：/memory 内容（加） /memory del 关键词（删） /memory list（列出）'))
        return

    # 开关指令：@bot /off 关闭、/on 开启
    if is_at and text in ('/off', '/关闭', '/stop', '/停'):
        enabled = False
        await matcher.send(MessageSegment.text('关了'))
        return
    if is_at and text in ('/on', '/开启', '/start', '/开'):
        enabled = True
        await matcher.send(MessageSegment.text('开了'))
        return

    # 帮助：列出所有指令
    if is_at and text in ('/help', '/指令', '/帮助', '/菜单'):
        await matcher.send(MessageSegment.text(
            '/on 开启\n/off 关闭\n/memory 内容 加记忆\n/memory list 列记忆\n/memory del 词 删记忆\n/model deepseek|qwen 切模型\n/reset 失忆\n/status 状态\n/ping 在吗'))
        return

    # 状态
    if is_at and text in ('/status', '/状态'):
        st = '开' if enabled else '关'
        await matcher.send(MessageSegment.text(f'状态：{st}｜模型：{persona.provider}｜记忆：{len(memory.facts)} 条'))
        return

    # 切模型
    if is_at and text.startswith('/model'):
        m = text[len('/model'):].strip().lower()
        if m in ('deepseek', 'qwen'):
            persona.provider = m
            await matcher.send(MessageSegment.text(f'已切到 {m}'))
        else:
            await matcher.send(MessageSegment.text('用法：/model deepseek 或 /model qwen'))
        return

    # 失忆：清空当前群上下文
    if is_at and text in ('/reset', '/失忆'):
        contexts[gid].clear()
        await matcher.send(MessageSegment.text('忘了'))
        return

    # 健康检查
    if is_at and text in ('/ping', '/在吗'):
        await matcher.send(MessageSegment.text('在'))
        return

    # 关闭状态：不回复（以上魔法指令仍可用）
    if not enabled:
        return

    if not text:
        if is_at:
            text = '？'  # 被 @ 或点名但没文字，用问号触发回复
        else:
            return

    contexts[gid].append((_sender_name(event), text))

    # 纯结束语/语气词（"哦/嗯/好/哈哈"），没@没点名 → 不回（但已记入上下文）
    if not is_at and text in BARE_ACK:
        return

    # 在提别人（other_names 里的人）而没提到自己（且没有"你"）→ 不回，别替别人答
    if not is_at and any(n in text for n in OTHER_NAMES) and '你' not in text:
        return

    # @ 了别人（不是自己）→ 别人在点名别人，不插嘴
    if not is_at and _has_other_at(event):
        return

    # 主动插嘴频率控制：最近 6 条里已经发过言，就不再主动插嘴（@/点名仍必回）；
    # 但上一条紧挨着就是 bot 自己说的（对方在接 bot 的话）→ 不算主动插嘴，允许回。
    if not is_at:
        _c = list(contexts[gid])
        _prev_is_me = len(_c) >= 2 and _c[-2][0] == _NAME
        if not _prev_is_me and any(s == _NAME for s, _t in _c[-6:]):
            return

    # 每条群消息都交给 LLM 判断回不回
    history = list(contexts[gid])
    _provider, reply = persona.reply_group(history, memory, must_reply=is_at)
    reply = (reply or '').strip()
    if _is_silent(reply):
        return

    # 连发：按换行拆成多条消息，模拟人类一条一条发
    segments = [s.strip() for s in reply.split('\n') if s.strip()][:5]
    for i, seg in enumerate(segments):
        await matcher.send(MessageSegment.text(seg))
        contexts[gid].append((_NAME, seg))  # 记住自己说了啥，保持对话连贯
        if i < len(segments) - 1:
            await asyncio.sleep(random.uniform(0.4, 1.0))
    task = asyncio.create_task(_learn(gid))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
