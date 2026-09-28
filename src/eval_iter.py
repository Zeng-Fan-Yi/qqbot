# -*- coding: utf-8 -*-
"""迭代评测：抽长回复+短回复混合样本，对比长度分布与内容差异。"""
import json
import random
from pathlib import Path

from src.memory import MemoryStore
from src.persona import Persona

BASE = Path(__file__).resolve().parent.parent


def load_pairs():
    out = []
    for l in (BASE / 'data' / 'pairs.jsonl').read_text(encoding='utf-8').splitlines():
        if l.strip():
            out.append(json.loads(l))
    return out


def ok(o):
    p = (o.get('prev') or '').strip()
    r = (o.get('reply') or '').strip()
    if not p or not r:
        return False
    if any(k in p for k in ('[图片', '[表情', 'http', '[视频', '[语音', '[文件')):
        return False
    if not (2 <= len(p) <= 40):
        return False
    return True


def main():
    pairs = [o for o in load_pairs() if ok(o)]
    long = [o for o in pairs if len(o['reply'].strip()) >= 8]
    short = [o for o in pairs if len(o['reply'].strip()) <= 4]
    print(f'长回复样本 {len(long)}，短回复样本 {len(short)}')

    random.seed(8888)
    sample = random.sample(long, 15) + random.sample(short, 15)
    random.shuffle(sample)

    persona = Persona('deepseek')
    memory = MemoryStore()

    rlens, blens = [], []
    for o in sample:
        prev = o['prev'].strip()
        real = o['reply'].strip()
        _p, bot = persona.reply_group([('对方', prev)], memory, must_reply=True)
        bot = (bot or '').replace('\n', ' ').strip()
        rlens.append(len(real))
        blens.append(len(bot))
        print(f'对方：{prev}')
        print(f'  真实({len(real)})：{real}')
        print(f'  bot ({len(bot)})：{bot}')

    print('\n=== 统计 ===')
    print(f'真实回复 平均 {sum(rlens)/len(rlens):.1f} 字，bot 平均 {sum(blens)/len(blens):.1f} 字')
    for label, lens in (('真实', rlens), ('bot ', blens)):
        d = {'短(≤4)': 0, '中(5-7)': 0, '长(≥8)': 0}
        for x in lens:
            d['短(≤4)' if x <= 4 else '中(5-7)' if x <= 7 else '长(≥8)'] += 1
        print(f'{label}分布：' + '  '.join(f'{k}={v}' for k, v in d.items()))


if __name__ == '__main__':
    main()
