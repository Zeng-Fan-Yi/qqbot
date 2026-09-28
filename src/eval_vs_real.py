# -*- coding: utf-8 -*-
"""离线对比：抽 20 组真实对话（prev→目标人物真实回复），喂给 bot，对比输出差异。"""
import json
import random
from collections import Counter
from pathlib import Path

from src.memory import MemoryStore
from src.persona import Persona

BASE = Path(__file__).resolve().parent.parent


def load_pairs():
    pairs = []
    for l in (BASE / 'data' / 'pairs.jsonl').read_text(encoding='utf-8').splitlines():
        if not l.strip():
            continue
        o = json.loads(l)
        pairs.append(o)
    return pairs


def is_substantive(o, min_reply=8):
    p = (o.get('prev') or '').strip()
    r = (o.get('reply') or '').strip()
    if not p or not r:
        return False
    # 去掉纯表情/图片/链接类
    if any(k in p for k in ('[图片', '[表情', 'http', '[视频', '[语音', '[文件')):
        return False
    if len(p) < 2 or len(p) > 40:
        return False
    if len(r) < min_reply:
        return False
    return True


def main():
    pairs = [o for o in load_pairs() if is_substantive(o, min_reply=8)]
    print(f'长回复样本（真实回复≥8字）{len(pairs)} 条，抽取 30 条\n')
    random.seed(99)
    sample = random.sample(pairs, 30)

    persona = Persona('deepseek')
    memory = MemoryStore()

    print('=' * 90)
    for i, o in enumerate(sample, 1):
        prev = o['prev'].strip()
        real = o['reply'].strip()
        hist = [('对方', prev)]
        _prov, bot = persona.reply_group(hist, memory, must_reply=True)
        bot = (bot or '').replace('\n', '⏎').strip()
        real_disp = real.replace('\n', '⏎')
        print(f'[{i}] 对方：{prev}')
        print(f'    真实({len(real)}字)：{real_disp}')
        print(f'    bot ({len(bot)}字)：{bot}')
        print('-' * 90)


if __name__ == '__main__':
    main()
