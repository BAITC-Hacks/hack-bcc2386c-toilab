import logging
from urllib.parse import quote
from .models import AddRequest
from .adapter import matching_specs

log=logging.getLogger("catalog")

class CatalogService:
    def __init__(self, store, public_url):
        self.store,self.public_url=store,public_url.rstrip("/")
    def product(self, identifier):
        return next((p for p in self.store.items() if p.id==identifier),None)
    def search(self,q,limit):
        tokens=q.casefold().split()
        return [p for p in self.store.items() if all(t in (p.id+" "+p.sku+" "+p.name+" "+p.category).casefold() for t in tokens)][:limit]
    def analogs(self,identifier,limit):
        original=self.product(identifier)
        if original is None:
            return None
        def score(item):
            return sum(matching_specs(original).get(k)==v for k,v in matching_specs(item).items())
        candidates=[p for p in self.store.items() if p.id!=identifier and p.category==original.category]
        return sorted(candidates,key=lambda p:(-score(p),p.id))[:limit]
    def cart(self,session):
        return {"items":self.store.cart(session),"cart_url":self.public_url+"/cart/view/"+quote(session,safe="")}
    def add(self,request:AddRequest):
        # Lock covers snapshot, validation and write. Never mutate on a refusal.
        with self.store.lock:
            item=self.product(request.product_id)
            code=message=None
            if request.confirmed is not True:
                code,message="not_confirmed","Требуется явное подтверждение клиента."
            elif item is None:
                code,message="not_found","Товар не найден."
            elif request.qty>item.stock:
                code,message="qty_exceeds_stock","Количество превышает доступный остаток."
            if code:
                log.warning("cart_refused",extra={"event":"cart_refused","reason":code})
                return {"success":False,"error":{"code":code,"message":message}}
            self.store.set_qty(request.session_id,request.product_id,request.qty)
            return {"success":True,"cart":self.cart(request.session_id)}
