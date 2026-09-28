# -*- coding: utf-8 -*-
"""guard.py —— 输出软护栏。只拦"明显出戏"，不强制字数。"""

import re

EMOJI_RE = re.compile(r'[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF]')


def guard(text: str) -> str:
    """去掉 emoji/省略号/波浪号；保留换行（作为连发分隔），去掉空行。"""
    t = (text or '').strip()
    t = EMOJI_RE.sub('', t)
    for ch in ('…', '……', '~', '～'):
        t = t.replace(ch, '')
    lines = [ln.strip() for ln in t.split('\n')]
    return '\n'.join(ln for ln in lines if ln)
