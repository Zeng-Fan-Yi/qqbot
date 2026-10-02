# -*- coding: utf-8 -*-
"""
persona.py —— 人格层：拼装提示词 + 调用 LLM + 软护栏，产出"像目标人物"的回复。

- 系统提示词（软约束） + 静态 few-shot（7 类） + 动态 few-shot（TF-IDF 检索相关对答）
- 统一走 DeepSeek/Qwen（chat_with_fallback 自动降级）

用法：
  from src.persona import Persona
  p = Persona('deepseek')
  provider, reply = p.reply('搞定了')
"""

import json
import re
from pathlib import Path

from src.config import load_persona
from src.guard import guard
from src.llm import chat_with_fallback
from src.retrieval import TfidfIndex

BASE = Path(__file__).resolve().parent.parent
STYLE_DIR = BASE / 'data' / 'style'
FEWSHOT_JSON = STYLE_DIR / 'few_shot.json'
INDEX_FILE = STYLE_DIR / 'pairs_index.json'

_PERSONA = load_persona()
_NAME = _PERSONA['name']
_NICKNAMES = '、'.join(_PERSONA.get('nicknames', []))
_ADDRESS_STR = '、'.join(_PERSONA.get('address_words', []))
# 目标人物专属的提示词片段（隐私、放 persona.json 的 prompt_hints 里），没有则用通用回退
_HINTS = _PERSONA.get('prompt_hints', {})
_RECALL_CLAIM = _HINTS.get('recall_claim_examples', '比如「你以前…」「我们是不是同学」「你玩不玩游戏」')
_RECALL_KEYWORD = _HINTS.get('recall_keyword_examples', '如「游戏」「女朋友」「学校」')
_SILENT_RELATED = _HINTS.get('silent_related', '你在玩的游戏、你的学校课程')
_SILENT_GAME_EXAMPLE = _HINTS.get('silent_game_example', '对方：有人打游戏吗\n你：有，我打')

# 系统提示词放在 config/system_prompt.txt（隐私、不入库），
# 没有该文件时回退到 config/system_prompt.example.txt（通用模板）。
# 这样可以在不改代码的情况下，保留目标人物专属的调校效果。
PROMPT_FILE = BASE / 'config' / 'system_prompt.txt'
PROMPT_EXAMPLE = BASE / 'config' / 'system_prompt.example.txt'


def _load_system_prompt():
    path = PROMPT_FILE if PROMPT_FILE.exists() else PROMPT_EXAMPLE
    template = path.read_text(encoding='utf-8')
    return template.format(name=_NAME, nicknames=_NICKNAMES, address=_ADDRESS_STR)


SYSTEM_PROMPT = _load_system_prompt()


RECALL_MEMORY_TOOL = {
    'type': 'function',
    'function': {
        'name': 'recall_memory',
        'description': (
            f'检索你（{_NAME}）自己的过往记忆。'
            f'当对方问起你的事，或对方声称/提到关于你的事（{_RECALL_CLAIM}）时，先调用本工具查询再回答。'
            '别凭空否认、别瞎编、别乱说。普通闲聊、不涉及你个人的话题不要调用。'),
        'parameters': {
            'type': 'object',
            'properties': {
                'query': {'type': 'string', 'description': f'1-4 个字的简短关键词，{_RECALL_KEYWORD}，不要写整句'}
            },
            'required': ['query'],
        },
    },
}


def _fmt_pair(prev, reply):
    return f'对方：{prev}\n你：{reply}'


