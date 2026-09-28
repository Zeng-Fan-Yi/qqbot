# -*- coding: utf-8 -*-
"""抽 30 组目标人物骂人/怼人的对话对，对比 bot 输出对不对味。"""
import json
import random
from pathlib import Path

from src.memory import MemoryStore
from src.persona import Persona

BASE = Path(__file__).resolve().parent.parent

SWEAR = ('放屁', '我呸', '滚', '几把', '他妈', '妈的', '傻逼', '狗屁', '废物',
         '离谱', '你妈', '垃圾', '智障', '憨批', '草', '死', '你配', '尼玛', '逼')


def load():
    out = []
    for l in (BASE / 'data' / 'pairs.jsonl').read_text(encoding='utf-8').splitlines():
        if l.strip():
            o = json.loads(l)
            r = o.get('reply') or ''
            if any(w in r for w in SWEAR) and len(r) >= 2:
                out.append(o)
    return out


def main():
    pairs = load()
    print(f'骂人样本 {len(pairs)} 条，抽 30 条\n')
    random.seed(666)
    sample = random.sample(pairs, 30)

    persona = Persona('deepseek')
    memory = MemoryStore()

    for i, o in enumerate(sample, 1):
        prev = o['prev'].strip()
        real = o['reply'].strip()
        _p, bot = persona.reply_group([('对方', prev)], memory, must_reply=True)
        bot = (bot or '').replace('\n', '⏎').strip()
        print(f'[{i}] 对方：{prev}')
        print(f'    真实：{real}')
        print(f'    bot ：{bot}')
        print('-' * 80)


if __name__ == '__main__':
    main()
