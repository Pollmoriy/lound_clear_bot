# Loud & Clear — Telegram-бот регистрации на встречи

Бот: список мероприятий (с фото, если есть) → регистрация → подтверждение / лист ожидания.
`/admin` — участники, лист ожидания, экспорт CSV, изменить вместимость, закрыть мероприятие.
Плюс напоминание о встрече (см. про деплой ниже — на PythonAnywhere оно приходит
раз в сутки, а не точно за 24ч/3ч).

## Стек

- **aiogram 3** — вся логика бота
- **SQLAlchemy** — работает и с SQLite (для локальной разработки), и с Postgres/Supabase (для прода)
- **Два способа получать сообщения от Telegram**, для разных сценариев:
  - `bot.py` — long polling, для локального запуска и разработки (`python bot.py`)
  - `flask_app.py` — webhook через Flask, для деплоя на PythonAnywhere без карты
    (бесплатный тариф не даёт фоновый процесс, зато даёт постоянно работающий сайт)
- **APScheduler** — используется только внутри `bot.py` при локальном запуске;
  на PythonAnywhere вместо него — отдельный скрипт `send_reminders.py` по расписанию

## 1. Бот в BotFather

1. @BotFather → `/newbot` → получи `BOT_TOKEN`
2. `/setdescription` — текст, который человек видит в пустом чате с ботом до /start:
   > Бот Loud & Clear — регистрация на встречи speaking club в Минске. Жми /start, выбирай мероприятие и записывайся в пару кликов 🗣
3. `/setabouttext` — короткое описание в профиле бота (до ~120 символов):
   > Регистрация на встречи Loud & Clear — English speaking club в Минске 🗣

## 2. Свой Telegram ID

@userinfobot → /start → скопируй число → впиши в `.env` как `ADMIN_IDS`
(несколько админов — через запятую: `ADMIN_IDS=111,222`).

## 3. Запуск локально

```bash
pip install -r requirements.txt
cp .env.example .env
# впиши BOT_TOKEN и ADMIN_IDS
python bot.py
```

В Telegram (от админского аккаунта):
- `/new_event` — название → дата (строго формат `27.09.2026 18:00`) → место → кол-во мест →
  фото (или `/skip`)
- `/admin` — управление, в тексте будет показан **ID мероприятия** — он нужен для кнопки в канале
- `/export` (кнопка "Экспорт списка" в /admin) — присылает CSV с участниками

От любого аккаунта:
- `/start` — список мероприятий
- `/cancel` — отменить свою регистрацию

## 4. Кнопка "Зарегистрироваться" в посте канала

Важный момент про Telegram: если ты обычным способом (через приложение) публикуешь пост
в канале, **прикрепить к нему настоящую inline-кнопку с логикой нельзя** — такие кнопки
может добавлять только сам бот, когда постит сообщение через Bot API.

Решение, которое работает без лишних сложностей — **deep link**: обычная кликабельная
ссылка в тексте поста, которая открывает бота сразу на нужном мероприятии.

1. Создай мероприятие через `/new_event`, бот покажет его **ID** (например `3`)
2. В посте канала выдели текст (например "🎟 Зарегистрироваться") → добавить ссылку →
   вставь:
   ```
   https://t.me/loudandclear_minsk_bot?start=event_3
   ```
   (замени `loudandclear_minsk_bot` на реальный username твоего бота, `3` — на ID мероприятия)
3. Человек жмёт на ссылку → у него открывается бот → сразу видит карточку этого
   мероприятия с фото и кнопкой регистрации

Работает в любом Telegram-клиенте, не требует делать бота админом канала.

## 5. База данных: переезд на Supabase

Бесплатный Web Service на Render не хранит файлы между перезапусками — SQLite-файл
обнулится при редеплое. Для прода нужна внешняя база. Supabase подходит и даёт
постоянный бесплатный тариф.

**Важный нюанс**, который легко пропустить: Supabase Direct connection по умолчанию
работает только по IPv6, а большинство бесплатных хостов (включая Render) — IPv4-only.
Поэтому нужно брать не "Direct connection", а **Supavisor Session pooler**:

1. Supabase Dashboard → твой проект → Connect (кнопка сверху)
2. Выбери **Session pooler** (не Direct connection, не Transaction pooler)
3. Скопируй строку — она выглядит примерно так:
   ```
   postgresql://postgres.abcxyzproject:[YOUR-PASSWORD]@aws-0-eu-central-1.pooler.supabase.com:5432/postgres
   ```
