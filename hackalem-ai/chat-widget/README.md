# Chat Widget · 3000

Запуск: `python chat-widget/server.py` из корня. Зависимости — стандартная библиотека Python. Docker аналогичен.

`ASSISTANT_SERVICE_URL=http://localhost:8002` — **браузерный** адрес Assistant. В Docker нельзя ставить сюда внутреннее имя assistant-service: браузер его не разрешит. Сервер отдаёт публичный config.js без секретов. Не помещайте LLM/API-ключи в frontend env.

Откройте http://localhost:3000. Плавающая кнопка, быстрые вопросы, отправка Enter (Shift+Enter — новая строка), ожидание с disabled-инпутом, сообщения об ошибках, выделение предложения, явная ссылка на корзину. Ответы выводятся textContent, а не innerHTML. Ссылки принимают только http/https, открываются с noopener. Виджет делает только POST /assistant/message. Health напрямую не вызывается.

UUID v4 и последние 40 сообщений хранятся в localStorage. Сбой/quota localStorage не ломает текущую сессию. Серверная история после перезапуска не восстанавливается из браузера. Варианты доверенного состояния и подтверждения принадлежат Assistant.

Мобильная высота использует visualViewport + 100dvh для виртуальной клавиатуры. Есть aria-label, live log, keyboard/focus states, reduced motion, системный font fallback. Карточки — явно обозначенные synthetic fixtures с заглушками изображений по заданию. Их кнопки задают вопрос в чат, не меняют корзину.

Ограничения: нет вложений/авторизации; нет реальных товарных фото и live-витрины. Статическая публикация dist — просмотр интерфейса, при попытке диалога объясняет локальный запуск. Для production: CDN/reverse proxy вместо Python SimpleHTTPServer, CSP, Same-Origin gateway, signed consent UI, политика удаления localStorage.

Локальный launcher задаёт CHAT_TIMEOUT_MS=315000 и LLM_PROVIDER=ollama: браузер дольше ждёт ответ и показывает локальный режим. WIDGET_HOST по умолчанию 127.0.0.1; Compose явно задаёт 0.0.0.0 внутри контейнера.
