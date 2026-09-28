# -*- coding: utf-8 -*-
"""
build_memory.py —— 从 info_corpus 蒸馏目标人物的过往事实，建 TF-IDF 记忆索引。

- 去重 → LLM 蒸馏成 ≤20 字的短句事实 → 去重 → 存 facts.jsonl + facts_index.json
- 用法：
    python -m scripts.build_memory                 # 全量
    python -m scripts.build_memory --limit 40      # 只处理前 40 条（验证用）
"""

import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

from src.config import load_persona
from src.llm import LLMClient
from src.retrieval import TfidfIndex

_NAME = load_persona()['name']

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / 'data'
INFO = DATA / 'info_corpus.txt'
MEM_DIR = DATA / 'memory'
FACTS_FILE = MEM_DIR / 'facts.jsonl'
INDEX_FILE = MEM_DIR / 'facts_index.json'

BATCH = 20

DISTILL_PROMPT = (
    f'你是信息提炼器。下面每条是「{_NAME}」在 QQ 里说过的一句话，'
    '把其中透露出的、关于他本人的稳定信息（经历/偏好/技能/关系/计划/正在做的事/观点）提炼成一条短句。'
    '只输出 JSON 数组（不要任何解释）：\n'
    '[{"fact": "短句", "topic": "游戏|学习|课程|人物|地点|事件|偏好|技能|其他"}]\n'
    '规则：\n'
    f'- fact ≤20 字，站在{_NAME}的视角写，例如「爱打游戏」「在北京上学」「想去看电影」。\n'
    '- 只提炼"长期/稳定的信息"。以下都输出 {"fact": null}：玩笑、打情骂俏、一时情绪、'
    '单次行为、反问、纯吐槽、说的是别人。\n'
    '- 只提炼原话里已有的信息，绝不编造。\n'
    '输入消息（按序号）：\n'
)


def load_and_dedupe():
    lines = [l.strip() for l in INFO.read_text(encoding='utf-8').splitlines() if l.strip()]
    seen, uniq = set(), []
    for l in lines:
        if l not in seen:
            seen.add(l)
            uniq.append(l)
    return uniq


def distill_batch(client, msgs):
    numbered = '\n'.join(f'{i + 1}. {m}' for i, m in enumerate(msgs))
    try:
        out = client.chat(
            [{'role': 'user', 'content': DISTILL_PROMPT + numbered}],
            temperature=0.2, max_tokens=2000)
        m = re.search(r'\[.*\]', out, re.S)
        if not m:
            return [None] * len(msgs)
        arr = json.loads(m.group())
        if not isinstance(arr, list):
            return [None] * len(msgs)
        if len(arr) < len(msgs):
            arr = arr + [None] * (len(msgs) - len(arr))
        return arr[:len(msgs)]
    except Exception as e:
        print(f'    批次失败: {e}')
        return [None] * len(msgs)


def main():
    limit = None
    if '--limit' in sys.argv:
        limit = int(sys.argv[sys.argv.index('--limit') + 1])

    msgs = load_and_dedupe()
    print(f'去重后消息: {len(msgs)} 条')
    if limit:
        msgs = msgs[:limit]
        print(f'（仅处理前 {limit} 条）')

    client = LLMClient('deepseek', temperature=0.2, max_tokens=2000)
    facts = []
    for i in range(0, len(msgs), BATCH):
        batch = msgs[i:i + BATCH]
        results = distill_batch(client, batch)
        for src, r in zip(batch, results):
            if isinstance(r, dict) and r.get('fact'):
                facts.append({'fact': str(r['fact']).strip(),
                              'topic': str(r.get('topic', '其他')).strip(),
                              'src': src})
        print(f'  处理 {min(i + BATCH, len(msgs))}/{len(msgs)}，累计事实 {len(facts)}')

    seen, uniq_facts = set(), []
    for f in facts:
        if f['fact'] not in seen:
            seen.add(f['fact'])
            uniq_facts.append(f)
    print(f'事实去重: {len(facts)} -> {len(uniq_facts)}')

    MEM_DIR.mkdir(exist_ok=True)
    with open(FACTS_FILE, 'w', encoding='utf-8') as f:
        for x in uniq_facts:
            f.write(json.dumps(x, ensure_ascii=False) + '\n')

    idx = TfidfIndex()
    for x in uniq_facts:
        idx.add(x['fact'], x)
    idx.finalize()
    idx.save(INDEX_FILE)

    print(f'已保存 {FACTS_FILE} ({len(uniq_facts)} 条) 和 {INDEX_FILE}')
    print('话题分布:', dict(Counter(x['topic'] for x in uniq_facts)))
    random.seed(1)
    print('抽样:')
    for x in random.sample(uniq_facts, min(20, len(uniq_facts))):
        print(f'  [{x["topic"]}] {x["fact"]}')


if __name__ == '__main__':
    main()
