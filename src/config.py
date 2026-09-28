# -*- coding: utf-8 -*-
"""
config.py —— 加载人格配置（姓名、昵称、点名词、群白名单等）。

- 优先读 config/persona.json（隐私，不入库）；
- 没有的话回退到 config/persona.example.json（模板，入库）。
"""

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE / 'config'
PERSONA_JSON = CONFIG_DIR / 'persona.json'
PERSONA_EXAMPLE = CONFIG_DIR / 'persona.example.json'


def load_persona():
    """返回人格配置 dict。"""
    path = PERSONA_JSON if PERSONA_JSON.exists() else PERSONA_EXAMPLE
    with open(path, encoding='utf-8') as f:
        return json.load(f)
