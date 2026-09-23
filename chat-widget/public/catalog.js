/* Storefront data, separate from the chat widget and its message contract. */
if (config.catalogMode === 'live') {
  const root = document.querySelector('#products');
  const notice = document.querySelector('.notice p');
  const title = document.querySelector('.product-toolbar h2');
  let loadedItems = [], selected = 'all', timer = null, requestNumber = 0;
  document.querySelector('.utility b').textContent = 'КАТАЛОГ EKT.KZ';
  document.querySelector('.breadcrumb').textContent = 'Главная / Каталог ekt.kz';
  document.querySelector('.catalog-label p').textContent = 'товаров в загруженной выборке';
  document.querySelector('.catalog-label>span').textContent = '…';
  title.textContent = 'Товары ekt.kz';
  notice.textContent = 'Получаем реальную выборку из API ekt.kz. Это может занять некоторое время.';
  document.querySelector('[data-question*="сертификат"]').dataset.question='Есть ли сертификат у товара 200300285_?';
  const quick=document.querySelectorAll('#quick [data-question]');
  quick[0].dataset.question='Расскажи о товаре 200300285_: цена, остаток, характеристики. Укажи противоречия, если они есть.';
  quick[1].dataset.question='Подбери аналоги товара 515291 и объясни отличия. Если характеристики противоречат друг другу, предупреди об этом.';
  document.querySelector('#message').placeholder='Название, артикул или вопрос о товаре';
  document.querySelectorAll('.category').forEach(b=>b.remove());
  const sidebar=document.querySelector('aside');
  const categories=document.createElement('div');sidebar.insertBefore(categories,document.querySelector('.advisor-note'));
  const search=document.createElement('form');search.className='catalog-search';
  const input=document.createElement('input');input.type='search';input.maxLength=256;input.placeholder='Поиск в загруженной выборке';input.setAttribute('aria-label','Поиск товаров');
  const submit=document.createElement('button');submit.type='submit';submit.textContent='Найти';search.append(input,submit);title.parentElement.after(search);
  function element(tag,text,className){const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(className)el.className=className;return el;}
  function message(text){root.replaceChildren(element('p',text,'catalog-state'));}
  function imageURL(value){try{const u=new URL(value);return u.protocol==='https:'&&['ekt.kz','www.ekt.kz'].includes(u.hostname)&&!u.username&&!u.password?u.href:null;}catch{return null;}}
  function label(item){return item.specs['Тип изделия']||item.category.split('/').at(-1).replaceAll('_',' ');}
  function render(){
    const list=loadedItems.filter(p=>selected==='all'||p.category===selected);root.replaceChildren();
    if(!list.length)message('В загруженной выборке нет подходящих товаров. Попробуйте другой запрос.');
    for(const p of list){
      const card=element('article',undefined,'product');
      const top=element('div',undefined,'product-top');top.append(element('span',label(p),'tag'));
      const url=imageURL(p.specs['Изображение']);
      if(url){const img=document.createElement('img');img.src=url;img.alt=p.name;img.loading='lazy';img.referrerPolicy='no-referrer';img.className='real-product-image';img.onerror=()=>img.replaceWith(element('span','Фото недоступно','placeholder'));top.append(img);}
      else top.append(element('span','Без фотографии','placeholder'));
      const content=element('div',undefined,'product-content');content.append(element('span','АРТИКУЛ '+p.sku,'sku'),element('h3',p.name));
      const specs=element('div',undefined,'spec-pills');
      for(const key of ['Номинальный ток','Количество полюсов','Номинальное напряжение'])if(p.specs[key])specs.append(element('span',key+': '+p.specs[key]));
      content.append(specs);
      if(p.specs['Предупреждение'])content.append(element('p',p.specs['Предупреждение'],'product-warning'));
      const prices=element('div',undefined,'product-price');prices.append(element('span',money(p.price)+' ₸','price'),element('span',p.stock?'В наличии · '+p.stock:'Нет в наличии','stock'+(p.stock?'':' out')));content.append(prices);
      const button=element('button',p.stock?'Уточнить и выбрать ↗':'Подобрать аналог ↗');button.onclick=()=>{openChat();send(`Расскажи о товаре ${p.id}, артикул ${p.sku}. Укажи цену, наличие, характеристики и предупреждения. ${p.stock?'':'Если отсутствует, подбери доступные аналоги и объясни отличия.'}`)};content.append(button);
      card.append(top,content);root.append(card);
    }
    document.querySelector('#result-count').textContent=list.length+' позиций';
  }
  function refreshCategories(){
    selected='all';categories.replaceChildren();
    const values=new Map([['all','Все товары']]);loadedItems.forEach(p=>{if(!values.has(p.category))values.set(p.category,label(p));});
    for(const [key,text] of values){const b=element('button',text,'category'+(key==='all'?' active':''));b.onclick=()=>{selected=key;categories.querySelectorAll('button').forEach(x=>x.classList.remove('active'));b.classList.add('active');render();};categories.append(b);}
  }
  async function load(){
    clearTimeout(timer);const version=++requestNumber;submit.disabled=true;
    try{
      const response=await fetch('/catalog-data.json?q='+encodeURIComponent(input.value),{cache:'no-store',signal:AbortSignal.timeout(8000)});
      const data=await response.json();if(version!==requestNumber)return;if(!response.ok)throw new Error(data.error?.message||'Ошибка каталога');
      loadedItems=data.items;document.querySelector('.catalog-label>span').textContent=String(data.cached_count);
      if(!data.cached_count){message('Каталог ещё загружается. Если товары не появятся, посмотрите окно запуска и журнал catalog.log.');notice.textContent='Синхронизация ekt.kz. Демонстрационные цены не используются.';timer=setTimeout(load,5000);return;}
      notice.textContent='Реальные данные ekt.kz'+(data.page_limit?' · первые '+data.page_limit+' страницы каталога':'')+' · загружено '+data.cached_count+' товаров · обновлено '+new Date(data.last_sync).toLocaleString('ru-RU')+'. Цены и остатки могут измениться.';
      refreshCategories();render();timer=setTimeout(load,60000);
    }catch(error){if(version===requestNumber){message(error.message||'Не удалось получить каталог.');notice.textContent='Нет связи с каталогом. Демонстрационные данные не подставляются.';timer=setTimeout(load,15000);}}
    finally{if(version===requestNumber)submit.disabled=false;}
  }
  search.onsubmit=e=>{e.preventDefault();load();};message('Загружаем товары ekt.kz…');load();
}
