import asyncio
import logging
import httpx
from .adapter import normalize, unpack

log=logging.getLogger('catalog')

class PartnerSync:
    def __init__(self,store,base,username,password,max_pages=500,page_limit=0,concurrency=4):
        self.store,self.base,self.auth,self.max_pages=store,base.rstrip('/'),(username,password),max_pages
        self.page_limit=page_limit
        self.semaphore=asyncio.Semaphore(concurrency)
    async def get(self,client,path,params):
        for attempt in range(3):
            try:
                response=await client.get(self.base+path,params=params)
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError,ValueError):
                log.warning('partner_request_failed',extra={'event':'partner_request_failed','attempt':attempt+1})
                if attempt==2:
                    raise
                await asyncio.sleep(.25*2**attempt)
    async def detail(self,client,row):
        async with self.semaphore:
            identifier=row.get('id',row.get('ID'))
            if identifier is None:
                raise ValueError('Missing product ID')
            detail=await self.get(client,'/products/detail',{'id':identifier})
            if isinstance(detail,dict):
                detail=detail.get('data',detail)
            if not isinstance(detail,dict) or str(detail.get('id',detail.get('ID')))!=str(identifier):
                raise ValueError('Wrong product detail identity')
            return normalize({**row,**detail})
    async def once(self):
        try:
            items={};seen_pages=set()
            async with httpx.AsyncClient(auth=self.auth,timeout=5,follow_redirects=False) as client:
                for page in range(1,self.max_pages+1):
                    rows,pages=unpack(await self.get(client,'/products',{'page':page}))
                    if not rows:
                        break
                    fingerprint=tuple(str(r.get('id',r.get('ID'))) for r in rows)
                    if fingerprint in seen_pages:
                        raise ValueError('Pagination repeated a page')
                    seen_pages.add(fingerprint)
                    batch=await asyncio.gather(*(self.detail(client,row) for row in rows),return_exceptions=True)
                    for item in batch:
                        if isinstance(item,Exception):
                            # No silent zero stock or partial overwrite on one bad detail.
                            raise item
                        if item.id in items:
                            raise ValueError('Duplicate product in pagination')
                        items[item.id]=item
                    if (pages is not None and page>=pages) or (self.page_limit and page>=self.page_limit):
                        break
                else:
                    raise ValueError('Pagination safety limit reached')
            if not items:
                raise ValueError('Empty catalog; keeping previous snapshot')
            self.store.replace(list(items.values()))
            log.info('catalog_synced',extra={'event':'catalog_synced','count':len(items)})
            return True
        except (httpx.HTTPError,ValueError,TypeError,KeyError):
            log.warning('catalog_stale_cache',extra={'event':'catalog_stale_cache'})
            return False
    async def run(self,interval):
        while True:
            await self.once()
            await asyncio.sleep(interval)
