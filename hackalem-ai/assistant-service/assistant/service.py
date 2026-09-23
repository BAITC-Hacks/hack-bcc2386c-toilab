import asyncio
import json
import os
import time
from pathlib import Path
from pydantic import ValidationError
from .models import Action, SearchArgs, ProductArgs, AnalogArgs
from .catalog_client import CatalogUnavailable
from .llm import LLMUnavailable
from .privacy import contains_payment_data

SCHEMAS={"search_catalog":SearchArgs,"get_product":ProductArgs,"get_analogs":AnalogArgs,"propose_add_to_cart":Action}
TOOLS=[{"type":"function","function":{"name":name,"description":description,"parameters":SCHEMAS[name].model_json_schema()}} for name,description in [
    ("search_catalog","Search authoritative catalog by name or SKU."),
    ("get_product","Get current item details by product_id."),
    ("get_analogs","Get same-category analogs ranked by matching specifications."),
    ("propose_add_to_cart","Propose exact quantity for subsequent confirmation. Does NOT mutate cart.")]]

def may_execute(pending,decision,age):
    """Fail closed. Only a server-owned, unexpired identical proposal is eligible."""
    return bool(pending and age<=300 and decision.confirmed is True and
                decision.injection_detected is False and
                decision.product_id==pending.product_id and decision.qty==pending.qty)

def answer(text,action=None,url=None):
    return {"reply_text":text,"proposed_action":action.model_dump() if action else None,"needs_confirmation":action is not None,"cart_url":url}

class AssistantService:
    def __init__(self,catalog,llm,sessions):
        self.catalog,self.llm,self.sessions=catalog,llm,sessions
        self.prompt=(Path(__file__).parent.parent/"prompts/system.md").read_text(encoding="utf-8")
    async def message(self,request):
        session=self.sessions.get(request.session_id)
        async with session.lock:
            if contains_payment_data(request.text):
                session.pending=None
                return answer("Не отправляйте платёжные реквизиты. Сообщение не сохранено и не передано модели. Задайте вопрос о товаре без этих данных.")
            try:
                async with asyncio.timeout(float(os.getenv("ASSISTANT_TURN_TIMEOUT","25"))):
                    result=await self._turn(request,session)
            except LLMUnavailable as exc:
                session.pending=None
                if str(exc)=="local_model_unavailable":
                    result=answer("Локальная ИИ-модель не ответила. Убедитесь, что Ollama работает. Первый ответ может занять больше времени. Если подтверждали покупку, проверьте корзину перед повтором.")
                else:
                    result=answer("ИИ не подключён. Запустите START_LOCAL_AI.cmd для работы без API-ключа либо настройте ключ провайдера.")
            except (CatalogUnavailable,ValidationError,ValueError,KeyError,TypeError,TimeoutError):
                session.pending=None
                result=answer("Сейчас не удаётся получить надёжный ответ от каталога или ИИ. Попробуйте ещё раз чуть позже. Если вы подтверждали покупку, проверьте корзину: ответ мог потеряться.")
            session.history.extend([{"role":"user","content":request.text},{"role":"assistant","content":result["reply_text"]}])
            session.history=session.history[-30:]
            return result
    async def _turn(self,request,session):
        previous=session.pending
        age=time.monotonic()-session.pending_at
        # Consume even on refusal/error. An intervening message invalidates the offer.
        session.pending=None
        if previous and age<=300:
            decision=await self.llm.classify(request.text,previous)
            if may_execute(previous,decision,time.monotonic()-session.pending_at):
                result=await self.catalog.add(request.session_id,previous)
                if result.get("success") is True:
                    return answer("Товар добавлен в корзину: "+str(previous.qty)+" шт. Проверьте выбранные позиции перед оформлением.",url=result["cart"]["cart_url"])
                return answer(result.get("error",{}).get("message","Не удалось добавить товар. Повторите выбор."))
            if decision.injection_detected:
                return answer("Для покупки нужно выбрать конкретный товар и количество, затем отдельно подтвердить предложение.")
        # Client history is intentionally never trusted for state or model instructions.
        messages=[{"role":"system","content":self.prompt}]+session.history+[{"role":"user","content":request.text}]
        proposed=None;offered_item=None;warnings=set()
        for _ in range(6):
            message=await self.llm.complete(messages,TOOLS)
            messages.append(message)
            calls=message.get("tool_calls") or []
            if not calls:
                text=message.get("content") or "Уточните название или артикул товара."
                if warnings:
                    text+="\n\n"+"\n".join(sorted(warnings))
                if proposed:
                    # Fixed server-authored offer binds visible text to the stored action.
                    text+=f"\n\nДобавить «{offered_item['name']}» ({offered_item['sku']}), {proposed.qty} шт. по {offered_item['price']:g} ₸? Подтвердите отдельным сообщением. Это установит указанное количество в корзине."
                    session.pending=proposed;session.pending_at=time.monotonic()
                return answer(text,proposed)
            if len(calls)>4:
                raise ValueError("Too many tools")
            for call in calls:
                name=call["function"]["name"]
                try:
                    model=SCHEMAS[name].model_validate_json(call["function"]["arguments"])
                    if name=="search_catalog":
                        result=await self.catalog.search(model.q,model.limit)
                    elif name=="get_product":
                        result=await self.catalog.product(model.product_id)
                    elif name=="get_analogs":
                        result=await self.catalog.analogs(model.product_id,model.limit)
                    else:
                        item=await self.catalog.product(model.product_id)
                        if "error" in item or item["stock"]<model.qty:
                            result={"error":{"code":"unavailable","message":"Товар или нужное количество недоступны."}}
                        elif proposed is not None:
                            result={"error":{"code":"one_offer_only","message":"Можно предложить одну позицию за ход."}}
                        else:
                            proposed=model;offered_item=item
                            result={"proposal":model.model_dump(),"item":item,"requires_next_message_confirmation":True}
                    # Enforce analog lookup even if the model forgets its prompt.
                    originals=result.get("items",[]) if isinstance(result,dict) else []
                    if isinstance(result,dict) and "stock" in result:
                        originals=[result]
                    for source_item in originals:
                        warning=source_item.get("specs",{}).get("Предупреждение")
                        if warning:
                            warnings.add(warning)
                    if name in ("search_catalog","get_product"):
                        missing=[p for p in originals if p.get("stock")==0]
                        if missing:
                            result={"result":result,"required_analogs":[{"original_id":p["id"],"analogs":await self.catalog.analogs(p["id"],5)} for p in missing[:5]]}
                except (ValidationError,KeyError,json.JSONDecodeError):
                    result={"error":{"code":"invalid_tool_arguments","message":"Исправьте аргументы инструмента."}}
                messages.append({"role":"tool","tool_call_id":call["id"],"content":json.dumps(result,ensure_ascii=False)})
        raise ValueError("Tool budget exhausted")
