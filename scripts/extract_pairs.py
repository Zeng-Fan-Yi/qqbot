# -*- coding: utf-8 -*-
"""
extract_pairs.py —— 从原始聊天记录提取「对方消息 → 目标人物回复」对话对。

- 解析 data/chat.txt，把每条"对方上一句"和"目标人物的回复"配对；
- 目标人物的发送人名字在 config/persona.json 的 chat_senders 里配置；
- 输出 data/pairs.jsonl，供 build_style.py 建风格索引。

用法：
    python -m scripts.extract_pairs
"""

import re
import json
from datetime import datetime
from pathlib import Path
from collections import Counter

BASE = Path(__file__).resolve().parent.parent  # 项目根目录
DATA = BASE / 'data'
INPUT_FILE = DATA / 'chat.txt'
OUTPUT_FILE = DATA / 'pairs.jsonl'


def _load_target_senders():
    """从 config/persona.json（隐私）读取目标人物的聊天发送人名字；没有则回退 example。"""
    cfg = BASE / 'config' / 'persona.json'
    if not cfg.exists():
        cfg = BASE / 'config' / 'persona.example.json'
    with open(cfg, encoding='utf-8') as f:
        return json.load(f).get('chat_senders', [])


TARGET_SENDERS = _load_target_senders()
MAX_GAP_SECONDS = 3 * 60  # 对方消息与回复之间的最大间隔（秒），超过视为新话题（收紧到3分钟，减少"答非所问"的假配对）

# ---------- 解析正则 ----------
TIMESTAMP_SENDER_RE = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{1,2}:\d{2}:\d{2})\s+(\S+)$')
BARE_TIMESTAMP_RE = re.compile(r'^\d{4}-\d{2}-\d{2} \d{1,2}:\d{2}:\d{2}$')
SECTION_OBJ_RE = re.compile(r'^消息对象:(.*)$')
TS_RE = re.compile(r'^(\d{4})-(\d{2})-(\d{2}) (\d{1,2}):(\d{2}):(\d{2})$')

# ---------- 过滤规则（复用 3.py）----------
SYSTEM_KEYWORDS = ('请使用最新版手机QQ',)
SYSTEM_PREFIXES = ('[戳一戳]',)
DROP_TAGS = {
    '[表情]', '[图片]', '[文件]', '[语音]', '[视频]',
    '[吃糖]', '[我想开了]', '[菜汪]', '[变形]', '[流泪]', '[QQ红包]',
}
PUNCT_CHARS = set('，。！、；：""''（）()【】《》,.!;:()[]{}')
MENTION_ONLY = re.compile(r'^@\S+\s*$')
SYSTEM_SENDER_RE = re.compile(r'^系统')          # 系统消息(10000) 等系统发送人
LEAD_TAG_RE = re.compile(r'^(?:\[[^\]]{1,10}\]\s*)+')  # 行首的表情/图片标签，如 [表情]xxx


def ts_to_dt(s: str):
    m = TS_RE.match(s)
    if not m:
        return None
    y, mo, d, h, mi, se = (int(g) for g in m.groups())
    return datetime(y, mo, d, h, mi, se)


def is_pure_punct(s: str) -> bool:
    return bool(s) and all(c in PUNCT_CHARS for c in s)


def drop_reply(s: str) -> str:
    """返回非空字符串表示丢弃原因（目标人物回复的清洗）。"""
    if not s:
        return 'empty'
    if any(k in s for k in SYSTEM_KEYWORDS):
        return 'system'
    if s.startswith(SYSTEM_PREFIXES):
        return 'system'
    if s in DROP_TAGS:
        return 'tag'
    if is_pure_punct(s):
        return 'punct'
    if MENTION_ONLY.match(s):
        return 'mention'
    return ''


def clean_prev(s: str) -> str:
    """对方消息的轻量清洗：只要非空文本，并去掉行首的表情标签。"""
    s = s.strip()
    if s in DROP_TAGS:
        return ''
    s = LEAD_TAG_RE.sub('', s).strip()
    return s


