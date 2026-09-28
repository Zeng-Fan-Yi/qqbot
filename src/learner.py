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
    '从下面这段群聊里，提取值得长期记住的稳定信息（关于群里的人、他们的关系、'
    f'正在发生/计划中的事、以及「{_NAME}」自己透露的新信息）。只输出 JSON 数组（不要解释）：\n'
    '[{"fact": "短句", "topic": "人物|关系|事件|计划|偏好|其他"}]\n'
    '规则：\n'
    f'- fact ≤20 字，站在{_NAME}视角写，例如「张三要去北京实习」「我和李四组队打游戏」。\n'
    '- 只记稳定/有用的信息；玩笑、寒暄、一次性话题、纯情绪，不记。\n'
    '- 没有可记的就输出 []。\n'
    '输入群聊：\n'
)


def extract_facts(text: str, provider='deepseek'):
    """从群聊文本抽取事实列表 [{fact, topic}]；失败返回 []。"""
    if not (text or '').strip():
        return []
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
        memory.add_fact(f['fact'], f['topic'])
        added += 1
    if added:
        memory.rebuild()
    return added
