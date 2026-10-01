#!/usr/bin/env python3
"""OpenAI gateway for legacy guided_choice and a fixed non-thinking contract."""
import json
import hashlib
import time
import os
from pathlib import Path
import re
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

app = FastAPI()
BACKEND = os.environ.get('M2_BACKEND_URL', 'http://127.0.0.1:18036')
BACKEND_KIND = os.environ.get('M2_BACKEND_KIND', 'sglang')
MODEL = '/public/home/sunyihan/rd_instruction_20260923/v5_models/Qwen3.6-27B-FP8'
TOKENIZER_CONFIG = json.loads((Path(MODEL) / 'tokenizer_config.json').read_text())
THINKING_IDS = [key for key, value in TOKENIZER_CONFIG['added_tokens_decoder'].items()
               if value['content'] in ('<think>', '</think>')]


@app.get('/health')
async def health():
    async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
        response = await client.get(BACKEND + '/health')
    return JSONResponse({'ready': response.status_code == 200, 'backend': BACKEND_KIND,
        'repo': 'Qwen/Qwen3.6-27B-FP8', 'thinking': False,
        'revision': json.loads((Path(MODEL) / 'DOWNLOAD_MANIFEST.json').read_text())['revision'],
        'decoding': {'thinking_delimiters_blocked': THINKING_IDS,
                     'multimodal_min_tokens': 1},
        'guided_choice': 'regex' if BACKEND_KIND == 'sglang' else 'structured_outputs.choice'},
        status_code=200 if response.status_code == 200 else 503)


@app.api_route('/v1/{path:path}', methods=['GET', 'POST'])
async def forward(path: str, request: Request):
    body = await request.json() if request.method == 'POST' else None
    if body is not None and path in ('chat/completions', 'completions'):
        choices = body.pop('guided_choice', None)
        if choices:
            if not isinstance(choices, list) or not all(isinstance(x, str) for x in choices):
                return JSONResponse({'error': 'guided_choice_must_be_string_list'}, status_code=400)
            if BACKEND_KIND == 'sglang':
                body['regex'] = '(' + '|'.join(re.escape(x) for x in choices) + ')'
            else:
                body['structured_outputs'] = {'choice': choices}
        if path == 'chat/completions':
            body['chat_template_kwargs'] = {**(body.get('chat_template_kwargs') or {}), 'enable_thinking': False}
            body['logit_bias'] = {**(body.get('logit_bias') or {}),
                                  **{key: -100 for key in THINKING_IDS}}
            multimodal = any(isinstance(message.get('content'), list) and any(
                item.get('type') in ('image_url', 'video_url', 'input_audio')
                for item in message['content']) for message in body.get('messages', []))
            if multimodal:
                # Raw non-thinking image requests can stop before emitting an answer.
                body['min_tokens'] = max(1, body.get('min_tokens', 0))
    client = httpx.AsyncClient(timeout=600, trust_env=False)
    backend_request = client.build_request(request.method, BACKEND + '/v1/' + path,
                                           params=request.query_params, json=body)
    response = await client.send(backend_request, stream=True)
    if body and body.get('stream'):
        async def chunks():
            try:
                async for chunk in response.aiter_bytes():
                    yield chunk
            finally:
                await response.aclose()
                await client.aclose()
        return StreamingResponse(chunks(), status_code=response.status_code,
                                 media_type=response.headers.get('content-type'))
    data = await response.aread()
    audit_path = os.environ.get('A1M_BACKEND_AUDIT')
    if audit_path and body and path == 'chat/completions':
        # Record the actual backend reply without auth headers or client config.
        try:
            reply = json.loads(data)
        except ValueError:
            reply = {'non_json_body': data.decode(errors='replace')}
        rec = {'unix_s': time.time(), 'status_code': response.status_code,
               'request_sha256': hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest(),
               'request_settings': {k: body.get(k) for k in ('model', 'max_tokens', 'max_completion_tokens', 'temperature', 'top_p', 'top_k', 'min_p', 'presence_penalty', 'repetition_penalty', 'stream')},
               'message_count': len(body.get('messages', [])), 'response': reply}
        with Path(audit_path).open('a') as audit:
            audit.write(json.dumps(rec) + '\n')
        request_audit=os.environ.get('A1M_NO_TOOL_REQUEST_AUDIT')
        choices=reply.get('choices',[])
        if request_audit and choices and not any(c.get('message',{}).get('tool_calls') for c in choices):
            with Path(request_audit).open('a') as audit:
                audit.write(json.dumps({'request_sha256':rec['request_sha256'],'request':body,'response':reply})+'\n')
    await response.aclose()
    await client.aclose()
    return Response(data, status_code=response.status_code,
                    media_type=response.headers.get('content-type', 'application/json'))