def main():
    target_set = set(TARGET_SENDERS)

    chat = None
    in_msg = False
    sender = None
    ts_cur = None
    content_lines = []
    last_other = None  # 同一段内最近一条"非目标发送人"的消息 {text, ts, sender}

    pairs = []
    stats = Counter()

    def flush():
        nonlocal in_msg, sender, ts_cur, content_lines, last_other
        if not in_msg:
            return
        text = ' '.join('\n'.join(content_lines).split())
        stats['total_msgs'] += 1

        if sender in target_set:
            # 目标人物的消息 → 尝试配对
            reason = drop_reply(text)
            if reason:
                stats[f'reply_dropped_{reason}'] += 1
            else:
                if last_other and last_other['text'] and ts_cur:
                    gap = (ts_cur - last_other['ts']).total_seconds()
                    if 0 <= gap <= MAX_GAP_SECONDS:
                        pairs.append({
                            'chat': chat,
                            'prev_sender': last_other['sender'],
                            'prev': last_other['text'],
                            'prev_ts': last_other['ts'].isoformat(timespec='seconds'),
                            'reply': text,
                            'reply_ts': ts_cur.isoformat(timespec='seconds'),
                            'gap_sec': round(gap),
                        })
                        stats['pairs'] += 1
                    else:
                        stats['gap_too_large'] += 1
                else:
                    stats['no_prev'] += 1
        elif sender is not None and not SYSTEM_SENDER_RE.match(sender):
            # 非目标、非系统的真人消息 → 更新"对方"上下文
            t = clean_prev(text)
            if t:
                last_other = {'text': t, 'ts': ts_cur, 'sender': sender}
                stats['other_msgs'] += 1
            else:
                # 对方上一条是媒体/空 → 不当作有效上下文
                last_other = None
        # sender is None 或 系统消息 → 忽略，不影响 last_other

        sender = None
        ts_cur = None
        content_lines = []
        in_msg = False

    with open(INPUT_FILE, encoding='utf-8') as f:
        for raw in f:
            line = raw.rstrip('\r\n')
            stripped = line.strip()

            m_obj = SECTION_OBJ_RE.match(stripped)
            if m_obj:
                flush()
                chat = m_obj.group(1).strip()
                last_other = None
                continue

            m = TIMESTAMP_SENDER_RE.match(stripped)
            if m:
                flush()
                ts_cur = ts_to_dt(m.group(1))
                sender = m.group(2)
                in_msg = True
                continue

            if BARE_TIMESTAMP_RE.match(stripped):
                flush()
                ts_cur = ts_to_dt(stripped)
                sender = None
                in_msg = True
                continue

            if in_msg:
                content_lines.append(line)
        flush()

    # 去重：chat.txt 疑似包含重复的会话块（同一批会话导出两遍，见「消息对象:xxx」出现两次），
    # 按 (prev, reply) 去重，避免频率统计被翻倍。
    seen = set()
    deduped = []
    for p in pairs:
        key = (p['prev'], p['reply'])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(p)
    print(f'去重: {len(pairs)} -> {len(deduped)}')
    pairs = deduped

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + '\n')

    # ---------- 报告 ----------
    print('=' * 60)
    print('对话对提取完成')
    print('=' * 60)
    print(f'解析消息总数:      {stats["total_msgs"]}')
    print(f'其中对方消息:      {stats["other_msgs"]}')
    print(f'产出对话对:        {stats["pairs"]}')
    print(f'丢弃(目标人物回复):    ' + ' | '.join(
        f'{k}={v}' for k, v in sorted(stats.items())
        if k.startswith('reply_dropped_')))
    print(f'无上一条/间隔过大: no_prev={stats["no_prev"]}, '
          f'gap_too_large={stats["gap_too_large"]}')

    # 间隔分布
    if pairs:
        gaps = [p['gap_sec'] for p in pairs]
        print(f'\n间隔分布(秒): min={min(gaps)}, 中位={sorted(gaps)[len(gaps)//2]}, '
              f'max={max(gaps)}, 均值={round(sum(gaps)/len(gaps))}')
        print('间隔直方图:')
        for lo, hi in [(0, 60), (60, 300), (300, 600), (600, 1800)]:
            c = sum(1 for g in gaps if lo <= g < hi)
            print(f'  {lo:>4}-{hi:>4}s: {c}')

        # 抽样 20 条
        import random
        random.seed(42)
        print('\n抽样 20 条:')
        for p in random.sample(pairs, min(20, len(pairs))):
            prev = p['prev'] if len(p['prev']) <= 40 else p['prev'][:40] + '…'
            reply = p['reply'] if len(p['reply']) <= 40 else p['reply'][:40] + '…'
            print(f"  [{p['chat']}] ({p['gap_sec']}s) {p['prev_sender']}: {prev}  →  目标人物: {reply}")

    print(f'\n已保存至 {OUTPUT_FILE}')


if __name__ == '__main__':
    main()
