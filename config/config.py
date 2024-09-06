from os import getenv
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Класс-конфиг для проекта"""

    telegram_bot_token: str = getenv("TELEGRAM_BOT_TOKEN")
    google_sheets_spreadsheet_id: str = getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
    database_path: str = getenv("DATABASE_PATH")
    google_sheets_credentials_file: str = getenv("GOOGLE_SHEETS_CREDENTIALS_FILE")
    google_sheets_categories_sheet_id: int = getenv("GOOGLE_SHEETS_CATEGORIES_SHEET_ID")
    google_sheets_records_sheet_id: int = getenv("GOOGLE_SHEETS_RECORDS_SHEET_ID")
    head_chat_ids: list[int] = list(map(int, getenv("HEAD_CHAT_IDS").split(",")))
    finance_chat_ids: list[int] = list(map(int, getenv("FINANCE_CHAT_IDS").split(",")))
    payers_chat_ids: list[int] = list(map(int, getenv("PAYERS_CHAT_IDS").split(",")))
    developer_chat_id: list[int] = getenv("DEVELOPER_CHAT_ID")
    white_list: set[int] = set(map(int, getenv("WHITE_LIST").split(",")))