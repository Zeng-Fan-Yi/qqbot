# -*- coding: utf-8 -*-
"""
build_style.py —— 从 pairs.jsonl 构建风格资产：
  1) 动态 few-shot 检索索引（对「对方消息」建 TF-IDF，供"检索式风格"用）；
  2) 静态 few-shot 集（按 认同/追问/怼人/否定/长句/其他 分类，去重取高频）。

用法（项目根目录）：python -m src.build_style
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from src.retrieval import TfidfIndex

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / 'data'
PAIRS = DATA / 'pairs.jsonl'
STYLE_DIR = DATA / 'style'
INDEX_FILE = STYLE_DIR / 'pairs_index.json'
FEWSHOT_JSON = STYLE_DIR / 'few_shot.json'
FEWSHOT_TXT = STYLE_DIR / 'few_shot.txt'

# ---- 静态 few-shot 分类关键词（来自方案 §5 的口头禅清单）----
ACK = {'哦', '嗯', '对'}                                   # 应答（中性，应付普通陈述）
AGREE = {'确实', '不错', '有理', '是的', '对呀', '我也是', '厉害'}  # 认同（正面，回应报喜/求认同）
CHAL = {'我呸', '放屁', '呸', '离谱', '狗屁', '滚', '去你妈的', '去你的', '去你的吧'}
ASK = {'咋了', '干嘛呢', '然后呢', '那怎么办', '为啥', '为什么', '怎么说', '还有呢', '啥意思', '这啥'}
DENY = {'不知道', '没有', '不会', '不了'}


def classify(reply: str) -> str:
    r = reply.strip()
    if r in AGREE:
        return 'agree'
    if r in ACK:
        return 'ack'
    if r in CHAL or r.startswith(('我呸', '放屁', '滚', '狗屁', '去你')):
        return 'chal'
    if r in ASK or r.startswith(('咋了', '干嘛', '然后', '那怎么办', '为啥', '为什么', '怎么', '还有呢', '啥意思', '这啥')):
        return 'ask'
    if r in DENY:
        return 'deny'
    if len(r) >= 8:
        return 'long'
    return 'other'


def load_pairs():
    pairs = []
    with open(PAIRS, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                pairs.append(json.loads(line))
    return pairs


def build_static_fewshot(pairs, per_cat=8):
    """按 reply 分类，同类内去重 reply 后按词频取 top-per_cat。"""
    buckets = defaultdict(list)
    for p in pairs:
        buckets[classify(p['reply'])].append(p)

    freq = Counter(p['reply'] for p in pairs)
    fewshot = {}
    for cat in ('ack', 'agree', 'chal', 'ask', 'deny', 'long', 'other'):
        plist = buckets.get(cat, [])
        seen = {}
        for p in plist:
            if p['reply'] not in seen:
                seen[p['reply']] = p
        uniq = list(seen.values())
        # 高频在前（更"口头禅"），其次短句优先
        uniq.sort(key=lambda p: (-freq[p['reply']], len(p['reply'])))
        fewshot[cat] = [{'prev': p['prev'], 'reply': p['reply']} for p in uniq[:per_cat]]
    return fewshot, {c: len(buckets.get(c, [])) for c in fewshot}


# 只保留"正常聊天"规模的对话对：prev 太长=粘贴的长文，reply 太长=小作文
PREV_MAX = 60
REPLY_MAX = 40
# 动态索引收「通用口头禅(高频)」或「与对方的话有内容重叠」的配对：
#   - 过滤掉「挺好的→下个月」这种答非所问的一次性句；
#   - 保留「风主已经很强了→风主什么垃圾」这类内容相关回怼。
MIN_GENERIC_FREQ = 3
_CJK = re.compile(r'[\u4e00-\u9fff]+')


def shares_bigram(a: str, b: str) -> bool:
    """两个短句是否共享任意一个中文 2-gram（粗判"回复是否真的在回应对方"）。"""
    def bigrams(s):
        out = set()
        for run in _CJK.findall(s):
            for i in range(len(run) - 1):
                out.add(run[i:i + 2])
        return out
    return bool(bigrams(a) & bigrams(b))


def main():
    pairs = load_pairs()
    print(f'加载对话对: {len(pairs)}')
    style_pairs = [p for p in pairs
                   if len(p['prev']) <= PREV_MAX and len(p['reply']) <= REPLY_MAX]
    print(f'过滤后(prev≤{PREV_MAX} 且 reply≤{REPLY_MAX}): {len(style_pairs)}')

    reply_freq = Counter(p['reply'] for p in style_pairs)

    def keep_dyn(p):
        return reply_freq[p['reply']] >= MIN_GENERIC_FREQ or shares_bigram(p['prev'], p['reply'])

    dyn_pairs = [p for p in style_pairs if keep_dyn(p)]
    print(f'动态索引用配对(通用口头禅或内容相关): {len(dyn_pairs)}')

    # 1) 动态检索索引（对 prev 建索引，meta 存 reply）
    STYLE_DIR.mkdir(exist_ok=True)
    idx = TfidfIndex()
    for p in dyn_pairs:
        idx.add(p['prev'], {'reply': p['reply'], 'chat': p['chat']})
    idx.finalize()
    idx.save(INDEX_FILE)
    print(f'已建 TF-IDF 索引并保存: {INDEX_FILE} ({len(idx)} 条)')

    # 2) 静态 few-shot（用全部 style_pairs，分类 + 按频取 top）
    fewshot, counts = build_static_fewshot(style_pairs)
    with open(FEWSHOT_JSON, 'w', encoding='utf-8') as f:
        json.dump(fewshot, f, ensure_ascii=False, indent=2)
    with open(FEWSHOT_TXT, 'w', encoding='utf-8') as f:
        names = {'ack': '应答', 'agree': '认同', 'chal': '怼人', 'ask': '追问', 'deny': '否定', 'long': '长句', 'other': '其他'}
        for cat in fewshot:
            f.write(f'【{names[cat]}】\n')
            for e in fewshot[cat]:
                f.write(f"对方：{e['prev']}\n你：{e['reply']}\n\n")
    print(f'静态 few-shot 各分类规模: {counts}')
    print(f'已保存: {FEWSHOT_JSON}, {FEWSHOT_TXT}')

    # 3) 演示：动态检索 few-shot
    print('\n' + '=' * 60)
    print('动态检索演示（对方消息 -> 检索到的历史相似"对方话->目标人物回"）')
    print('=' * 60)
    demos = ['难受', '你喜欢吗', '自拍呢', '风主已经很强了', '控分才是大佬',
             '这把稳了', '这个怎么做', '他说明天会来']
    for q in demos:
        hits = idx.search(q, top_n=3)
        print(f'\n>>> {q}')
        for prev, meta, score in hits:
            print(f'    [{score}] {prev}  →  {meta["reply"]}')


if __name__ == '__main__':
    main()
