# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Typed choice adapter for the unmodified stock Qwen vLLM gateway."""

import json
import time
from urllib.request import Request, urlopen


def score(endpoint, context, instruction, options, *, memory_text=None):
    letters = [chr(65+i) for i in range(len(options))]
    if not 1<=len(options)<=24:
        raise ValueError('expected 1..24 typed choices')
    prompt=context+'\n\n'+instruction+'\n'+ '\n'.join(
        letter+'. '+option for letter,option in zip(letters,options))+'\nReturn one choice letter.'
    messages=[]
    if memory_text is not None:
        messages.append({'role':'system','content':memory_text})
    messages.append({'role':'user','content':prompt})
    body={'model':'Qwen3.6-27B-FP8','messages':messages,'guided_choice':letters,
          'max_completion_tokens':8192,'temperature':.7,'top_p':.8,'top_k':20,'min_p':0,
          'presence_penalty':1.5,'repetition_penalty':1.0,'stream':False}
    request=Request(endpoint.rstrip('/')+'/chat/completions',
                    data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    started=time.perf_counter()
    with urlopen(request,timeout=180) as response:
        result=json.load(response)
    elapsed=time.perf_counter()-started
    choice=result['choices'][0]['message']['content'].strip()
    if choice not in letters:
        raise ValueError('stock guided_choice did not return an allowed letter')
    return {'selected':letters.index(choice),'probabilities':None,'model':result['model'],
            'choice_http_round_trip_s':elapsed,'model_inference_s':None,
            'decision_inference_kind':'http_round_trip_not_server_compute',
            'usage':result.get('usage'),'stock_request':body,'stock_response':result,
            'sampling':{k:body[k] for k in ('temperature','top_p','top_k','min_p','presence_penalty','repetition_penalty')}}
