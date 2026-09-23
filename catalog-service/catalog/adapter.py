"""ekt.kz mapping verified against user-provided list and detail JSON samples."""
from decimal import Decimal, InvalidOperation
import re
from urllib.parse import urlparse, unquote
from .models import Item

LABELS = {
    'KOLICHESTVO_POLYUSOV':'Количество полюсов',
    'NOMINALNAYA_OTKLYUCHAYUSHCHAYA_SPOSOBNOST':'Отключающая способность',
    'NOMINALNOE_NAPRYAZHENIE':'Номинальное напряжение',
    'NOMINALNYY_TOK':'Номинальный ток',
    'TIP_USTANOVKI':'Тип установки',
    'TORGOVAYA_MARKA':'Торговая марка',
    'ARTIKULPOSTAVSHCHIKA':'Артикул производителя',
    'KRATNOST_MIN':'Минимальная кратность (API)',
    'OBYEM':'Тип изделия',
}
INTERNAL_PREFIXES=('CML2_', 'BRAND_', 'IMYAKARTINKI', 'RECOMMEND', 'NOVINKA', 'SPETSPREDLOZHENIE')
METADATA={'Изображение','Страница товара','Описание','Предупреждение','Минимальная кратность (API)','Артикул производителя','Номинальный ток (в названии)'}


def number(value):
    if isinstance(value,bool) or value is None:
        raise ValueError('Missing numeric field')
    try:
        result=Decimal(str(value).replace(' ','').replace('\xa0','').replace(',','.'))
        if not result.is_finite() or result<0:
            raise ValueError('Invalid nonnegative number')
        return result
    except InvalidOperation as exc:
        raise ValueError('Invalid number') from exc


def safe_partner_url(value):
    if not isinstance(value,str):
        return None
    parsed=urlparse(value)
    if parsed.scheme=='https' and parsed.hostname in ('ekt.kz','www.ekt.kz') and not parsed.username and not parsed.password:
        return value
    return None


def category_for(raw):
    for key in ('category','category_name','CATEGORY'):
        if raw.get(key):
            value=raw[key]
            return str(value.get('name','')) if isinstance(value,dict) else str(value)
    # Stable category identifier derived from the actual catalog hierarchy, not guessed from a name.
    url=safe_partner_url(raw.get('url'))
    if url:
        parts=[unquote(x) for x in urlparse(url).path.split('/') if x]
        if len(parts)>=3 and parts[0]=='catalog':
            return '/'.join(parts[1:-1])
    raise ValueError('Missing category and category URL')


def normalize(raw:dict)->Item:
    def field(*names):
        for name in names:
            if name in raw:
                return raw[name]
        raise ValueError('Missing field: '+names[0])
    identifier=field('id','ID')
    name=field('name','NAME')
    if identifier is None or not name:
        raise ValueError('Missing identity')
    properties=raw.get('specs',raw.get('properties',{})) or {}
    if isinstance(properties,list):
        properties={str(p['name']):p['value'] for p in properties}
    if not isinstance(properties,dict):
        raise ValueError('Invalid properties')
    specs={}
    for key,value in properties.items():
        if value is None or isinstance(value,(dict,list)) or str(key).startswith(INTERNAL_PREFIXES):
            continue
        specs[LABELS.get(str(key),str(key))]=str(value)
    stock=field('stock','quantity','QUANTITY')
    if isinstance(stock,list):
        stock=sum(number(row['quantity']) for row in stock)
    stock=number(stock)
    if stock!=int(stock):
        raise ValueError('Fractional stock is not supported by the integer-qty contract')
    # quantity is the source total; do not add stores to it a second time.
    for warehouse in raw.get('stores',[]) or []:
        if isinstance(warehouse,dict) and warehouse.get('name') and warehouse.get('quantity') is not None:
            qty=number(warehouse['quantity'])
            if qty>0:
                specs['Склад: '+str(warehouse['name'])]=str(qty)
    for external,label in [('image','Изображение'),('url','Страница товара')]:
        url=safe_partner_url(raw.get(external))
        if url:
            specs[label]=url
    if isinstance(raw.get('description'),str) and raw['description'].strip():
        specs['Описание']=raw['description'].strip()
    property_current=specs.get('Номинальный ток','')
    named=re.findall(r'(?<![\w.])(\d+(?:[.,]\d+)?)\s*[АA](?![\w])',str(name),flags=re.I)
    prop=re.fullmatch(r'\s*(\d+(?:[.,]\d+)?)\s*[АA]\s*',property_current,flags=re.I)
    if prop and len(named)==1 and number(named[0])!=number(prop.group(1)):
        specs['Номинальный ток (в названии)']=named[0]+' А'
        specs['Предупреждение']=f'В API противоречие: в названии {named[0]} А, в свойствах {property_current}. Номинальный ток нужно уточнить у менеджера; электрическая совместимость не подтверждена.'
    cert=raw.get('certificate_url')
    if not isinstance(cert,str) or urlparse(cert).scheme not in ('https','http'):
        cert=None
    return Item(id=str(identifier),sku=str(field('sku','article','ARTNUMBER')),name=str(name),
                category=category_for(raw),specs=specs,
                price=float(number(field('price','PRICE'))),stock=int(stock),certificate_url=cert)


def matching_specs(item):
    return {k:v for k,v in item.specs.items() if k not in METADATA and not k.startswith('Склад:')}


def unpack(payload):
    if isinstance(payload,list):
        return payload,None
    data=payload.get('items',payload.get('products',payload.get('data')))
    if isinstance(data,dict):
        data=data.get('items',data.get('products'))
    if not isinstance(data,list):
        raise ValueError('Unsupported partner response shape')
    pages=payload.get('last_page',payload.get('total_pages'))
    if pages is None and isinstance(payload.get('pagination'),dict):
        pages=payload['pagination'].get('total_pages')
    # count=20 is the size of this page, NOT the number of pages.
    return data,int(pages) if pages is not None else None