class Persona:
    def __init__(self, provider='deepseek', temperature=1.1):
        self.provider = provider
        self.temperature = temperature
        self.static_block = self._build_static_block()
        self.index = TfidfIndex.load(INDEX_FILE) if INDEX_FILE.exists() else None

    def _build_static_block(self, per_cat=3):
        if not FEWSHOT_JSON.exists():
            return ''
        fewshot = json.loads(FEWSHOT_JSON.read_text(encoding='utf-8'))
        names = {'ack': '应答', 'agree': '认同', 'chal': '怼人', 'ask': '追问',
                 'deny': '否定', 'long': '长句', 'other': '其他'}
        block = ''
        for cat in ('ack', 'agree', 'chal', 'ask', 'deny', 'long', 'other'):
            ex = fewshot.get(cat, [])[:per_cat]
            if not ex:
                continue
            block += f'\n【{names[cat]}】\n'
            for e in ex:
                block += _fmt_pair(e['prev'], e['reply']) + '\n'
        # 连发示例（"你："出现多次 = 分多条消息发）
        block += '\n【连发】\n'
        block += '对方：搞定了\n你：不错\n你：稳了\n\n'
        block += '对方：我超厉害的\n你：我呸\n你：就你？\n\n'
        block += '对方：我昨天遇到个事\n你：哦\n你：然后呢\n\n'
        block += '对方：出问题了\n你：咋了\n你：说清楚\n\n'
        block += '对方：你变了\n你：哎\n你：怎么就变了\n'
        return block

    def build_messages(self, query):
        sys = SYSTEM_PROMPT + self.static_block
        if self.index is not None:
            hits = [h for h in self.index.search(query, top_n=3) if h[2] >= 0.5]
            if hits:
                sys += '\n【你历史上面对类似的话是这么回的——学它的语气和长度，'
                sys += '但结合当前这句自己决定回什么，别照抄示例】\n'
                for prev, meta, _s in hits:
                    sys += _fmt_pair(prev, meta['reply']) + '\n'
        sys += '\n直接回，别解释、别加引号。想连发就每条一行。'
        return [{'role': 'system', 'content': sys}, {'role': 'user', 'content': query}]

    def reply(self, query):
        msgs = self.build_messages(query)
        fallback = 'qwen' if self.provider == 'deepseek' else 'deepseek'
        provider, raw = chat_with_fallback(
            msgs, order=(self.provider, fallback),
            temperature=self.temperature, max_tokens=80)
        return provider, guard(raw)

    def reply_with_memory(self, query, memory):
        """带记忆的回复：模型可调用 recall_memory 工具按需检索过往，默认不调。"""
        msgs = self.build_messages(query)
        fallback = 'qwen' if self.provider == 'deepseek' else 'deepseek'
        order = (self.provider, fallback)
        provider, content, tcs = chat_with_fallback(
            msgs, order=order, tools=[RECALL_MEMORY_TOOL],
            temperature=self.temperature, max_tokens=80)
        if not tcs:
            return provider, guard(content)
        # 模型决定检索记忆
        try:
            args = json.loads(tcs[0]['function'].get('arguments', '{}'))
            mq = args.get('query', query)
        except Exception:
            mq = query
        facts = memory.recall(mq, top_n=2)
        sys = msgs[0]['content']
        if facts:
            sys += '\n\n你关于自己的真实情况（可能含不同时期，挑最自然的一条据实回答）：' + '；'.join(f for f, _s in facts)
        msgs2 = [{'role': 'system', 'content': sys}, msgs[1]]
        provider2, raw = chat_with_fallback(
            msgs2, order=order, temperature=self.temperature, max_tokens=80)
        return provider2, guard(raw)

    def reply_group(self, history, memory, must_reply=False):
        """群聊回复：history=[(sender, text)]，末条是当前触发消息。返回 (provider, reply)。

        - 注入最近 50 条群聊上下文；
        - must_reply=True（被@）必回；否则允许回 [SILENT] 潜水；
        - 仍按需走 recall_memory 工具召回记忆。
        """
        if not history:
            return self.provider, ''
        _sender, last_text = history[-1]
        sys = SYSTEM_PROMPT + self.static_block
        # 先召回记忆（每次都用整句话检索）
        facts = memory.recall(last_text, top_n=3) if memory else []
        # 动态 few-shot：只在没有相关记忆时注入，避免「风格示例」和「记忆事实」打架
        if self.index is not None and not facts:
            hits = [h for h in self.index.search(last_text, top_n=3) if h[2] >= 0.5]
            if hits:
                sys += '\n【你历史上面对类似的话是这么回的——学他的语气和长短（他回长你就说长、回短你就说短），但内容针对当前对话用自己的话答、换个说法，别逐字抄】\n'
                for prev, meta, _s in hits:
                    sys += _fmt_pair(prev, meta['reply']) + '\n'
        ctx = '\n'.join(f'{s}: {t}' for s, t in history[-50:])
        sys += f'\n\n【最近的群聊记录（知道在聊什么）】\n{ctx}'
        if must_reply:
            sys += '\n\n对方 @ 了你或点名了你，必须回。如果是在问你问题，认真回答（知道就答，不知道就说不知道），别回「哦」敷衍。'
        else:
            sys += '\n\n【要不要回？重要：你在群里大部分时候不说话，宁可潜水也别插嘴】\n'
            sys += '绝大多数群消息都回 [SILENT]（就这三个字母，别输出别的字，更别输出「无视」）。只有两种情况才开口：\n'
            sys += f'1. 有人叫你/点名你（{_ADDRESS_STR}、@你），或明显在直接跟你说话 → 回。\n'
            sys += f'2. 有人明确聊到跟你本人相关的事（{_SILENT_RELATED}）→ 可以插一句。\n'
            sys += '以下一律 [SILENT]：\n'
            sys += '- 对方 @ 的是别人（不是你）→ [SILENT]。\n'
            sys += '- 群友聊吃什么、天气、无聊、八卦、别人的事、感叹、表情、接龙 → [SILENT]。\n'
            sys += '- 只是寒暄/一句感叹/一个表情，没具体事、没问你 → [SILENT]。\n'
            sys += '例：\n'
            sys += '对方：今天天气不错\n你：[SILENT]\n\n'
            sys += '对方：中午吃什么\n你：[SILENT]\n\n'
            sys += '对方：好无聊啊\n你：[SILENT]\n\n'
            sys += '对方：@张三 你去不去\n你：[SILENT]\n\n'
            sys += f'{_SILENT_GAME_EXAMPLE}\n\n'
            sys += '对方：你作业写了吗\n你：没写\n'
        if facts:
            sys += '\n\n【你的偏好（问「喜欢/会/爱玩吗」就按这些答）：' + '；'.join(f for f, _s in facts) + '】\n'
            sys += '注意：对方问「玩不玩/玩吗/打不打」时（没提「喜欢/爱玩」），一般是在问「现在」→ 按当下答（你比较被动 → 「不玩」「没玩」），别说「平时不玩」这种否定偏好的话。问「喜欢/爱玩吗」才按上面的偏好答。'
        sys += '\n直接回，别解释、别加引号。想连发就每条一行。'
        msgs = [{'role': 'system', 'content': sys}, {'role': 'user', 'content': last_text}]
        fallback = 'qwen' if self.provider == 'deepseek' else 'deepseek'
        order = (self.provider, fallback)
        provider, content = chat_with_fallback(
            msgs, order=order, temperature=self.temperature, max_tokens=80)
        return provider, guard(content)
