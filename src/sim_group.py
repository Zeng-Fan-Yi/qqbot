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

try:
    from src.scenarios_mined import MINED_SCENARIOS
except Exception:
    MINED_SCENARIOS = []

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
    {
        'name': '8. 多人刷屏聊原神（该克制，偶尔插一句）',
        'messages': [
            ('曾凡义', '原神5.0新角色你们抽了吗', False),
            ('徐飞扬', '抽了，歪了', False),
            ('猫粮孝子', '我也歪了', False),
            ('曾凡义', '我大保底出的', False),
            ('徐飞扬', '牛', False),
            ('曾凡义', '新地图探索了吗', False),
            ('猫粮孝子', '还没，这周末肝', False),
            ('曾凡义', '一起啊', False),
        ],
    },
    {
        'name': '9. 相关话题聊很久（bot 别每条都接）',
        'messages': [
            ('曾凡义', '三国杀军八谁最强', False),
            ('徐飞扬', '神曹操', False),
            ('猫粮孝子', '神司马懿也猛', False),
            ('曾凡义', '那界黄盖呢', False),
            ('徐飞扬', '界黄盖苦肉强', False),
            ('曾凡义', '还有神吕布', False),
            ('猫粮孝子', '神吕布单挑不行', False),
            ('曾凡义', '你们谁玩', False),
            ('徐飞扬', '我偶尔玩', False),
            ('猫粮孝子', '我也玩', False),
        ],
    },
    {
        'name': '10. 别人吹牛后继续吹（bot 该怼一两次，别每条都怼）',
        'messages': [
            ('徐飞扬', '我昨天通宵肝完了', False),
            ('曾凡义', '牛啊', False),
            ('徐飞扬', '还顺手做了个视频', False),
            ('曾凡义', '真的假的', False),
            ('徐飞扬', '真的，三连了都', False),
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
            # 频率控制：最近 6 条里自己发过言就跳过（与插件逻辑一致）；
            # 但上一条紧挨着是自己说的（对方在接话）→ 不拦。
            _c = list(ctx)
            _prev_is_me = len(_c) >= 2 and _c[-2][0] == BOT_NAME
            if not _prev_is_me and any(s == BOT_NAME for s, _t in _c[-6:]):
                print('    [频率控制: 最近发过言，跳过]')
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
    if '--mined' in sys.argv:
        scenarios = MINED_SCENARIOS
    else:
        scenarios = SCENARIOS
    only = None
    if '--only' in sys.argv:
        only = int(sys.argv[sys.argv.index('--only') + 1]) - 1
    if only is not None:
        run_one(only, scenarios[only])
    else:
        for i, sc in enumerate(scenarios):
            run_one(i, sc)


if __name__ == '__main__':
    main()
