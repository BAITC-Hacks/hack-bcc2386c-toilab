import httpx
from urllib.parse import quote

class CatalogUnavailable(Exception): pass

class CatalogClient:
    def __init__(self,base,token=""):
        self.base=base.rstrip("/");self.token=token
    async def request(self,method,path,**kwargs):
        try:
            async with httpx.AsyncClient(timeout=3,trust_env=False,headers={"Authorization":"Bearer "+self.token} if self.token else {}) as client:
                response=await client.request(method,self.base+path,**kwargs)
                if response.status_code==404:
                    return {"error":{"code":"not_found","message":"Товар не найден."}}
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError,ValueError) as exc:
            raise CatalogUnavailable() from exc
    async def health(self):
        try: return (await self.request("GET","/health")).get("status")=="ok"
        except CatalogUnavailable: return False
    async def search(self,q,limit=5): return await self.request("GET","/catalog/search",params={"q":q,"limit":limit})
    async def product(self,product_id): return await self.request("GET","/catalog/product/"+quote(product_id,safe=""))
    async def analogs(self,product_id,limit=5): return await self.request("GET","/catalog/analogs/"+quote(product_id,safe=""),params={"limit":limit})
    async def add(self,session_id,action):
        return await self.request("POST","/cart/add",json={"session_id":session_id,"product_id":action.product_id,"qty":action.qty,"confirmed":True})
