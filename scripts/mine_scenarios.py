# -*- coding: utf-8 -*-
"""从 chat.txt 挖多人群聊片段，生成复杂测试场景 → src/scenarios_mined.py。"""
import re
import random
from collections import Counter
from datetime import datetime

TIMESTAMP_RE = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{1,2}:\d{2}:\d{2})\s+(\S+)$')

# 周坤（本尊 1721295347）的发送人关键词
ZHOU_KEY = ('周乾坤', '1721295347', '绩点', '猫粮')
# 朋友名映射（曾凡义=导出账号 笑而不语i）
FRIEND_MAP = {'笑而不语i': '曾凡义', '曾凡义': '曾凡义', '徐飞扬': '徐飞扬'}
# 目标群（部分匹配）
GROUP_KEY = ('1701班', '交流', '团支部', '老乡群')


def parse_sections():
    sections = []
    cur_obj = None
    cur_msgs = []
    with open('data/chat.txt', encoding='utf-8', errors='replace') as f:
        it = iter(f)
        for line in it:
            line = line.rstrip('\n')
            if line.startswith('消息对象:'):
                if cur_obj and cur_msgs:
                    sections.append((cur_obj, cur_msgs))
                cur_obj = line.split(':', 1)[1].strip()
                cur_msgs = []
            elif TIMESTAMP_RE.match(line):
                m = TIMESTAMP_RE.match(line)
                ts, sender = m.group(1), m.group(2)
                try:
                    text = next(it).rstrip('\n').strip()
                except StopIteration:
                    break
                if text and '[图片]' not in text and '[表情]' not in text and '[动画表情]' not in text:
                    cur_msgs.append((ts, sender, text))
        if cur_obj and cur_msgs:
            sections.append((cur_obj, cur_msgs))
    return sections


def normalize_sender(sender):
    if any(k in sender for k in ZHOU_KEY):
        return '猫粮孝子'
    for k, v in FRIEND_MAP.items():
        if k in sender:
            return v
    return sender.split('(')[0]


def is_at(text):
    # 挖掘数据里没有「@ bot」（数据是 bot 上线前的），@周乾坤 是 @ 真人 → 都算 False
    return False


def main():
    random.seed(42)
    sections = parse_sections()

    # 目标群：名字匹配 + 含周坤
    candidates = []
    for obj, msgs in sections:
        if not any(k in obj for k in GROUP_KEY):
            continue
        if not any(any(k in s for k in ZHOU_KEY) for _t, s, _x in msgs):
            continue
        candidates.append((obj, msgs))
    print(f'候选群 {len(candidates)} 个:', [o for o, _ in candidates])

    segments = []
    for obj, msgs in candidates:
        parsed = []
        for ts, sender, text in msgs:
            try:
                parsed.append((datetime.strptime(ts, '%Y-%m-%d %H:%M:%S'), sender, text))
            except Exception:
                continue
        parsed.sort(key=lambda x: x[0])
        seg = []
        for dt, sender, text in parsed:
            if seg and (dt - seg[-1][0]).total_seconds() > 180:
                if 5 <= len(seg) <= 14:
                    segments.append((obj, seg))
                seg = []
            seg.append((dt, sender, text))
        if 5 <= len(seg) <= 14:
            segments.append((obj, seg))

    print(f'片段 {len(segments)} 个')

    # 多发送人 + 含周坤
    good = []
    for obj, seg in segments:
        senders = set(normalize_sender(s) for _t, s, _x in seg)
        has_zhou = any(any(k in s for k in ZHOU_KEY) for _t, s, _x in seg)
        if len(senders) < 3 or not has_zhou:
            continue
        good.append((obj, seg))

    random.shuffle(good)
    picked = good[:30]
    print(f'选出 {len(picked)} 个场景')

    lines = ['# -*- coding: utf-8 -*-',
             '# 从 chat.txt 自动挖出的复杂群聊场景（真实数据，发送人已映射）',
             'MINED_SCENARIOS = [']
    for i, (obj, seg) in enumerate(picked):
        lines.append('    {')
        lines.append(f"        'name': 'M{i + 1}. {obj}',")
        lines.append('        \'messages\': [')
        for _t, sender, text in seg:
            s = normalize_sender(sender)
            at = is_at(text)
            # 文本里的「周乾坤」也是指真人 → 统一换成「猫粮孝子」，避免 bot 误以为在叫自己
            text = text.replace('周乾坤', '猫粮孝子').replace('乾坤', '猫粮孝子')
            text = text.replace('\\', '\\\\').replace("'", "\\'")
            lines.append(f"            ('{s}', '{text}', {at}),")
        lines.append('        ],')
        lines.append('    },')
    lines.append(']')

    with open('src/scenarios_mined.py', 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

    print('\n=== 场景摘要 ===')
    for i, (obj, seg) in enumerate(picked):
        senders = Counter(normalize_sender(s) for _t, s, _x in seg)
        print(f'M{i + 1}. [{obj}] {len(seg)}条 | {dict(senders)}')


if __name__ == '__main__':
    main()
