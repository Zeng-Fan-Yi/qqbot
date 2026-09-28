# -*- coding: utf-8 -*-
"""
llm.py —— 统一 LLM 客户端（DeepSeek / Qwen，OpenAI 兼容，纯标准库零依赖）。

- 从项目根目录 .env 读取密钥与模型配置；
- DeepSeek / Qwen 都是 OpenAI 兼容 /chat/completions，可一键切换；
- 支持超时 + 重试 + 失败自动降级到另一个 provider（互为灾备）。

用法：
  from src.llm import LLMClient, chat_with_fallback
  c = LLMClient('deepseek')
  print(c.chat([{'role':'user','content':'你好'}]))
"""

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

PROVIDERS = {
    'deepseek': {
        'base_url': 'https://api.deepseek.com/v1',
        'model': 'deepseek-chat',
    },
    'qwen': {
        'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'model': 'qwen-plus',
    },
}


def load_env() -> dict:
    env = {}
    fp = BASE / '.env'
    if fp.exists():
        for line in fp.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()
    # 环境变量覆盖 .env 文件（便于 Docker/容器部署）
    for k in list(os.environ):
        if k.startswith(('DEEPSEEK', 'QWEN')):
            env[k] = os.environ[k]
    return env


def get_config(provider: str) -> dict:
    env = load_env()
    conf = dict(PROVIDERS[provider])
    key = env.get(f'{provider.upper()}_API_KEY', '')
    if env.get(f'{provider.upper()}_BASE_URL'):
        conf['base_url'] = env[f'{provider.upper()}_BASE_URL']
    if env.get(f'{provider.upper()}_MODEL'):
        conf['model'] = env[f'{provider.upper()}_MODEL']
    conf['api_key'] = key
    return conf


class LLMClient:
    def __init__(self, provider='deepseek', temperature=0.85, max_tokens=200, timeout=90):
        self.provider = provider
        self.cfg = get_config(provider)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    def _call(self, messages, tools=None, temperature=None, max_tokens=None, retries=3):
        url = self.cfg['base_url'].rstrip('/') + '/chat/completions'
        payload = {
            'model': self.cfg['model'],
            'messages': messages,
            'temperature': self.temperature if temperature is None else temperature,
            'max_tokens': self.max_tokens if max_tokens is None else max_tokens,
            'stream': False,
        }
        if tools:
            payload['tools'] = tools
            payload['tool_choice'] = 'auto'
        data = json.dumps(payload).encode('utf-8')
        last_err = None
        for attempt in range(retries):
            req = urllib.request.Request(
                url, data=data,
                headers={'Content-Type': 'application/json',
                         'Authorization': f"Bearer {self.cfg['api_key']}"},
                method='POST')
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = json.loads(resp.read().decode('utf-8'))
                return body['choices'][0]['message']
            except urllib.error.HTTPError as e:
                detail = e.read().decode('utf-8', 'replace')
                last_err = f'{self.provider} HTTP {e.code}: {detail}'
                if e.code in (401, 403, 404, 422):  # 不可重试的错误
                    break
            except Exception as e:  # 网络/超时，重试
                last_err = f'{self.provider} {type(e).__name__}: {e}'
            time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(last_err or f'{self.provider} 调用失败')

    def chat(self, messages, temperature=None, max_tokens=None, retries=3):
        msg = self._call(messages, None, temperature, max_tokens, retries)
        return (msg.get('content') or '').strip()

    def chat_tools(self, messages, tools, temperature=None, max_tokens=None, retries=3):
        msg = self._call(messages, tools, temperature, max_tokens, retries)
        return (msg.get('content') or '').strip(), msg.get('tool_calls') or []


def chat_with_fallback(messages, order=('deepseek', 'qwen'), tools=None, **kwargs):
    """按顺序尝试，失败自动切下一个 provider。

    tools 为空 → 返回 (provider, content)；
    tools 非空 → 返回 (provider, content, tool_calls)。
    """
    last_err = None
    for p in order:
        try:
            c = LLMClient(p, **kwargs)
            if tools is not None:
                content, tcs = c.chat_tools(messages, tools)
                return p, content, tcs
            return p, c.chat(messages)
        except Exception as e:
            last_err = e
    raise RuntimeError(f'所有 provider 均失败：{last_err}')
