# Marketing Budget Tennisi Bot

Telegram бот для управления бюджетом.

## Описание

Бот отправляет запросы на валидацию счетов и добавляет расходы в
Google Sheet таблицу "Бюджет маркетинг RU внутренне пользование"

## Команды

- `/enter_record`: Запустить ввод данных о счете
- `/stop`: Прервать ввод информации о счете
- `/show_not_paid`: Просмотреть все неоплаченные счета
- `/reject_record`: Ввести ID счета для отклонения платежа
- `/approve_record`: Ввести ID счета для подтверждения платежа

## Установка

Для запуска бота выполните следующие шаги:

1. Создайте файл ./data/credentials.json с данными сервисного аккаунта Google

2. Создайте файл ./config/.env со следующими переменными:
   TELEGRAM_BOT_TOKEN=ваш-токен-бота
   GOOGLE_SHEETS_SPREADSHEET_ID=spreadsheet_id
   DATABASE_PATH=./approvals.db
   GOOGLE_SHEETS_CREDENTIALS_FILE=./data/credentials.json
   GOOGLE_SHEETS_CATEGORIES_SHEET_ID=sheet_id-листа-категорий
   GOOGLE_SHEETS_RECORDS_SHEET_ID=sheet_id-листа-счетов
   INITIATORS_CHAT_IDS=chat_ids-инициаторов
   HEAD_CHAT_IDS=chat_id-главы-департамента
   FINANCE_CHAT_IDS=chat_ids-финансового-отдела
   PAYERS_CHAT_IDS=chat_ids-плательщиков
   DEVELOPER_CHAT_ID=chat_ids-разработчика
   WHITE_LIST=chat_ids-пользователей

3. Соберите Docker-образ командой: `docker-compose up -d`

Отправьте боту(https://t.me/marketing_budget_tennisi_bot) команду /start через Telegram для начала взаимодействия.

Copyright [2024] [Tennisi]. Все права защищены.

Автор: Иван Шелухин