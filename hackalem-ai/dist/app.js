"use strict";
const $=s=>document.querySelector(s);
const config=window.APP_CONFIG||{};
const demo=[
 {id:"101",sku:"DEMO-C16",title:"Автоматический выключатель ВА47-29 C16",category:"breaker",price:1890,stock:24,specs:["16 А","1 полюс","4.5 кА"],mark:"01"},
 {id:"102",sku:"DEMO-C16-OLD",title:"Автоматический выключатель C16 Classic",category:"breaker",price:1750,stock:0,specs:["16 А","1 полюс","4.5 кА"],mark:"02"},
 {id:"103",sku:"DEMO-C25",title:"Автоматический выключатель ВА47-29 C25",category:"breaker",price:2190,stock:18,specs:["25 А","1 полюс","Тип C"],mark:"03"},
 {id:"104",sku:"DEMO-CABLE",title:"Кабель ВВГнг-LS 3×2.5 · 100 м",category:"cable",price:42900,stock:12,specs:["3 жилы","2.5 мм²","100 м"],mark:"04"}
];
function paymentData(text){return /(?:\d[ -]?){13,19}/.test(text)||/\b(?:cvv|cvc|pin)[ :‐-]*\d{3,6}\b/i.test(text)||/\b[A-Z]{2}\d{2}[A-Z0-9]{12,30}\b/i.test(text)}
const money=n=>n.toLocaleString("ru-RU");
function products(filter="all"){
 const list=demo.filter(p=>filter==="all"||p.category===filter);$("#products").replaceChildren();
 for(const p of list){
  const card=document.createElement("article");card.className="product";
  card.innerHTML=`<div class="product-top"><span class="tag">${p.category==="breaker"?"Модульное оборудование":"Кабельная продукция"}</span><div class="placeholder"><strong>${p.mark}</strong><small>ДЕМО / БЕЗ ФОТО</small></div></div><div class="product-content"><span class="sku">АРТИКУЛ ${p.sku}</span><h3>${p.title}</h3><div class="spec-pills">${p.specs.map(s=>`<span>${s}</span>`).join("")}</div><div class="product-price"><span class="price">${money(p.price)} <small>₸ / шт.</small></span><span class="stock ${p.stock?"":"out"}">${p.stock?"В наличии · "+p.stock+" шт.":"Нет в наличии"}</span></div><button><span>${p.stock?"Уточнить и выбрать":"Найти аналог"}</span><span>↗</span></button></div>`;
  card.querySelector("button").onclick=()=>{openChat();send(p.stock?`Расскажи о ${p.sku}: цена, наличие, характеристики и сертификат.`:`${p.sku} отсутствует? Подбери аналог, объясни сходство и предложи добавить 1 шт.`)};
  $("#products").append(card);
 }
 $("#result-count").textContent=list.length+" позиции";
}
products();
for(const b of document.querySelectorAll("[data-filter]"))b.onclick=()=>{document.querySelectorAll(".category").forEach(x=>x.classList.remove("active"));b.classList.add("active");products(b.dataset.filter)};
let saved={};try{saved=JSON.parse(localStorage.getItem("hackalem-v1")||"{}")}catch{}
const sessionId=/^[0-9a-f-]{36}$/i.test(saved.sessionId||"")?saved.sessionId:crypto.randomUUID();
let history=Array.isArray(saved.history)?saved.history.filter(m=>m&&["user","assistant"].includes(m.role)&&typeof m.text==="string"&&!paymentData(m.text)).slice(-40):[];
let cartUrl=validUrl(saved.cartUrl),busy=false;
function validUrl(value){try{const u=new URL(value);return ["https:","http:"].includes(u.protocol)?u.href:null}catch{return null}}
function persist(){try{localStorage.setItem("hackalem-v1",JSON.stringify({sessionId,history:history.slice(-40),cartUrl}))}catch{}}
function renderMessage(m){
 const div=document.createElement("div");div.className="msg "+m.role+(m.confirm?" confirm":"")+(m.error?" error":"");
 if(m.confirm){const badge=document.createElement("span");badge.className="badge";badge.textContent="ЖДЁМ ВАШЕГО ПОДТВЕРЖДЕНИЯ";div.append(badge)}
 div.append(document.createTextNode(m.text));const url=validUrl(m.cartUrl);
 if(url){const a=document.createElement("a");a.className="cart-link";a.href=url;a.target="_blank";a.rel="noopener noreferrer";a.textContent="Перейти в корзину ↗";div.append(a)}
 $("#messages").append(div);$("#messages").scrollTop=$("#messages").scrollHeight;
}
function add(m){history.push(m);history=history.slice(-40);renderMessage(m);persist()}
if(history.length)history.forEach(renderMessage);else renderMessage({role:"assistant",text:"Здравствуйте! Я помогу разобраться в характеристиках, найти товар и подобрать замену. С чего начнём?"});
function openChat(){$("#chat").hidden=false;$("#launcher").hidden=true;$("#launcher").style.display="none";$("#launcher").setAttribute("aria-expanded","true");if(innerWidth>600)$("#message").focus()}
function closeChat(){$("#chat").hidden=true;$("#launcher").hidden=false;$("#launcher").style.display="flex";$("#launcher").setAttribute("aria-expanded","false");$("#launcher").focus()}
$("#launcher").onclick=openChat;$("#open-advisor").onclick=openChat;$("#close-chat").onclick=closeChat;
document.addEventListener("keydown",e=>{if(e.key==="Escape"&&!$("#chat").hidden)closeChat()});
for(const button of document.querySelectorAll("[data-question]"))button.onclick=()=>{openChat();send(button.dataset.question)};
$("#cart-nav").onclick=()=>{if(cartUrl)window.open(cartUrl,"_blank","noopener,noreferrer");else{openChat();renderMessage({role:"assistant",text:"Ссылка на корзину появится после подтверждения покупки в чате."})}};
if(cartUrl)$("#cart-count").textContent="✓";
function showError(error){add({role:"assistant",text:error?.error?.message||"Не удалось связаться с консультантом. Проверьте соединение и попробуйте ещё раз.",error:true})}
async function send(text){
 text=text.trim();if(!text||busy)return;
 if(paymentData(text)){$("#message").value="";renderMessage({role:"assistant",text:"Не отправляйте платёжные реквизиты. Сообщение не сохранено и не отправлено. Удалите эти данные и повторите вопрос.",error:true});return}
 busy=true;
 const previous=history.map(({role,text})=>({role,text})).slice(-30);
 add({role:"user",text});$("#message").value="";$("#message").disabled=true;$("#send").disabled=true;
 document.querySelectorAll("[data-question]").forEach(b=>b.disabled=true);
 const typing=document.createElement("div");typing.className="typing";typing.textContent="Консультант печатает…";$("#messages").append(typing);typing.scrollIntoView({block:"nearest"});
 const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),30000);
 try{
  if(config.preview)throw {error:{code:"preview_only",message:"Это опубликованный интерфейс прототипа. Для ИИ-диалога запустите проект из архива командой docker compose up --build и задайте LLM_API_KEY в .env. Серверы каталога и ассистента здесь не размещены."}};
  const response=await fetch(config.assistantUrl.replace(/\/$/,"")+"/assistant/message",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({session_id:sessionId,text,history:previous}),signal:controller.signal});
  const result=await response.json();if(!response.ok||result.error)throw result;
  if(typeof result.reply_text!=="string")throw new Error("Invalid response");
  if(result.cart_url&&validUrl(result.cart_url)){cartUrl=validUrl(result.cart_url);$("#cart-count").textContent="✓"}
  add({role:"assistant",text:result.reply_text,confirm:result.needs_confirmation===true,cartUrl:validUrl(result.cart_url)});
 }catch(error){showError(error)}finally{clearTimeout(timer);typing.remove();busy=false;$("#message").disabled=false;$("#send").disabled=false;document.querySelectorAll("[data-question]").forEach(b=>b.disabled=false);if(innerWidth>600)$("#message").focus()}
}
$("#chat-form").onsubmit=e=>{e.preventDefault();send($("#message").value)};
$("#message").addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey&&!e.isComposing){e.preventDefault();send(e.target.value)}});
function resize(){if(window.visualViewport)document.documentElement.style.setProperty("--chat-height",window.visualViewport.height+"px")}
window.visualViewport?.addEventListener("resize",resize);resize();
