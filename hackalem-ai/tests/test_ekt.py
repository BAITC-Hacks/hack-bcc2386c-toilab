import asyncio
import copy
import json
from pathlib import Path
import httpx
import pytest
from catalog.adapter import normalize,unpack,matching_specs
from catalog.data import Store
from catalog.sync import PartnerSync

FIXTURES=Path(__file__).parent/'fixtures'
def fixture(name):return json.loads((FIXTURES/name).read_text(encoding='utf-8'))

def test_real_sample_mapping_and_conflict():
    item=normalize(fixture('ekt_detail.json'))
    assert item.id=='515291' and item.sku=='200300285_'
    assert item.price==64920 and item.stock==23
    assert item.category=='nizkovoltnaya_apparatura/silovye_avtomaticheskie_vyklyuchateli/drx250_mt_10_250_a_legrand'
    assert item.specs['Номинальный ток']=='250 А'
    assert item.specs['Номинальный ток (в названии)']=='160 А'
    assert 'противоречие' in item.specs['Предупреждение']
    assert item.specs['Склад: Алматы']=='5'
    assert 'RECOMMEND' not in item.specs and 'CML2_TRAITS' not in item.specs
    assert item.certificate_url is None
    assert 'Изображение' not in matching_specs(item)
    assert 'Склад: Алматы' not in matching_specs(item)

def test_list_has_no_stock_and_cannot_be_used_as_detail():
    page=fixture('ekt_page.json')
    rows,pages=unpack(page)
    assert len(rows)==20 and pages is None # count is page length
    with pytest.raises(ValueError):normalize(rows[0])

def test_no_credentials_or_external_hosts_in_image():
    raw=fixture('ekt_detail.json')
    raw['image']='https://ekt.kz@evil.example/image.jpg'
    assert 'Изображение' not in normalize(raw).specs

def test_concurrent_detail_sync_is_atomic_and_limited(monkeypatch):
    for key in ('ALL_PROXY','HTTP_PROXY','HTTPS_PROXY','all_proxy','http_proxy','https_proxy'):
        monkeypatch.delenv(key,raising=False)
    store=Store(':memory:')
    sample=fixture('ekt_detail.json')
    calls=[];active=0;peak=0
    sync=PartnerSync(store,'https://ekt.kz/api','','',page_limit=2,concurrency=2)
    async def get(client,path,params):
        nonlocal active,peak
        calls.append((path,params))
        if path=='/products':
            return {'page':params['page'],'per_page':3,'count':3,'items':[{'id':str(params['page']*10+i)} for i in range(3)]}
        active+=1;peak=max(peak,active)
        await asyncio.sleep(.001)
        active-=1
        return {**sample,'id':params['id']}
    sync.get=get
    assert asyncio.run(sync.once())
    assert len(store.items())==6 and peak==2
    assert max(params['page'] for path,params in calls if path=='/products')==2
    snapshot=store.items()
    async def bad(client,path,params):
        if path=='/products':return {'items':[{'id':'10'}]}
        return {**sample,'id':'wrong'}
    sync.get=bad
    assert not asyncio.run(sync.once()) and store.items()==snapshot
