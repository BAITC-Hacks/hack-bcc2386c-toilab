# Catalog Service · 8001

Запуск из корня проекта после установки requirements: `uvicorn catalog.api:app --app-dir catalog-service --port 8001`.
Для production Docker запускает один worker; локальный `.env` автоматически не читается. Передайте переменные через окружение либо используйте корневой Compose.

## Настройки

| Переменная | Назначение / default |
|---|---|
| CATALOG_MODE | demo либо live; default demo |
| CATALOG_DB | путь к SQLite, data/catalog.sqlite |
| PARTNER_API_URL | https://ekt.kz/api |
| PARTNER_API_USER, PARTNER_API_PASSWORD | Basic Auth, только через env |
| SYNC_INTERVAL | 300 секунд после окончания предыдущего sync |
| PUBLIC_CATALOG_URL | адрес браузерной корзины, http://localhost:8001 |
| INTERNAL_API_TOKEN | общий секрет для POST /cart/add; пустой только для localhost demo |

Маршруты → CatalogService → Store. Adapter — единственное место с внешними полями. Совпадение specs аналогов — точное по паре ключ/значение в той же category; сортировка по числу совпадений, затем id. Нулевой stock аналога не скрывается в Catalog: Assistant рекомендует только доступные позиции.

POST /cart/add устанавливает абсолютное qty позиции (идемпотентность), не увеличивает его. confirmed=false, отсутствующий товар и превышение остатков не меняют корзину. Строгая валидация на границе. Проверка и запись под единым lock.

Синхронизация в фоне, 3 попытки/5 секунд на HTTP, backoff. Только полный успешный результат атомарно заменяет кэш. JSON-логи: catalog_synced, partner_request_failed, catalog_stale_cache, cart_refused с reason. Исходные заголовки/ответы и Basic Auth не логируются.

Ограничения: схема ekt.kz требует сверки с реальным payload; число страниц ограничено 500; detail-запросы последовательные; нет резерва склада, привязки корзины к пользователю, записи в реальную корзину ekt.kz и cleanup корзин. В production: Postgres/Redis, auth, мониторинг возраста кэша, согласованный write API и TTL. Экранирование HTML корзины включено.

Тесты из корня: `python run_tests.py`.
