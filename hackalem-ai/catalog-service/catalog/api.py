import asyncio
import contextlib
import html
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, HTMLResponse
from starlette.exceptions import HTTPException
from .data import Store
from .models import Item, AddRequest
from .services import CatalogService
from .sync import PartnerSync

class JsonLog(logging.Formatter):
    def format(self,record):
        return json.dumps({"level":record.levelname,"event":getattr(record,"event",record.getMessage()),**{k:getattr(record,k) for k in ("count","reason","attempt") if hasattr(record,k)}})
handler=logging.StreamHandler();handler.setFormatter(JsonLog())
logging.getLogger("catalog").addHandler(handler);logging.getLogger("catalog").setLevel(logging.INFO)

def create_app(store=None):
    store=store or Store(os.getenv("CATALOG_DB","data/catalog.sqlite"))
    service=CatalogService(store,os.getenv("PUBLIC_CATALOG_URL","http://localhost:8001"))
    @asynccontextmanager
    async def lifespan(app):
        task=None
        mode=os.getenv("CATALOG_MODE","demo")
        if mode=="demo" and not store.items():
            store.replace([Item.model_validate(p) for p in json.loads((Path(__file__).parent/"demo.json").read_text(encoding="utf-8"))])
        if mode=="live":
            sync=PartnerSync(store,os.getenv("PARTNER_API_URL","https://ekt.kz/api"),os.getenv("PARTNER_API_USER",""),os.getenv("PARTNER_API_PASSWORD",""),page_limit=int(os.getenv("EKT_PAGE_LIMIT","0")))
            task=asyncio.create_task(sync.run(int(os.getenv("SYNC_INTERVAL","300"))))
        yield
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError): await task
    app=FastAPI(title="HackAlem Catalog",lifespan=lifespan)
    app.state.service=service
    def error(status,code,message):
        return JSONResponse(status_code=status,content={"error":{"code":code,"message":message}})
    @app.exception_handler(RequestValidationError)
    async def validation(request,exc): return error(400,"invalid_request","Проверьте поля запроса: "+", ".join(str(e["loc"][-1]) for e in exc.errors()))
    @app.exception_handler(HTTPException)
    async def http_error(request,exc): return error(exc.status_code,"not_found" if exc.status_code==404 else "http_error",str(exc.detail))
    @app.exception_handler(Exception)
    async def unexpected(request,exc):
        logging.getLogger("catalog").error("internal_error")
        return error(500,"internal_error","Временная ошибка сервиса.")
    @app.middleware("http")
    async def cart_auth(request:Request,call_next):
        token=os.getenv("INTERNAL_API_TOKEN","")
        if request.url.path=="/cart/add" and token and request.headers.get("authorization")!="Bearer "+token:
            return error(401,"unauthorized","Нет доступа к изменению корзины.")
        return await call_next(request)
    @app.get("/health")
    def health(): return {"status":"ok","catalog_items_cached":len(store.items()),"last_sync":store.last_sync()}
    @app.get("/catalog/search")
    def search(q:str=Query(min_length=0,max_length=256),limit:int=Query(10,ge=1,le=50)): return {"items":service.search(q,limit)}
    @app.get("/catalog/product/{identifier}")
    def product(identifier:str): return service.product(identifier) or error(404,"not_found","Товар не найден.")
    @app.get("/catalog/analogs/{identifier}")
    def analogs(identifier:str,limit:int=Query(5,ge=1,le=50)):
        result=service.analogs(identifier,limit)
        return {"items":result} if result is not None else error(404,"not_found","Товар не найден.")
    @app.post("/cart/add")
    def add(body:AddRequest): return service.add(body)
    @app.get("/cart/{session}")
    def cart(session:str): return service.cart(session)
    @app.get("/cart/view/{session}",response_class=HTMLResponse)
    def cart_page(session:str):
        rows=[];total=0
        for row in service.cart(session)["items"]:
            item=service.product(row["product_id"])
            if item:
                total+=item.price*row["qty"]
                rows.append(f"<tr><td>{html.escape(item.name)}</td><td>{row['qty']}</td><td>{item.price:,.0f} ₸</td></tr>")
        content="".join(rows) or '<tr><td colspan="3">Корзина пока пуста</td></tr>'
        return '<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Корзина — HackAlem</title><style>body{font:18px system-ui;background:#f3f5f7;color:#182433;margin:0;padding:6vw}main{max-width:850px;margin:auto;background:white;padding:32px;border-radius:20px}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:20px 8px;border-bottom:1px solid #ddd}h1{font-size:40px}small{color:#697586}</style><main><small>HACKALEM / КОРЗИНА</small><h1>Вы выбрали</h1><table><tr><th>Товар</th><th>Кол-во</th><th>Цена за шт.</th></tr>'+content+f'</table><h2>Итого: {total:,.0f} ₸</h2><p>Это корзина прототипа. Заказ и оплата не выполняются. Остатки и цены требуют повторной проверки перед оформлением.</p></main></html>'
    return app
app=create_app()
