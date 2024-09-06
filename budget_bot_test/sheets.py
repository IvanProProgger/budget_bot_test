from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

import gspread_asyncio
import pandas as pd
import pytz

from google.oauth2.service_account import Credentials

from config.config import Config
from config.logging_config import logger

date_format = {  # паттерн для преобразования числа даты в необходимый формат
    "numberFormat": {"type": "DATE", "pattern": "dd.mm.yyyy"}
}

currency_format = {  # паттерн для преобразования числа суммы в рубли
    "numberFormat": {"type": "CURRENCY", "pattern": "₽ #,###.0000000000"}
}


async def get_today_moscow_time() -> str:
    """Функция для получения текущей даты"""

    moscow_tz = pytz.timezone("Europe/Moscow")
    today = datetime.now(moscow_tz)
    formatted_date = today.strftime("%d.%m.%Y")
    return formatted_date


async def add_record_to_google_sheet(record: dict) -> None:
    """Функция для добавления строки в таблицу Google Sheet."""
    manager = GoogleSheetsManager()
    await manager.initialize_google_sheets()
    await manager.add_payment_to_sheet(record)


def get_credentials() -> Credentials:
    """Функция для получения данных для авторизации в Google Sheets"""

    creds = Credentials.from_service_account_file(Config.google_sheets_credentials_file)
    scoped = creds.with_scopes(
        [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
    )
    return scoped


class GoogleSheetsManager:
    """Класс для обработки Google Sheets таблиц."""

    def __init__(self):
        self.sheets_spreadsheet_id = Config.google_sheets_spreadsheet_id
        self.records_sheet_id = Config.google_sheets_records_sheet_id
        self.categories_sheet_id = Config.google_sheets_categories_sheet_id
        self.options_dict = None
        self.items = None
        self.agc = None

    async def initialize_google_sheets(self) -> gspread_asyncio.AsyncioGspreadClient:
        """Инициализация в Google Sheets"""

        try:
            agcm = gspread_asyncio.AsyncioGspreadClientManager(get_credentials)
            self.agc = await agcm.authorize()
            return self.agc
        except Exception as e:
            raise RuntimeError(f"Не удалось авторизоваться в сервисе Google Sheet. Ошибка: {e}")

    async def add_payment_to_sheet(self, payment_info: dict[str, str]) -> None:
        """Добавление счёта в таблицу"""

        try:
            spreadsheet = await self.agc.open_by_key(self.sheets_spreadsheet_id)
            worksheet = await spreadsheet.get_worksheet_by_id(0)
            logger.info(f"Открытие листа: {self.sheets_spreadsheet_id}")

        except Exception as e:
            raise RuntimeError(f"Ошибка при открытии или доступе к листу: {e}")

        today_date = await get_today_moscow_time()
        period = payment_info["period"].split(" ")
        months = [
            datetime.strptime(f"01.{a}", "%d.%m.%y").strftime("%d.%m.%Y")
            for a in period
        ]
        total_sum = Decimal(payment_info["amount"]) / Decimal(len(months))
        rounded_sum = float(total_sum.quantize(Decimal('0.0000000001'), rounding=ROUND_HALF_UP))
        for month in months:
            row_data = [
                today_date,
                rounded_sum,
                payment_info["expense_item"],
                payment_info["expense_group"],
                payment_info["partner"],
                payment_info["comment"],
                month,
                payment_info["payment_method"],
            ]
            await worksheet.append_row(row_data, value_input_option="USER_ENTERED")
            logger.info(f"Добавлена строка: {row_data}")
        await worksheet.format("A3:A", date_format)
        await worksheet.format("B3:B", currency_format)
        await worksheet.format("G3:G", date_format)

    async def get_data(self) -> tuple[dict[str, dict[str, list[str]]], list[str]]:
        """
        Получение списка статей и списка словарей данных из таблицы "категории"
        """

        try:
            spreadsheet = await self.agc.open_by_key(self.sheets_spreadsheet_id)
            worksheet = await spreadsheet.get_worksheet_by_id(self.categories_sheet_id)
        except Exception as e:
            raise RuntimeError(f'Ошибка получения данных с листа "категории". Ошибка: {e}')

        df = pd.DataFrame(await worksheet.get_all_records())
        unique_items = df["Статья"].unique()
        data_structure = {}

        for _, row in df.iterrows():
            category = row["Статья"]
            group = row["Группа"]
            partner = row["Партнер"]

            if category not in data_structure:
                data_structure[category] = {}

            if group not in data_structure[category]:
                data_structure[category][group] = []

            data_structure[category][group].append(partner)

        self.options_dict, self.items = data_structure, unique_items

        return data_structure, unique_items
