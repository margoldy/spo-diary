# Фронтенд

Vue 3, Vite. Node.js 22.12+.

Из `client`:

```powershell
npm install
npm run dev
```

Адрес: http://127.0.0.1:5173. Бэкенд: http://127.0.0.1:8000. Запросы `/api` проксируются через Vite.

Бэкенд запускается отдельно по [инструкции](../server/README.md).

В PyCharm: конфигурация `Фронтенд` запускает Vite; `Фронтенд + бэкенд` одновременно запускает Vite и бэкенд с обработчиком отзывов. Корень проекта: `проект`.

```powershell
npm run build
npm run preview
```

Сборка: `dist`. На сервере `/api` направляется в бэкенд, остальные маршруты в `index.html`.

Проверки:

Требуется PostgreSQL с правом создания БД. Тесты используют отдельную `spo_diary_ui_test`, письма не отправляются. Порт 8000 должен быть свободен.

```powershell
npx playwright install chromium
npm test
```
