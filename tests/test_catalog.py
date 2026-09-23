import asyncio
import json
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient
from catalog.adapter import normalize,unpack
from catalog.models import AddRequest,Item
from catalog.data import Store
from catalog.services import CatalogService
from catalog.api import create_app
from catalog.sync import PartnerSync

SID="c6065580-d434-402e-94c8-123456789012"
@pytest.fixture
def service():
    store=Store(":memory:")
    data=json.loads((Path(__file__).parents[1]/"catalog-service/catalog/demo.json").read_text(encoding="utf-8"))
    store.replace([Item.model_validate(x) for x in data])
    return CatalogService(store,"http://localhost:8001")

def request(**kwargs): return AddRequest(session_id=SID,product_id="101",qty=kwargs.get("qty",2),confirmed=kwargs.get("confirmed",True))

def test_adapter():
    item=normalize({"ID":7,"ARTNUMBER":"X","NAME":"Автомат","category":{"name":"Защита"},"PRICE":"1 234,50","QUANTITY":"2","properties":[{"name":"Ток","value":16}],"certificate_url":"javascript:alert(1)"})
    assert item.id=="7" and item.price==1234.5 and item.stock==2
    assert item.specs=={"Ток":"16"} and item.certificate_url is None

def test_missing_stock_not_invented():
    with pytest.raises(ValueError): normalize({"id":1,"sku":"x","name":"x","category":"x","price":1})

def test_pagination(): assert unpack({"products":[{"id":1}],"pagination":{"total_pages":2}})==([{"id":1}],2)

def test_happy_and_idempotent(service):
    first=service.add(request());second=service.add(request())
    assert first==second and first["success"]
    assert first["cart"]["items"]==[{"product_id":"101","qty":2}]
    service.add(request(qty=3))
    assert service.cart(SID)["items"][0]["qty"]==3

@pytest.mark.parametrize("kwargs,code",[({"qty":999},"qty_exceeds_stock"),({"confirmed":False},"not_confirmed")])
def test_rejections_do_not_mutate(service,kwargs,code):
    service.add(request());before=service.cart(SID)
    assert service.add(request(**kwargs))["error"]["code"]==code
    assert service.cart(SID)==before

def test_not_found(service):
    assert service.add(AddRequest(session_id=SID,product_id="absent",qty=1,confirmed=True))["error"]["code"]=="not_found"
    assert service.cart(SID)["items"]==[]

def test_analogs(service):
    results=service.analogs("102",10)
    assert results[0].id=="101" and all(p.id!="102" and p.category==results[0].category for p in results)

@pytest.mark.parametrize("qty,confirmed",[(0,True),(-1,True),(1.5,True),(True,True),(1,"true")])
def test_api_validation(service,qty,confirmed):
    with TestClient(create_app(service.store)) as client:
        r=client.post("/cart/add",json={"session_id":SID,"product_id":"101","qty":qty,"confirmed":confirmed})
        assert r.status_code==400 and "error" in r.json()

def test_contracts_and_cart_page(service):
    with TestClient(create_app(service.store)) as client:
        assert client.get("/health").status_code==200
        assert client.get("/catalog/product/101").json()["sku"]=="DEMO-C16"
        assert client.get("/catalog/product/nope").status_code==404
        assert client.get("/catalog/search?q=C16&limit=0").status_code==400
        r=client.post("/cart/add",json=request().model_dump())
        assert r.json()["success"]
        page=client.get("/cart/view/"+SID)
        assert page.status_code==200 and "ВА47-29" in page.text

def test_sync_failure_preserves_cache(service,monkeypatch):
    for key in ("ALL_PROXY","HTTP_PROXY","HTTPS_PROXY","all_proxy","http_proxy","https_proxy"):
        monkeypatch.delenv(key,raising=False)
    sync=PartnerSync(service.store,"http://invalid","","",max_pages=1)
    async def fail(*args,**kwargs): raise httpx.ConnectError("offline")
    sync.get=fail
    before=service.store.items()
    assert asyncio.run(sync.once()) is False and service.store.items()==before

def test_auth(service,monkeypatch):
    monkeypatch.setenv("INTERNAL_API_TOKEN","test-only-token")
    with TestClient(create_app(service.store)) as client:
        assert client.post("/cart/add",json=request().model_dump()).status_code==401
        assert client.post("/cart/add",json=request().model_dump(),headers={"Authorization":"Bearer test-only-token"}).json()["success"]
