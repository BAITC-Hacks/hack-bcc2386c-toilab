# Assistant Service · 8002

Запуск: `uvicorn assistant.api:app --app-dir assistant-service --port 8002` из корня после установки requirements. Env передаются оболочкой или Compose; `.env.example` — только шаблон.

| Env | Значение |
|---|---|
| CATALOG_SERVICE_URL | http://localhost:8001 локально; http://catalog-service:8001 в Compose |
| INTERNAL_API_TOKEN | тот же секрет, что у Catalog |
| LLM_BASE_URL | Chat Completions-совместимая база, default https://api.openai.com/v1 |
| LLM_MODEL | default gpt-4.1-mini, поддержка tools + JSON Schema обязательна |
| LLM_API_KEY | секрет провайдера; без него возвращается честная ошибка |
| CORS_ORIGINS | список разрешённых origin через запятую |

`prompts/system.md` содержит правила grounded-ответов, аналогов, покупки и prompt injection. `LLM.complete` выполняет реальный HTTP-запрос. Модель имеет search_catalog, get_product, get_analogs, propose_add_to_cart. POST /cart/add не является tool.

`may_execute` — отдельный тестируемый guardrail. Сервер хранит Action и timestamp, классификатор модели принимает только текущий текст и предложение. Модель не может заменить server-side Action. Следующий ход потребляет предложение даже при отказе или ошибке; срок 5 минут. History клиента не доверяется. Locks сериализуют запросы одной сессии. Replay подтверждения сам по себе не повторяет покупку.

MemorySessions реализует SessionRepository; TTL 1 час, лимит 5000, максимум 30 сообщений server-side. Замена для production: persistent repository + распределённый lock; при нескольких workers текущая реализация не подходит. Timeout Catalog 3 секунды, LLM 12, общий ход 25. Любая зависимость может отказать без остановки процесса. Health проверяет доступность Catalog, но не доступность/ключ LLM.

Ограничения: вероятностный классификатор требует eval реальным провайдером; не считать scripted unit tests доказательством неуязвимости. Для сильного consent нужны подписанные challenges и явное UI-подтверждение. Добавить rate limiting, аутентификацию, защиту чувствительного текста и наблюдаемость без PII. Вложения не входят в контракт.

Тесты: `python run_tests.py` из корня.

## Локальная модель без ключа

Новый `LLM_PROVIDER=ollama` использует native `/api/chat` и `OLLAMA_URL`. `ollama_adapter.py` преобразует историю tool calls, объекты аргументов и результаты инструментов. Для классификации передаётся JSON Schema Decision через format. `think=false`, `stream=false`. Обрезанные и ошибочные ответы отклоняются, модель не подменяется заглушкой. Ключ не используется.

Запуск Windows — корневой START_LOCAL_AI.cmd. Переменные LLM_TIMEOUT и ASSISTANT_TURN_TIMEOUT позволяют ждать локальную модель дольше. При отсутствии провайдера LLM_PROVIDER по умолчанию openai; старый облачный режим сохранён. Health по контракту по-прежнему отражает только Catalog, готовность Ollama проверяется launcher до открытия браузера.
