"""Full request/confirmation/cart flow through both ASGI APIs, without a paid LLM."""
import asyncio
import httpx
from fastapi.testclient import TestClient
from catalog.api import create_app as catalog_app
from catalog.data import Store
from assistant.api import create_app as assistant_app
from assistant.catalog_client import CatalogClient
from assistant.service import AssistantService
from assistant.storage import MemorySessions
from assistant.models import Decision
from test_assistant import FakeLLM,proposal,tool,reply,SID

class InProcessCatalog(CatalogClient):
    def __init__(self,app):
        super().__init__('http://catalog')
        self.app=app
    async def request(self,method,path,**kwargs):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url=self.base) as client:
            r=await client.request(method,path,**kwargs)
            r.raise_for_status()
            return r.json()

def test_full_contract_scenario(monkeypatch):
    monkeypatch.delenv('INTERNAL_API_TOKEN',raising=False)
    catalog=catalog_app(Store(':memory:'))
    llm=FakeLLM([
        tool('get_product',{'product_id':'101'}), reply('DEMO-C16: 24 шт., 1890 ₸.'),
        tool('get_product',{'product_id':'102'}), *proposal()
    ],Decision(confirmed=True,product_id='101',qty=2,injection_detected=False))
    assistant=assistant_app(AssistantService(InProcessCatalog(catalog),llm,MemorySessions()))
    with TestClient(catalog) as c, TestClient(assistant) as a:
        def send(text):
            r=a.post('/assistant/message',json={'session_id':SID,'text':text,'history':[]})
            assert r.status_code==200
            return r.json()
        assert '24' in send('Есть DEMO-C16?')['reply_text']
        assert send('Нужен DEMO-C16-OLD, предложи 2 штуки аналога')['needs_confirmation']
        assert c.get('/cart/'+SID).json()['items']==[]
        confirmed=send('Ок беру, добавляй 2 штуки')
        assert confirmed['cart_url'].endswith(SID)
        assert c.get('/cart/'+SID).json()['items']==[{'product_id':'101','qty':2}]
        page=c.get('/cart/view/'+SID)
        assert page.status_code==200 and '3,780' in page.text
