# -*- coding: utf-8 -*-
"""离线准确率评测：跑手写场景，对比「实际回没回」和「预期该不该回」。

指标：
- 该回命中率（precision）：标记该回的，bot 真回了的比例
- 不该回准确率（silence）：标记不该回的，bot 正确潜水的比例
- 总准确率（accuracy）

用法：python -m src.sim_eval
"""

import sys
from collections import deque

from src.memory import MemoryStore
from src.persona import Persona
from src.sim_scenarios import HAND_SCENARIOS

persona = Persona('deepseek')
memory = MemoryStore()
BOT_NAME = '周乾坤'


def judge_and_generate(ctx, since_at, sender, text, at_bot):
    """返回 (是否真的回, 回复文本)。逻辑与插件一致。"""
    ctx.append((sender, text))
    if at_bot:
        since_at[0] = 0
    else:
        since_at[0] += 1
    history = list(ctx)
    if at_bot:
        tone = '认真答'
    else:
        should, tone = persona._judge(history)
        if not should:
            return False, ''
        if since_at[0] > 10 and any(s == BOT_NAME for s, _t in list(ctx)[-6:]):
            return False, ''  # 频率控制
    _p, reply = persona._generate(history, memory, tone, must_reply=at_bot)
    reply = (reply or '').strip()
    if not reply or reply == '[SILENT]':
        return False, ''
    # 把 bot 的回复追加进上下文（连发逐条加），保持频率门控/接话逻辑一致
    for seg in reply.split('\n'):
        seg = seg.strip()
        if seg:
            ctx.append((BOT_NAME, seg))
    return True, reply


def main():
    only = None
    if '--only' in sys.argv:
        only = int(sys.argv[sys.argv.index('--only') + 1]) - 1

    scenarios = HAND_SCENARIOS if only is None else [HAND_SCENARIOS[only]]

    tp = fn = tn = fp = 0  # tp=该回且回了 fn=该回没回 tn=不该回没回 fp=不该回却回了
    detail = []
    for sc in scenarios:
        ctx = deque(maxlen=50)
        since_at = [999]  # 用列表做可变引用，起始视为很久没被@
        for sender, text, at_bot, should_reply in sc['messages']:
            replied, reply = judge_and_generate(ctx, since_at, sender, text, at_bot)
            if should_reply and replied:
                tp += 1
                mark = '✓回'
            elif should_reply and not replied:
                fn += 1
                mark = '✗漏回'
            elif not should_reply and not replied:
                tn += 1
                mark = '✓潜'
            else:
                fp += 1
                mark = '✗错回'
            detail.append((sc['name'], sender, text[:20], should_reply, mark,
                          (reply.split('\n')[0] if reply else '')[:20]))

    print(f'{"场景":<28} {"发送":<8} {"内容":<20} 预期  实际')
    for name, sender, text, should, mark, rep in detail:
        exp = '回' if should else '潜'
        print(f'{name:<28} {sender:<8} {text:<20} {exp}  {mark} {rep}')

    total = tp + fn + tn + fp
    prec = tp / (tp + fn) if (tp + fn) else 0
    sil = tn / (tn + fp) if (tn + fp) else 0
    acc = (tp + tn) / total if total else 0
    print(f'\n===== 结果 =====')
    print(f'该回命中率: {tp}/{tp+fn} = {prec:.0%}   (漏回 {fn} 条)')
    print(f'不该回准确率: {tn}/{tn+fp} = {sil:.0%}   (错回 {fp} 条)')
    print(f'总准确率: {tp+tn}/{total} = {acc:.0%}')


if __name__ == '__main__':
    main()
