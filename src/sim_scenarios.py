# -*- coding: utf-8 -*-
"""手写群聊测试场景（参考真实聊天风格整理），每条消息带预期结果。

消息格式：(发送人, 内容, 是否@bot, 是否该回)
- 是否@bot：这条消息是否 @/点名 bot（决定 must_reply）
- 是否该回：期望 bot 对这条消息回话（True）还是潜水（False）
"""

HAND_SCENARIOS = [
    # ===== @ / 点名 必回 =====
    {
        'name': '1. @bot 问问题',
        'messages': [
            ('曾凡义', '@周乾坤 三国杀有多少武将', True, True),
        ],
    },
    {
        'name': '2. @bot 寒暄',
        'messages': [
            ('曾凡义', '@周乾坤 在吗', True, True),
        ],
    },
    {
        'name': '3. 点名「周乾坤」',
        'messages': [
            ('曾凡义', '周乾坤你去不去打球', False, True),
        ],
    },
    # ===== 相关话题：该插嘴（但别每条都插） =====
    {
        'name': '4. 别人聊三国杀（该插一句）',
        'messages': [
            ('徐飞扬', '三国杀里哪个武将强', False, True),
            ('曾凡义', '神曹操吧', False, False),
            ('徐飞扬', '那神吕布呢', False, False),
        ],
    },
    {
        'name': '5. 别人聊原神（该插一句）',
        'messages': [
            ('曾凡义', '原神新角色抽了吗', False, True),
            ('徐飞扬', '抽了歪了', False, False),
            ('曾凡义', '我大保底', False, False),
        ],
    },
    {
        'name': '6. 别人聊课程作业（该插一句）',
        'messages': [
            ('徐飞扬', '这周作业写到几点啊', False, True),
            ('曾凡义', '我还没写', False, False),
        ],
    },
    {
        'name': '7. 问「你玩不玩」（该回）',
        'messages': [
            ('曾凡义', '你玩不玩三国杀', False, True),
        ],
    },
    {
        'name': '8. 问具体知识（该认真答）',
        'messages': [
            ('曾凡义', '三国杀神曹操强不强', False, True),
        ],
    },
    # ===== 吹牛/骂人：该怼 =====
    {
        'name': '9. 别人吹牛（该怼）',
        'messages': [
            ('徐飞扬', '我考试全对', False, True),
            ('曾凡义', '牛啊', False, False),
        ],
    },
    {
        'name': '10. 别人骂你（该怼）',
        'messages': [
            ('徐飞扬', '周乾坤你就是个废物', False, True),
        ],
    },
    # ===== 连着追问：该持续接话 =====
    {
        'name': '11. @一次后连着追问',
        'messages': [
            ('曾凡义', '@周乾坤 干嘛呢', True, True),
            ('曾凡义', '玩的什么', False, True),
            ('曾凡义', '好玩吗', False, True),
        ],
    },
    # ===== 本尊在场：该潜水 =====
    {
        'name': '12. 本尊猫粮孝子在说话（潜水）',
        'messages': [
            ('曾凡义', '你回濉溪了吗', False, False),
            ('猫粮孝子', '没有', False, False),
            ('曾凡义', '果然不能指望你', False, False),
        ],
    },
    {
        'name': '13. 别人 @ 本尊（潜水）',
        'messages': [
            ('曾凡义', '@猫粮孝子 你回濉溪了吗', False, False),
            ('猫粮孝子', '没有', False, False),
        ],
    },
    # ===== 别人互聊无关话题：该潜水 =====
    {
        'name': '14. 两人聊天气（潜水）',
        'messages': [
            ('曾凡义', '今天天气不错', False, False),
            ('徐飞扬', '是啊适合出去玩', False, False),
        ],
    },
    {
        'name': '15. 两人聊八卦（潜水）',
        'messages': [
            ('曾凡义', '听说班长谈恋爱了', False, False),
            ('徐飞扬', '真的假的', False, False),
        ],
    },
    {
        'name': '16. 别人 @ 别人（潜水）',
        'messages': [
            ('曾凡义', '@徐飞扬 你去不去', False, False),
            ('徐飞扬', '不去', False, False),
        ],
    },
    {
        'name': '17. 两人聊吃的（潜水）',
        'messages': [
            ('曾凡义', '中午吃啥', False, False),
            ('徐飞扬', '食堂吧', False, False),
        ],
    },
    # ===== 寒暄/感叹/表情：该潜水 =====
    {
        'name': '18. 纯感叹（潜水）',
        'messages': [
            ('曾凡义', '好无聊啊', False, False),
            ('徐飞扬', '我也是', False, False),
        ],
    },
    {
        'name': '19. 报喜（该短回）',
        'messages': [
            ('徐飞扬', '我上岸了', False, True),
        ],
    },
    # ===== 更多复杂场景 =====
    {
        'name': '20. 多人聊游戏开黑（插1次）',
        'messages': [
            ('曾凡义', '有没有人开黑', False, True),
            ('徐飞扬', '我', False, False),
            ('猫粮孝子', '加我一个', False, False),
            ('曾凡义', '几排', False, False),
        ],
    },
    {
        'name': '21. 别人聊皮肤（插1次）',
        'messages': [
            ('曾凡义', '新皮肤手感咋样', False, True),
            ('徐飞扬', '还行', False, False),
            ('曾凡义', '多少钱', False, False),
        ],
    },
    {
        'name': '22. 问「你喜欢谁」（该回，带记忆）',
        'messages': [
            ('曾凡义', '@周乾坤 你喜欢甘雨还是胡桃', True, True),
        ],
    },
    {
        'name': '23. 别人聊配队（插1次）',
        'messages': [
            ('曾凡义', '融甘队怎么配', False, True),
            ('徐飞扬', '钟离班尼特香菱', False, False),
        ],
    },
    {
        'name': '24. 吹牛后继续吹（怼1次）',
        'messages': [
            ('徐飞扬', '我通宵肝完了', False, True),
            ('曾凡义', '牛', False, False),
            ('徐飞扬', '还做了个视频', False, False),
        ],
    },
    {
        'name': '25. 别人聊回老家（潜水，本尊话题）',
        'messages': [
            ('曾凡义', '你回濉溪了吗', False, False),
            ('猫粮孝子', '没回', False, False),
        ],
    },
    {
        'name': '26. 别人聊考试（插1次）',
        'messages': [
            ('徐飞扬', '明天考试慌不慌', False, True),
            ('曾凡义', '慌啥', False, False),
        ],
    },
    {
        'name': '27. 多人聊上课（插1次）',
        'messages': [
            ('曾凡义', '这课是不是要挂科了', False, True),
            ('徐飞扬', '不至于吧', False, False),
            ('猫粮孝子', '稳的', False, False),
        ],
    },
    {
        'name': '28. 表情/语气词（潜水）',
        'messages': [
            ('曾凡义', '哈哈', False, False),
            ('徐飞扬', '笑死', False, False),
        ],
    },
    {
        'name': '29. @bot 问在干嘛（短回）',
        'messages': [
            ('曾凡义', '@周乾坤 在干嘛', True, True),
        ],
    },
    {
        'name': '30. 别人聊你没玩过的游戏（潜水）',
        'messages': [
            ('曾凡义', '瓦罗兰特有人玩吗', False, False),
            ('徐飞扬', '我玩', False, False),
        ],
    },
]
