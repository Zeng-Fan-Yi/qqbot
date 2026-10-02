# -*- coding: utf-8 -*-
"""
sim_group.py —— 离线群聊模拟：跑一段多人群聊，看 bot 的插话/接话/潜水/定调效果。

用法：
    python -m src.sim_group            # 跑全部场景
    python -m src.sim_group --only 1   # 只跑第 1 个场景

每个场景是一条条 (发送人, 内容, 是否@bot) 的消息序列；
脚本逐条喂给 bot，打印：谁说了什么 → 判断结果（潜水/回+定调）→ bot 的回复。
用来看 bot 在「多人混乱聊天」里该不该插嘴、接不接得住话。
"""

import sys
from collections import deque

from src.memory import MemoryStore
from src.persona import Persona

persona = Persona('deepseek')
memory = MemoryStore()
BOT_NAME = persona._NAME if hasattr(persona, '_NAME') else '周乾坤'


SCENARIOS = [
    {
        'name': '1. 别人一对一互聊（bot 该潜水）',
        'messages': [
            ('曾凡义', '你回濉溪了吗', False),
            ('猫粮孝子', '没有', False),
            ('曾凡义', '果然不能指望你', False),
            ('猫粮孝子', '哈哈，别这么说', False),
            ('曾凡义', '你这个人就是懒', False),
        ],
    },
    {
        'name': '2. 直接 @ bot 问问题（该认真答）',
        'messages': [
            ('曾凡义', '三国杀现在有多少个武将了', False),
            ('猫粮孝子', '算上前缀估计有500', False),
            ('曾凡义', '才这么点吗', False),
            ('曾凡义', '@周乾坤 你玩三国杀吗', True),
        ],
    },
    {
        'name': '3. @ 一次后连着追问（该持续接话）',
        'messages': [
            ('曾凡义', '@周乾坤 干嘛呢', True),
            ('曾凡义', '玩的什么', False),
            ('曾凡义', '好玩吗？', False),
            ('曾凡义', '带我一个', False),
        ],
    },
    {
        'name': '4. 吹牛/装（该怼）',
        'messages': [
            ('徐飞扬', '我考试全对', False),
            ('曾凡义', '你就吹吧', False),
            ('徐飞扬', '真的，一个没抄', False),
        ],
    },
    {
        'name': '5. 纯寒暄/感叹（该潜水）',
        'messages': [
            ('曾凡义', '今天天气不错', False),
            ('徐飞扬', '是啊，适合出去玩', False),
            ('曾凡义', '哈哈', False),
        ],
    },
    {
        'name': '6. 多人混乱聊三国杀（该在相关时插嘴）',
        'messages': [
            ('曾凡义', '三国杀里哪个武将强', False),
            ('徐飞扬', '当然是神曹操', False),
            ('猫粮孝子', '神曹操也就那样', False),
            ('曾凡义', '那神吕布呢', False),
            ('徐飞扬', '神吕布单挑猛', False),
            ('曾凡义', '有没有人玩啊，开黑', False),
        ],
    },
    {
        'name': '7. 问偏好（该按记忆答）',
        'messages': [
            ('曾凡义', '@周乾坤 你喜欢甘雨还是胡桃', True),
            ('曾凡义', '说啊', False),
        ],
    },
]


def run_one(idx, scenario):
    ctx = deque(maxlen=50)
    print('=' * 70)
    print(scenario['name'])
    print('=' * 70)
    n_reply = 0
    for sender, text, at_bot in scenario['messages']:
        print(f'{sender}: {text}')
        ctx.append((sender, text))
        history = list(ctx)
        if at_bot:
            tone = '认真答'
            print('    [判断: @必回]')
        else:
            should, tone = persona._judge(history)
            if not should:
                print('    [判断: 潜水]')
                continue
            print(f'    [判断: 回 / {tone}]')
        _p, reply = persona._generate(history, memory, tone, must_reply=at_bot)
        reply = (reply or '').strip()
        if reply and reply != '[SILENT]':
            for seg in reply.split('\n'):
                seg = seg.strip()
                if seg:
                    print(f'    [bot] {seg}')
                    ctx.append((BOT_NAME, seg))
                    n_reply += 1
    print(f'--- 本场景 bot 共发言 {n_reply} 次 ---\n')


def main():
    only = None
    if '--only' in sys.argv:
        only = int(sys.argv[sys.argv.index('--only') + 1]) - 1
    if only is not None:
        run_one(only, SCENARIOS[only])
    else:
        for i, sc in enumerate(SCENARIOS):
            run_one(i, sc)


if __name__ == '__main__':
    main()
