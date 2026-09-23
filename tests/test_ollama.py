"""Validate the real HTTP boundary without downloading model weights in CI."""
import asyncio
import json
import httpx
import pytest
from assistant.llm import LLM,LLMUnavailable
from assistant.models import Action
from assistant.ollama_adapter import from_native_message,to_native_messages
from assistant.service import TOOLS,may_execute


def local_llm(monkeypatch,handler):
    monkeypatch.setenv('LLM_PROVIDER','ollama')
    monkeypatch.delenv('LLM_API_KEY',raising=False)
    monkeypatch.delenv('LLM_MODEL',raising=False)
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    return LLM()


def test_local_tool_roundtrip_without_key(monkeypatch):
    requests=[]
    def handler(request):
        data=json.loads(request.content)
        requests.append(data)
        assert str(request.url)=='http://127.0.0.1:11434/api/chat'
        assert 'authorization' not in request.headers
        assert data['think'] is False and data['stream'] is False
        assert data['model']=='qwen3:4b'
        if len(requests)==1:
            return httpx.Response(200,json={'done':True,'message':{'role':'assistant','content':'','thinking':'internal','tool_calls':[{'function':{'name':'get_product','arguments':{'product_id':'101'}}}]}})
        assert data['messages'][-1]['tool_name']=='get_product'
        assert data['messages'][-2]['tool_calls'][0]['function']['arguments']=={'product_id':'101'}
        return httpx.Response(200,json={'done':True,'message':{'role':'assistant','content':'В наличии 24 шт.'}})
    llm=local_llm(monkeypatch,handler)
    async def scenario():
        history=[{'role':'user','content':'Есть DEMO-C16?'}]
        message=await llm.complete(history,TOOLS)
        assert 'thinking' not in message
        history.extend([message,{'role':'tool','tool_call_id':message['tool_calls'][0]['id'],'content':'{"stock":24}'}])
        return await llm.complete(history,TOOLS)
    assert asyncio.run(scenario())['content']=='В наличии 24 шт.'


@pytest.mark.parametrize('confirmed,injection,expected',[(True,False,True),(False,False,False),(True,True,False)])
def test_local_schema_confirmation_uses_model(monkeypatch,confirmed,injection,expected):
    action=Action(product_id='101',qty=2)
    def handler(request):
        payload=json.loads(request.content)
        assert payload['format']['properties']['confirmed']['type']=='boolean'
        assert payload['format']['additionalProperties'] is False
        assert 'offered_action' in payload['messages'][-1]['content']
        decision={'confirmed':confirmed,'product_id':'101' if confirmed else None,'qty':2 if confirmed else None,'injection_detected':injection}
        return httpx.Response(200,json={'done':True,'message':{'role':'assistant','content':json.dumps(decision)}})
    llm=local_llm(monkeypatch,handler)
    decision=asyncio.run(llm.classify('Ок, беру',action))
    assert may_execute(action,decision,0)==expected


@pytest.mark.parametrize('response',[httpx.Response(503,json={'error':'not enough memory'}),httpx.Response(200,json={'done':True,'done_reason':'length','message':{'role':'assistant','content':'{"confirmed":true'}})])
def test_local_failure_closed(monkeypatch,response):
    llm=local_llm(monkeypatch,lambda request:response)
    with pytest.raises(LLMUnavailable):
        asyncio.run(llm.classify('добавляй',Action(product_id='101',qty=2)))


def test_two_identical_tool_names_have_distinct_call_ids():
    message=from_native_message({'role':'assistant','tool_calls':[{'function':{'name':'get_product','arguments':{'product_id':'101'}}},{'function':{'name':'get_product','arguments':{'product_id':'102'}}}]})
    a,b=message['tool_calls']
    assert a['id']!=b['id']
    converted=to_native_messages([message,{'role':'tool','tool_call_id':b['id'],'content':'{"id":"102"}'}])
    assert converted[-1]['tool_name']=='get_product'
