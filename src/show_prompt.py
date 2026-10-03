# -*- coding: utf-8 -*-
"""
show_prompt.py —— 打印某段群聊实际拼出来的完整提示词（判断 + 生成两步）。

用法：
    python -m src.show_prompt

把 chat_with_fallback 拦下来，原样打印每次发给 LLM 的 system / user 消息，
用来看上下文、few-shot、记忆、指令到底有没有拼对。
"""

import src.persona as P
from src.memory import MemoryStore
from src.persona import Persona

persona = Persona('deepseek')
memory = MemoryStore()

_orig = P.chat_with_fallback


def dump(msgs, *a, **k):
    print('  --- [system] ---')
    print(msgs[0]['content'])
    print('  --- [user] ---')
    print(msgs[-1]['content'])
    print()
    return ('deepseek', '[占位]')  # 让调用方 unpack 不报错


def main():
    # 复现场景
    scenario = [
        ('曾凡义', '兄弟们干嘛呢', False),
        ('曾凡义', '@周乾坤 问你话呢', True),
    ]

    from collections import deque
    ctx = deque(maxlen=50)
    for sender, text, at_bot in scenario:
        ctx.append((sender, text))
        history = list(ctx)

        if at_bot:
            print(f'===== 消息「{text}」被@，必回 → 直接进生成步 =====')
            P.chat_with_fallback = dump
            persona._generate(history, memory, '认真答', must_reply=True)
        else:
            print(f'===== 消息「{text}」未@ → 先进判断步 =====')
            P.chat_with_fallback = dump
            should, tone = persona._judge(history)
            print(f'    → 判断结果: {("回/" + tone) if should else "不（潜水）"}')
        print()


if __name__ == '__main__':
    main()
