# Rental Bot

Telegram-бот для автоматизации учёта показаний счётчиков и оплаты аренды.

## Возможности

**Для арендаторов:**
- `/start` — регистрация, показ Telegram ID
- `/readings` — сдача показаний счётчиков
- `/status` — просмотр неоплаченных счетов
- Отправка фото чека для подтверждения оплаты

**Для арендодателя:**
- `/all_status` — статус всех арендаторов
- `/unpaid` — список должников
- `/remind <id>` — отправить напоминание арендатору
- `/remind_all` — напомнить всем

**Автоматически:**
- 25 и 28 числа — напоминание о сдаче показаний
- 1 и 5 числа — напоминание об оплате

## Настройка

### 1. Создать Telegram бота

1. Написать [@BotFather](https://t.me/BotFather) в Telegram
2. Отправить `/newbot`, следовать инструкциям
3. Сохранить токен бота

### 2. Настроить Google Sheets

1. Создать новую таблицу в Google Sheets
2. Создать листы с заголовками:

**Лист "Арендаторы":**
| telegram_id | Имя | Помещение | is_owner |
|-------------|-----|-----------|----------|

**Лист "Счётчики":**
| telegram_id | Название счётчика | Тип | Тариф | Единица |
|-------------|-------------------|-----|-------|---------|

**Лист "Показания":**
| Дата | telegram_id | Счётчик | Пред. показание | Тек. показание | Расход | Сумма | Оплачено | Ссылка на чек |
|------|-------------|---------|-----------------|----------------|--------|-------|----------|---------------|

**Лист "Настройки":**
| Ключ | Значение |
|------|----------|
| payment_details | Сбербанк 1234 5678 9012 3456 |

3. Создать Service Account в Google Cloud Console:
   - Перейти на https://console.cloud.google.com
   - Создать проект или выбрать существующий
   - APIs & Services → Enable APIs → Google Sheets API
   - IAM & Admin → Service Accounts → Create
   - Создать ключ (JSON)

4. Расшарить таблицу на email сервисного аккаунта (Editor)

### 3. Настроить Cloudflare R2

1. Зайти в Cloudflare Dashboard → R2
2. Создать bucket (например: `rental-receipts`)
3. Manage R2 API Tokens → Create API Token
4. Сохранить Access Key ID и Secret Access Key

### 4. Переменные окружения

```env
TELEGRAM_BOT_TOKEN=...
GOOGLE_SHEETS_ID=...
GOOGLE_SERVICE_ACCOUNT_JSON={"type": "service_account", ...}
R2_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=rental-receipts
OWNER_TELEGRAM_ID=...
```

### 5. Запуск

**Локально:**
```bash
pip install -r requirements.txt
python -m src.main
```

**Docker:**
```bash
docker build -t rental-bot .
docker run --env-file .env rental-bot
```

**Railway:**
1. Push код в GitHub
2. Создать новый проект на Railway
3. Подключить репозиторий
4. Добавить переменные окружения
5. Deploy

## Добавление арендатора

1. Арендатор пишет боту `/start`
2. Бот показывает его Telegram ID
3. Арендодатель добавляет ID в таблицу "Арендаторы"
4. Арендодатель добавляет счётчики в таблицу "Счётчики"
5. Арендатор теперь может сдавать показания

## Структура проекта

```
src/
├── main.py           # Точка входа
├── config.py         # Конфигурация
├── bot/
│   ├── handlers/
│   │   ├── common.py   # /start, /help
│   │   ├── tenant.py   # Команды арендаторов
│   │   └── owner.py    # Команды арендодателя
│   ├── keyboards.py    # Inline-кнопки
│   └── states.py       # FSM состояния
└── services/
    ├── sheets.py       # Google Sheets API
    ├── storage.py      # Cloudflare R2
    └── scheduler.py    # Автонапоминания
```