4. В `.env` вставь как `DATABASE_URL`, только поменяй префикс `postgresql://` на
   `postgresql+asyncpg://` (это нужно для нашего асинхронного драйвера):
   ```
   DATABASE_URL=postgresql+asyncpg://postgres.abcxyzproject:[YOUR-PASSWORD]@aws-0-eu-central-1.pooler.supabase.com:5432/postgres
   ```

Код менять не нужно — `asyncpg` уже в requirements.txt, SSL для Postgres бот включает
автоматически.

## 6. Деплой на PythonAnywhere (без карты, webhook-режим)

Бесплатный тариф PythonAnywhere не даёт фоновый процесс (как Render Background
Worker), зато даёт постоянно работающий сайт — поэтому бот здесь работает
не через long polling (`bot.py`), а через **webhook** (`flask_app.py`):
Telegram сам присылает сообщения на наш адрес, вместо того чтобы бот сам их
запрашивал. Вся логика (регистрация, отмена, админка) — та же самая, просто
другой способ получения сообщений.

**Важное ограничение**, которое стоит знать заранее: на бесплатном тарифе
нет постоянно тикающего таймера, поэтому вместо точных напоминаний "за 24ч
и за 3ч" здесь — одно напоминание, отправляемое **раз в сутки** через
PythonAnywhere Scheduled Task (бесплатно, 1 задача в день). Этого достаточно
для "напомнить за день до встречи".

### Шаг 1. Собери код на GitHub (если ещё не делала)

```bash
git init
git add .
git commit -m "loud clear bot"
```
Дальше — создай пустой репозиторий на github.com и следуй подсказкам для
`git remote add origin` и `git push`.

### Шаг 2. Регистрация на PythonAnywhere

pythonanywhere.com → Pricing → **Create a Beginner account** (бесплатно, без
карты).

### Шаг 3. Залей код

Проще всего через встроенную консоль. В PythonAnywhere: Dashboard → **Consoles**
→ **Bash**. Там:
```bash
git clone https://github.com/твой-аккаунт/твой-репозиторий.git loud_clear_bot
cd loud_clear_bot
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
(если Python 3.10 недоступен — посмотри, какие версии предлагает `mkvirtualenv`,
подойдёт любая 3.10+）

### Шаг 4. Создай `.env` прямо на сервере

В той же Bash-консоли:
```bash
nano .env
```
Вставь туда переменные как в `.env.example`, заполнив реальными значениями:
`BOT_TOKEN`, `ADMIN_IDS`, `DATABASE_URL` (строка Supabase), `WEBHOOK_SECRET`
(придумай длинную случайную строку), `PA_USERNAME` (твой логин на
PythonAnywhere), и обязательно:
```
PA_PROXY_URL=http://proxy.server:3128
```
Сохрани: Ctrl+O, Enter, Ctrl+X.

### Шаг 5. Создай веб-приложение

Dashboard → **Web** → **Add a new web app** → **Manual configuration** →
выбери ту же версию Python, что и в virtualenv.

- **Virtualenv**: укажи путь `/home/твой_username/loud_clear_bot/venv`
- **WSGI configuration file** — открой его (ссылка прямо на странице Web) и
  замени всё содержимое на:
  ```python
  import sys

  path = '/home/твой_username/loud_clear_bot'
  if path not in sys.path:
      sys.path.append(path)

  from flask_app import app as application
  ```
  (замени `твой_username` на реальный логин)
- Нажми зелёную кнопку **Reload**

### Шаг 6. Зарегистрируй webhook у Telegram

Это делается **с твоего компьютера**, не на PythonAnywhere. В `.env` на
своём компьютере (не забудь: там тоже должны быть `PA_USERNAME` и тот же
`WEBHOOK_SECRET`, что и на сервере) запусти:
```bash
python set_webhook.py
```
Должно вывести `Webhook установлен на: https://...` — значит готово.
Напиши боту `/start` в Telegram — должен ответить мгновенно.

### Шаг 7. Напоминание за день — Scheduled Task

Dashboard → **Tasks** → добавь ежедневную задачу (бесплатно даётся одна),
время — на твой вкус (например 10:00), команда:
```
python3.10 /home/твой_username/loud_clear_bot/send_reminders.py
```

### Если что-то не работает

- Ошибка про недоступную сеть / proxy — проверь, что `PA_PROXY_URL=http://proxy.server:3128`
  прописан в `.env` на сервере
- Бот не отвечает — Dashboard → Web → **Log files** → error log, там будет
  видна причина
- После любого изменения кода на сервере (`git pull`) — не забывай нажимать
  **Reload** на странице Web
