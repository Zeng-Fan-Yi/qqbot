# -*- coding: utf-8 -*-
"""
eval_style.py —— 离线风格评测。

用 DeepSeek / Qwen 分别跑一组测试消息，检查：
  1) 像不像目标人物（短句、口头禅、语气）；
  2) 回复多样性（会不会塌缩成固定几句复读）。

用法：
  python -m src.eval_style                  # 两个模型都跑
  python -m src.eval_style --model deepseek # 只跑一个
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

from src.llm import LLMClient
from src.persona import SYSTEM_PROMPT
from src.retrieval import TfidfIndex

BASE = Path(__file__).resolve().parent.parent
STYLE_DIR = BASE / 'data' / 'style'
FEWSHOT_JSON = STYLE_DIR / 'few_shot.json'
INDEX_FILE = STYLE_DIR / 'pairs_index.json'

TEST_MSGS = [
    '我今天加班了',
    '搞定了',
    '他今天没来',
    '这把稳了',
    '我超厉害的',
    '他说明天会来',
    '我觉得挺好的',
    '这个怎么做',
    '你玩过吗',
    '去不去',
    '我昨天遇到个事',
    '出问题了',
    '你说呢',
    '就这样吧',
    '风主已经很强了',
    '我喜欢你',
    '明天考试',
    '你人呢',
    '吃饭了吗',
    '给我讲个道理',
]

EMOJI_RE = re.compile(r'[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF]')


def fmt_pair(prev, reply):
    return f'对方：{prev}\n你：{reply}'


def build_static_block(fewshot, per_cat=3):
    names = {'ack': '认同', 'chal': '怼人', 'ask': '追问', 'deny': '否定', 'long': '说整句', 'other': '其他'}
    block = ''
    for cat in ('ack', 'chal', 'ask', 'deny', 'long', 'other'):
        ex = fewshot.get(cat, [])[:per_cat]
        if not ex:
            continue
        block += f'\n【{names[cat]}】\n'
        for e in ex:
            block += fmt_pair(e['prev'], e['reply']) + '\n'
    return block


def guard(text):
    """软护栏：只清违禁符号；保留换行（连发分隔），去掉空行。"""
    t = (text or '').strip()
    t = EMOJI_RE.sub('', t)
    for ch in ('…', '……', '~', '～'):
        t = t.replace(ch, '')
    lines = [ln.strip() for ln in t.split('\n')]
    return '\n'.join(ln for ln in lines if ln)


def build_messages(query, static_block, index):
    sys = SYSTEM_PROMPT + static_block
    if index is not None:
        hits = index.search(query, top_n=3)
        hits = [h for h in hits if h[2] >= 0.5]
        if hits:
            sys += '\n【你历史上面对类似的话是这么回的——学它的语气和长度，'
            sys += '但结合当前这句自己决定回什么，别照抄示例】\n'
            for prev, meta, _score in hits:
                sys += fmt_pair(prev, meta['reply']) + '\n'
    sys += '\n直接回一句，别解释、别加引号。'
    return [{'role': 'system', 'content': sys}, {'role': 'user', 'content': query}]


def run_model(provider, queries, static_block, index):
    client = LLMClient(provider, temperature=1.1, max_tokens=80)
    results = []
    for q in queries:
        msgs = build_messages(q, static_block, index)
        try:
            raw = client.chat(msgs)
        except Exception as e:
            raw = f'<调用失败: {e}>'
        results.append((q, guard(raw), raw))
    return results


def main():
    model_arg = 'both'
    if '--model' in sys.argv:
        i = sys.argv.index('--model')
        model_arg = sys.argv[i + 1] if i + 1 < len(sys.argv) else 'both'

    fewshot = json.loads(FEWSHOT_JSON.read_text(encoding='utf-8'))
    static_block = build_static_block(fewshot)
    index = TfidfIndex.load(INDEX_FILE) if INDEX_FILE.exists() else None
    print(f'静态 few-shot + 动态检索索引已加载（索引 {len(index) if index else 0} 条）\n')

    providers = ['deepseek', 'qwen'] if model_arg == 'both' else [model_arg]

    for p in providers:
        print('=' * 70)
        print(f'模型: {p}')
        print('=' * 70)
        results = run_model(p, TEST_MSGS, static_block, index)
        replies = []
        violations = []
        for q, guarded, raw in results:
            replies.append(guarded)
            bad = []
            if EMOJI_RE.search(guarded):
                bad.append('emoji')
            if any(c in guarded for c in ('…', '~', '～')):
                bad.append('符号')
            if len(guarded) > 40:
                bad.append(f'过长({len(guarded)}字)')
            if bad:
                violations.append((q, guarded, ','.join(bad)))
            print(f'  {q:<12} -> {guarded}')
        print('\n  --- 统计 ---')
        lens = [len(r) for r in replies]
        print(f'  平均长度: {sum(lens)/len(lens):.1f} 字 | 最长: {max(lens)}')
        uniq = set(replies)
        print(f'  去重后回复种类: {len(uniq)}/{len(replies)}')
        print(f'  高频回复 top5: {Counter(replies).most_common(5)}')
        if violations:
            print(f'  违禁/异常 {len(violations)} 条:')
            for q, g, b in violations:
                print(f'    [{q}] {g}  ({b})')
        print()


if __name__ == '__main__':
    main()
