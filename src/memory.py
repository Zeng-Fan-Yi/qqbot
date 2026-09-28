# -*- coding: utf-8 -*-
"""
memory.py —— 记忆存储与召回。

- 静态事实：info_corpus 蒸馏出的「目标人物过往」，一次性建索引。
- 动态学习：`add_fact()` 追加新事实并重建索引（阶段 3 接入后用于持续学习群里的人和事）。
- 召回：`recall(query)` 用 TF-IDF 按需检索，**默认不注入提示词**，由模型决定何时调用。

用法：
  from src.memory import MemoryStore
  m = MemoryStore()
  m.recall('游戏', top_n=3)   # -> [(fact, score), ...]
"""

import json
import threading
from pathlib import Path

from src.retrieval import TfidfIndex

BASE = Path(__file__).resolve().parent.parent
MEM_DIR = BASE / 'data' / 'memory'
FACTS_FILE = MEM_DIR / 'facts.jsonl'
INDEX_FILE = MEM_DIR / 'facts_index.json'


class MemoryStore:
    def __init__(self):
        self.facts = []
        self.index = None
        self._lock = threading.RLock()
        self.load()

    def load(self):
        if FACTS_FILE.exists():
            self.facts = [json.loads(l) for l in
                          FACTS_FILE.read_text(encoding='utf-8').splitlines() if l.strip()]
        if INDEX_FILE.exists():
            self.index = TfidfIndex.load(INDEX_FILE)

    def recall(self, query, top_n=3, min_score=0.5):
        """按需召回相关事实，返回 [(fact_text, score)]（低于 min_score 视为不相关）。"""
        if self.index is None:
            return []
        return [(meta['fact'], score) for _text, meta, score in self.index.search(query, top_n=top_n)
                if score >= min_score]

    def add_fact(self, fact, topic='其他', src='manual'):
        """追加一条事实到文件与内存（不重建索引，批量后再 rebuild()）。src 标记来源（manual=人工修正）。"""
        fact = fact.strip()
        if not fact:
            return
        with self._lock:
            if any(f['fact'] == fact for f in self.facts):
                return
            item = {'fact': fact, 'topic': topic}
            if src:
                item['src'] = src
            self.facts.append(item)
            with open(FACTS_FILE, 'a', encoding='utf-8') as f:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')

    def remove_facts(self, keyword):
        """删除 fact 中包含 keyword 的所有事实，返回删除条数。"""
        keyword = keyword.strip()
        if not keyword:
            return 0
        with self._lock:
            before = len(self.facts)
            self.facts = [f for f in self.facts if keyword not in f['fact']]
            removed = before - len(self.facts)
            if removed:
                with open(FACTS_FILE, 'w', encoding='utf-8') as f:
                    for x in self.facts:
                        f.write(json.dumps(x, ensure_ascii=False) + '\n')
                self.rebuild()
            return removed

    def rebuild(self):
        """重建 TF-IDF 索引（批量追加事实后调用一次）。"""
        with self._lock:
            idx = TfidfIndex()
            for x in self.facts:
                idx.add(x['fact'], x)
            idx.finalize()
            self.index = idx
            idx.save(INDEX_FILE)
