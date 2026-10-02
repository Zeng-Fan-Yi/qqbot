# -*- coding: utf-8 -*-
"""
learner.py —— 动态学习：从群聊中抽取稳定事实，追加进记忆。

- 只抽"群里的人和事 / 关系 / 计划 / 目标人物自己的新信息"；
- 不注入提示词、不主动提旧事（抽到的事实由 recall_memory 按需召回）。
"""

import json
import re

from src.config import load_persona
from src.llm import LLMClient

_PERSONA = load_persona()
_NAME = _PERSONA['name']

EXTRACT_PROMPT = (
    f'从下面这段群聊里，提取值得长期记住的稳定信息，存进「{_NAME}」的记忆（之后被问到时能据此回答）。'
    '只输出 JSON 数组（不要解释）：\n'
    '[{"fact": "短句", "topic": "人物|关系|偏好|知识|事件|计划|其他"}]\n'
    '规则：\n'
    f'- 站在「{_NAME}」的视角写，fact ≤20 字。\n'
    '- 重点学【知识/事实】：大家聊到的具体内容，比如三国杀有多少武将、某游戏怎么玩、某门课什么内容。'
    '例：「三国杀武将大约五百到一千个」「造梦西游要先下载」「科一考交通法规」。\n'
    f'- 也学【人物/关系/偏好】：谁是谁、谁和谁什么关系、{_NAME} 喜欢/会/爱玩什么。\n'
    '- 只记稳定、以后用得到的信息；以下一律输出 {"fact": null}：\n'
    '  ① 纯问题/反问（谁问谁什么）、打招呼、寒暄、纯情绪、纯表情；\n'
    '  ② 一次性话题（今天吃啥、临时约局）；\n'
    f'  ③ {_NAME} 自己刚说过的话（那是它说的话，不是事实）；\n'
    '  ④ 开玩笑、打情骂俏、吹牛。\n'
    '- 没有可记的就输出 []。\n'
    '输入群聊：\n'
)


FILTER_PROMPT = (
    '看下面这段群聊，判断里面有没有值得长期记住的稳定信息'
    '（聊到的具体知识/事实、谁是谁、谁和谁什么关系、偏好、计划）。只输出：有 或 无。\n'
    '以下都算「无」：纯寒暄、纯情绪、纯表情、纯问题/反问（谁问谁什么）、一次性话题、开玩笑、吹牛。\n'
)


def _has_learnable(text: str, provider='deepseek'):
    """第一步：筛选——这段群聊有没有值得学的。"""
    if not (text or '').strip():
        return False
    client = LLMClient(provider, temperature=0.1, max_tokens=4)
    try:
        out = client.chat([{'role': 'user', 'content': FILTER_PROMPT + text}])
        return (out or '').strip().startswith('有')
    except Exception:
        return False


def extract_facts(text: str, provider='deepseek'):
    """从群聊文本抽取事实列表 [{fact, topic}]；失败返回 []。先筛选再提炼。"""
    if not (text or '').strip():
        return []
    # 第一步：筛选（没有值得学的就直接跳过，省一次大调用）
    if not _has_learnable(text, provider):
        return []
    # 第二步：提炼
    client = LLMClient(provider, temperature=0.2, max_tokens=800)
    try:
        out = client.chat([{'role': 'user', 'content': EXTRACT_PROMPT + text}])
        m = re.search(r'\[.*\]', out, re.S)
        if not m:
            return []
        arr = json.loads(m.group())
    except Exception:
        return []
    facts = []
    for x in arr:
        if isinstance(x, dict) and x.get('fact'):
            facts.append({'fact': str(x['fact']).strip(),
                          'topic': str(x.get('topic', '其他')).strip()})
    return facts


def learn_from_text(memory, text, provider='deepseek'):
    """抽取并批量追加到记忆，返回新增条数。"""
    new_facts = extract_facts(text, provider)
    added = 0
    for f in new_facts:
        if any(old['fact'] == f['fact'] for old in memory.facts):
            continue
        memory.add_fact(f['fact'], f['topic'], src='dynamic')
        added += 1
    if added:
        memory.rebuild()
    return added
