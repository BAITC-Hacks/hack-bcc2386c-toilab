"""Live partner + local AI launcher. Credentials remain in process environment only."""
import base64
import getpass
import json
import os
import sys
import urllib.error
import urllib.request
import start_local_ai


def main():
    print('Подключение реального каталога ekt.kz\n')
    occupied=start_local_ai.busy_ports([8001,8002,3000])
    if occupied:
        print('Сначала остановите старый запуск: Ctrl+C в каждом терминале или в окне запуска.')
        return 1
    username=os.environ.get('PARTNER_API_USER') or input('Логин API (Enter — apiuser): ').strip() or 'apiuser'
    password=os.environ.get('PARTNER_API_PASSWORD') or getpass.getpass('Пароль API ekt.kz (при вводе не отображается): ')
    if not password:
        print('Пароль не введён. Повторите запуск.')
        return 1
    base='https://ekt.kz/api'
    auth=base64.b64encode((username+':'+password).encode('utf-8')).decode('ascii')
    request=urllib.request.Request(base+'/products/detail?id=515291',headers={'Authorization':'Basic '+auth})
    print('Проверяю доступ к товару 515291…',flush=True)
    try:
        # Redirects must never forward the Basic Auth header to another host.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs): return None
        opener=urllib.request.build_opener(NoRedirect)
        with opener.open(request,timeout=15) as response:
            product=json.load(response)
        if not isinstance(product,dict) or str(product.get('id'))!='515291' or 'quantity' not in product or 'price' not in product:
            raise ValueError('unexpected_shape')
        print('API доступен. Получена карточка: '+str(product.get('name','515291')),flush=True)
    except urllib.error.HTTPError as exc:
        print('Ошибка доступа к ekt.kz: HTTP '+str(exc.code)+'. Проверьте логин/пароль или доступность API.')
        return 1
    except (OSError,ValueError):
        print('Не удалось получить карточку ekt.kz. Проверьте интернет; если ошибка повторится, пришлите снимок этого окна без пароля.')
        return 1
    os.environ.update({'CATALOG_MODE':'live','PARTNER_API_URL':base,'PARTNER_API_USER':username,
                       'PARTNER_API_PASSWORD':password,'EKT_PAGE_LIMIT':os.environ.get('EKT_PAGE_LIMIT','2')})
    try:
        return start_local_ai.main()
    finally:
        os.environ.pop('PARTNER_API_PASSWORD',None)


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('\nЗапуск отменён.')
