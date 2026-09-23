import json
import os
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, urlencode
from urllib.request import build_opener, ProxyHandler

HTTP=build_opener(ProxyHandler({}))

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(Path(__file__).parent/'public'),**kwargs)
    def output(self,data,status=200,kind='application/json; charset=utf-8'):
        payload=data if isinstance(data,bytes) else json.dumps(data,ensure_ascii=False).encode('utf-8')
        self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
    def do_GET(self):
        path=urlsplit(self.path)
        if path.path=='/config.js':
            config={'assistantUrl':os.getenv('ASSISTANT_SERVICE_URL','http://localhost:8002'),'preview':False,
                    'requestTimeoutMs':int(os.getenv('CHAT_TIMEOUT_MS','30000')),'localAI':os.getenv('LLM_PROVIDER')=='ollama',
                    'catalogMode':os.getenv('CATALOG_MODE','demo')}
            self.output(('window.APP_CONFIG='+json.dumps(config)+';').encode(),kind='application/javascript')
        elif path.path=='/catalog-data.json':
            # Storefront-only read proxy; the chat still calls only /assistant/message.
            try:
                q=parse_qs(path.query).get('q',[''])[0][:256]
                base=os.getenv('CATALOG_SERVICE_URL','http://localhost:8001').rstrip('/')
                with HTTP.open(base+'/catalog/search?'+urlencode({'q':q,'limit':50}),timeout=3) as response:
                    result=json.load(response)
                with HTTP.open(base+'/health',timeout=3) as response:
                    health=json.load(response)
                self.output({'items':result['items'],'last_sync':health['last_sync'],'cached_count':health['catalog_items_cached'],
                             'page_limit':int(os.getenv('EKT_PAGE_LIMIT','0'))})
            except (OSError,ValueError,KeyError):
                self.output({'error':{'code':'catalog_unavailable','message':'Каталог пока недоступен. Проверьте окно запуска.'}},503)
        else:
            super().do_GET()
    def send_error(self,code,message=None,explain=None):
        self.output({'error':{'code':'http_error','message':message or 'Request failed'}},code)

if __name__=='__main__':
    ThreadingHTTPServer((os.getenv('WIDGET_HOST','127.0.0.1'),3000),Handler).serve_forever()
