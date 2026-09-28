# -*- coding: utf-8 -*-
"""
retrieval.py —— 纯标准库 TF-IDF 检索（字符 n-gram 分词，零依赖）。

为什么用字符 n-gram 而不是 jieba：
  - 语料是极短的口语短句（中位数 4 字），jieba 分词对短句效果差；
  - 字符 2-3 gram 天然覆盖「咋了 / 放屁 / 干嘛 / 然后呢」这类口头禅；
  - 零第三方依赖，服务器上无需装 jieba/sklearn/numpy。

用法：
  idx = TfidfIndex()
  for text, meta in docs:
      idx.add(text, meta)
  idx.finalize()
  idx.search("难受", top_n=5)   # -> [(text, meta, score), ...]
  idx.save(path) / TfidfIndex.load(path)
"""

import json
import math
import re
from collections import Counter, defaultdict

_CJK_RE = re.compile(r'[\u4e00-\u9fff]')
_WORD_RE = re.compile(r'[a-zA-Z0-9]+')


def tokenize(text: str) -> Counter:
    """把文本切成词项：中文 1/2/3-gram + 英文/数字连续串（≥2 字符）。"""
    text = (text or '').lower()
    terms = Counter()
    for w in _WORD_RE.findall(text):
        if len(w) >= 2:
            terms[w] += 1
    for run in _CJK_RE.findall(text):
        if len(run) == 1:              # 只有真正的单字串才保留 1-gram，避免「毛/球」这类误匹配
            terms[run] += 1
        for i in range(len(run) - 1):
            terms[run[i:i + 2]] += 1
        for i in range(len(run) - 2):
            terms[run[i:i + 3]] += 1
    return terms


class TfidfIndex:
    """倒排索引 + 余弦相似度 TF-IDF。"""

    def __init__(self):
        self.items = []            # [(text, meta)]
        self.postings = defaultdict(list)  # term -> [(doc_idx, tf)]
        self.df = Counter()        # term -> document frequency
        self.doc_terms = []        # 每个 doc 的 term 计数
        self.idf = {}
        self.doc_norms = []

    def __len__(self):
        return len(self.items)

    def add(self, text, meta=None):
        idx = len(self.items)
        self.items.append((text, meta))
        terms = tokenize(text)
        self.doc_terms.append(terms)
        for t, c in terms.items():
            self.postings[t].append((idx, c))
            self.df[t] += 1

    def finalize(self):
        n = len(self.items)
        for t, df in self.df.items():
            self.idf[t] = math.log((n + 1) / (df + 1)) + 1.0
        for terms in self.doc_terms:
            norm = math.sqrt(sum((c * self.idf[t]) ** 2 for t, c in terms.items()))
            self.doc_norms.append(norm or 1.0)

    def search(self, query, top_n=5):
        """返回 [(text, meta, cosine_score)]，按相似度降序。"""
        if not self.idf:
            self.finalize()
        q = tokenize(query)
        qw = {t: c * self.idf.get(t, 0.0) for t, c in q.items() if t in self.idf}
        qnorm = math.sqrt(sum(v * v for v in qw.values())) or 1.0
        scores = defaultdict(float)
        for t, qw_t in qw.items():
            for doc_idx, tf in self.postings.get(t, []):
                scores[doc_idx] += qw_t * (tf * self.idf[t])
        ranked = []
        for doc_idx, raw in scores.items():
            cos = raw / (self.doc_norms[doc_idx] * qnorm)
            ranked.append((cos, doc_idx))
        ranked.sort(key=lambda kv: -kv[0])
        out = []
        for cos, doc_idx in ranked[:top_n]:
            text, meta = self.items[doc_idx]
            out.append((text, meta, round(cos, 4)))
        return out

    def save(self, path):
        data = {
            'items': self.items,
            'postings': {t: v for t, v in self.postings.items()},
            'idf': self.idf,
            'doc_norms': self.doc_norms,
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)

    @classmethod
    def load(cls, path):
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        obj = cls()
        obj.items = [(t, m) for t, m in data['items']]
        obj.postings = defaultdict(list, {t: [tuple(x) for x in v]
                                          for t, v in data['postings'].items()})
        obj.idf = data['idf']
        obj.doc_norms = data['doc_norms']
        return obj
