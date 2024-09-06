import re
import textwrap
from datetime import datetime

from google.api_core.exceptions import NotFound
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config.config import Config
from config.logging_config import logger
from db import db
from budget_bot_test.sheets import add_record_to_google_sheet


async def chat_ids_department(department: str) -> list[int]:
    """Возвращяет chat_id для подгрупп"""

    chat_ids = {
        "head": Config.head_chat_ids,
        "finance": Config.finance_chat_ids,
        "payers": Config.payers_chat_ids,
        "all": Config.head_chat_ids
               + Config.finance_chat_ids
               + Config.payers_chat_ids,
    }
    return chat_ids[department]


async def check_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in Config.white_list:
        await update.message.reply_text("Извините, у вас нет доступа к этому боту.")
        logger.warning("В бота пытаются зайти посторонние...")
        return


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""

    await update.message.reply_text(
        f"<b>Бот по автоматизации заполнения бюджета</b>\n\n"
        "<i>Отправьте команду /enter_record и укажите:</i>\n"
        "<i>1)Сумма счёта</i>\n"
        "<i>2)Статья расхода</i>\n"
        "<i>3)Группа расхода</i>\n"
        "<i>4)Партнёр</i>\n"
        "<i>5)Дата оплаты и дата начисления платежа через пробел</i>\n"
        "<i>6)Форма оплаты</i>\n"
        "<i>7)Комментарий к платежу</i>\n"
        "<i>Каждый пункт необходимо указывать строго через запятую.</i>\n\n"
        "<i>Вы можете просмотреть необработанные платежи командой /show_not_paid</i>\n\n"
        "<i>Одобрить заявку можно командой /approve_record указав id платежа</i>\n\n"
        "<i>Отклонить заявку можно командой /reject_record указав id платежа</i>\n\n"
        f"<i>Ваш chat_id - {update.message.chat_id}</i>",
        parse_mode="HTML"
    )


async def submit_record_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик введённого пользователем платежа в соответствии с паттерном:
    1)Сумма счёта: положительное число (возможно с плавающей точкой)
    2)Статья расхода: любая строка из букв и цифр
    3)Группа расхода: любая строка из букв и цифр
    4)Партнёр: любая строка из букв и цифр
    5)Дата: как минимум 2 даты; дата оплаты и дата(ы) начисления платежа
    6)Форма оплаты: любая строка из букв и цифр
    7)Комментарий к платежу: любая строка из букв и цифр
    Добавление платежа в базу данных 'approvals';
    Отправление данных о платеже для одобрения главой отдела.
    """

    initiator_chat_id = update.effective_chat.id
    if not context.args:
        await context.bot.send_message(
            chat_id=initiator_chat_id, text="Необходимо указать данные счёта."
        )
        raise ValueError(f"Необходимо ввести данные о платеже.")

    pattern = (
        r"((?:0|[1-9]\d*)(?:\.\d+)?)\s*;\s*([^;]+)\s*;\s*([^;]+)\s*;\s*([^;]+)\s*;\s*([^;]+)\s*;"
        r"\s*((?:\d{2}\.\d{2}\s*){1,})\s*;\s*([^;]+)$"
    )
    message = " ".join(context.args)
    match = re.match(pattern, message)
    if not match:
        await context.bot.send_message(
            chat_id=initiator_chat_id,
            text="Неверный формат аргументов. Пожалуйста, следуйте указанному формату.\n"
                 "1)Сумма счёта: положительное число (возможно с плавающей точкой)\n"
                 "2)Статья расхода: любая строка из букв и цифр\n"
                 "3)Группа расхода: любая строка из букв и цифр\n"
                 "4)Партнёр: любая строка из букв и цифр\n"
                 "5)Дата: как минимум 2 даты; дата оплаты и дата(ы) начисления платежа\n"
                 "6)Форма оплаты: любая строка из букв и цифр\n"
                 "7)Комментарий к платежу: любая строка из букв и цифр\n"
        )
        return

    try:
        period_dates = match.group(6).split()
        _ = [
            datetime.strptime(date, "%m.%y").strftime("%m.%Y") for date in period_dates
        ]

    except Exception as e:
        await context.bot.send_message(
            chat_id=initiator_chat_id,
            text=f'Ошибка {e}. Введены неверные даты. Даты вводятся в формате mm.yy. '
                 f'строго через пробел(например: "08.22 10.22"). Пожалуйста, следуйте указанному формату.'
        )
        return

    record_dict = {
        "amount": match.group(1),
        "expense_item": match.group(2),
        "expense_group": match.group(3),
        "partner": match.group(4),
        "comment": match.group(5),
        "period": match.group(6),
        "payment_method": match.group(7),
        "approvals_needed": 1 if float(match.group(1)) < 50000 else 2,
        "approvals_received": 0,
        "status": "Not processed",
        "approved_by": None,
        "initiator_id": initiator_chat_id
    }

    try:
        async with db:
            row_id = await db.insert_record(record_dict)
    except Exception as e:
        raise RuntimeError(f"Произошла ошибка при добавлении счёта в базу данных. {e}")

    await create_and_send_approval_message(row_id, record_dict, "head", context=context)


async def create_and_send_approval_message(row_id: str | int, record_dict: dict, department: str,
                                           context: ContextTypes.DEFAULT_TYPE) -> None:
    """Создание кнопок "Одобрить" и "Отклонить", создание и отправка сообщения для одобрения заявки."""

    keyboard = [
        [
            InlineKeyboardButton(
                text="Одобрить",
                callback_data=f"approval_approve_{department}_{row_id}",
            )
        ],
        [
            InlineKeyboardButton(
                text="Отклонить",
                callback_data=f"approval_reject_{department}_{row_id}",
            )
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message_text = (
        f"Пожалуйста, одобрите запрос на платёж {row_id}. \nДанные платежа:\n"
        f'сумма: {record_dict["amount"]}\nстатья: {record_dict["expense_item"]}\n'
        f'группа: {record_dict["expense_group"]}\nпартнер: {record_dict["partner"]}\n'
        f'период начисления: {record_dict["period"]}\nформа оплаты: {record_dict["payment_method"]}\n'
        f'комментарий: {record_dict["comment"]}'
    )

    chat_ids_list = await chat_ids_department(department)
    await send_message_to_chats(chat_ids_list, message_text, context, row_id, department, reply_markup)


async def send_message_to_chats(chat_ids_list: list[int], message_text: str, context: ContextTypes.DEFAULT_TYPE,
                                row_id: int | str, department: str = None, reply_markup: InlineKeyboardMarkup = None):
    """Отправка сообщения в выбранные телеграм-чаты."""

    message_ids = []
    for chat_id in chat_ids_list:
        message = await context.bot.send_message(
            chat_id=chat_id, text=message_text, reply_markup=reply_markup
        )
        message_ids.append(message.message_id)
    context.user_data[f"{row_id}_{department}"] = list(zip(chat_ids_list, message_ids))


async def approval_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик нажатий пользователем кнопок "Одобрить" или "Отклонить."
    """

    try:
        query = update.callback_query
        _, action, department, row_id = query.data.split("_")
        if query.from_user.username:
            approver = "@" + query.from_user.username
        else:
            approver = "@" + str(query.from_user.id)

    except Exception as e:
        raise RuntimeError(f'Ошибка обработки кнопок "Одобрить" и "Отклонить". {e}')

    async with db:
        record = await db.get_row_by_id(row_id)
        initiator_id = record.get("initiator_id")
        amount = record.get("amount")
        if not record:
            raise RuntimeError("Запись в таблице с данным id не найдена.")

    await approval_process(context, update, action, row_id, approver, department, amount, initiator_id)


async def approval_process(context: ContextTypes.DEFAULT_TYPE, update: Update, action: str,
                           row_id: str, approver: str, department: str,
                           amount: float, initiator_id: str | None = None) -> None:
    """Обработчик заявок для одобрения или отклонения."""

    if action == "approve":
        if department == "head" and amount >= 50000:
            await approve_to_financial_dep(context, update, row_id, approver)
        else:
            await approve_to_payment_dep(context, update, row_id, approver, department)

    else:
        await reject_record(context, update, row_id, approver, initiator_id, department)


async def approve_to_financial_dep(context: ContextTypes.DEFAULT_TYPE, update: Update,
                                   row_id: str, approver: str) -> None:
    """
    Изменение количества апрувов и статуса платежа.
    Отправка сообщения о платеже свыше 50.000 в финансовый отдел на согласование платежа.
    """

    async with db:
        await db.update_row_by_id(
            row_id,
            {
                "approvals_received": 1,
                "status": "Pending",
                "approved_by": approver,
            },
        )
        record = await db.get_row_by_id(row_id)

    for chat_id, message_id in context.user_data[f"{row_id}_head"]:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Запрос на одобрение отправлен в финансовый отдел.",
                reply_markup=InlineKeyboardMarkup([]),
            )
        except Exception as e:
            logger.error(f"Не удалось обновить сообщение об апруве счёта с chat_id: {chat_id}: {e}")
    del context.user_data[f'{row_id}_head']
    await create_and_send_approval_message(row_id, record, "finance", context=context)


async def approve_to_payment_dep(context: ContextTypes.DEFAULT_TYPE, update: Update,
                                 row_id: str, approver: str, department: str) -> None:
    """
    Изменение количество апрувов и статус платежа.
    Отправка сообщения об одобрении платежа для отдела оплаты.
    """

    async with db:
        record = await db.get_row_by_id(row_id)
        approver_in_db = record.get("approved_by")
        await db.update_row_by_id(
            row_id,
            {
                "approvals_received": 2 if department == "finance" else 1,
                "status": "Approved",
                "approved_by": f"{approver_in_db}, {approver}",
            },
        )
        record = await db.get_row_by_id(row_id)
    for chat_id, message_id in context.user_data[f'{row_id}_{department}']:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Запрос на платеж одобрен. Счёт ожидает оплату.",
                reply_markup=InlineKeyboardMarkup([]),
            )
        except Exception as e:
            logger.error(f"Не удалось обновить сообщение об апруве счёта с chat_id: {chat_id} {e}")
    del context.user_data[f'{row_id}_{department}']
    await create_and_send_payment_message(row_id, record, context)


async def reject_record(context: ContextTypes.DEFAULT_TYPE, update: Update,
                        row_id: str, approver: str, initiator_id: str, department:str) -> None:
    """Отправка сообщения об отклонении платежа и изменении статуса платежа."""

    async with db:
        await db.update_row_by_id(
            row_id, {"status": "Rejected"}
        )

    for chat_id in context.user_data[f'{row_id}_{department}']:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                text=f"Счёт №{row_id} отклонен.",
                reply_markup=InlineKeyboardMarkup([]),
            )
        except Exception as e:
            logger.error(f"Не удалось обновить информацию об отклонении счёта с chat_id: {chat_id} {e}")

    del context.user_data[f'{row_id}_{department}']
    await context.bot.send_message(
        initiator_id, f"Счёт №{row_id} отклонен {approver}."
    )


async def create_and_send_payment_message(row_id: str, record: dict, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Создание кнопок "Оплачено",
    создание и отправка сообщения для одобрения заявки.
    """

    keyboard = [
        [InlineKeyboardButton("Оплачено", callback_data=f"payment_{row_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message_text = (
        f"Запрос на платёж для заявки {row_id} одобрен {record["approved_by"]} "
        f'{record["approvals_needed"]}/{record["approvals_received"]} раз. Пожалуйста, оплатите заявку. '
        f'сумма: {record["amount"]}, статья: "{record["expense_item"]}", группа: "{record["expense_group"]}", '
        f'партнер: "{record["partner"]}", период начисления: {record["period"]}, форма оплаты: '
        f'{record["payment_method"]}, комментарий: {record["comment"]}'
    )
    chat_ids_list = await chat_ids_department("payers")
    await send_message_to_chats(chat_ids_list, message_text, context, row_id, "payment", reply_markup)


async def payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик нажатий пользователем кнопки "Оплачено"
    """

    try:
        response_list = update.callback_query.data.split("_")
        row_id = response_list[1]

    except Exception as e:
        raise RuntimeError(f'Ошибка считывания данных с кнопки "Оплачено". Ошибка: {e}')

    await make_payment_and_add_record_to_google_sheet(update, context, row_id)


async def make_payment_and_add_record_to_google_sheet(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                                      row_id) -> None:
    async with db:
        record = await db.get_row_by_id(row_id)
        if not record:
            raise NotFound(f"Счёт №{row_id} не найден")
        await db.update_row_by_id(row_id, {"status": "Paid"})

    for chat_id, message_id in context.user_data[f'{row_id}_payment']:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"Счёт №{row_id} оплачен.",
                reply_markup=InlineKeyboardMarkup([])
            )
        except Exception as e:
            logger.error(f"Не удалось обновить сообщение об оплате счёта с chat_id: {chat_id}: {e}")

    # При нажатии "Оплачено" добавляем данные в таблицу
    await add_record_to_google_sheet(record)


async def check_department(approver_id: int) -> str | None:
    departments = {
        **{k: "head" for k in Config.head_chat_ids},
        **{k: "finance" for k in Config.finance_chat_ids},
        **{k: "payers" for k in Config.payers_chat_ids}
    }
    department = departments.get(approver_id)
    if department not in ("head", "finance", "payers"):
        return None
    return department


async def reject_record_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Меняет в базе данных статус платежа на отклонён('Rejected'),
    и отправляет сообщение об отмене ранее одобренного платежа.
    """

    row_id = context.args
    if not row_id:
        raise ValueError("Пожалуйста, укажите id заявки!")
    if len(row_id) > 1:
        raise ValueError("Можно указать только 1 заявку!")

    approver_id = update.effective_chat.id
    department = await check_department(approver_id)
    if department not in ("head", "finance"):
        raise PermissionError("Вы не можете менять статус заявок!")

    row_id = row_id[0]
    approver = f"@{update.effective_user.username}"
    async with db:
        record = await db.get_row_by_id(row_id)
        initiator_id = record.get("initiator_id")
        if not record:
            raise RuntimeError(f"Запись с id: {row_id} не найдена.")
    await reject_record(context, update, row_id, approver, initiator_id)


async def approve_record_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Меняет в базе данных статус платежа на отклонён('Rejected'),
    и отправляет сообщение об отмене ранее одобренного платежа.
    """

    row_id = context.args
    if not row_id:
        raise ValueError("Пожалуйста, укажите id заявки!")
    if len(row_id) > 1:
        raise ValueError("Можно указать только 1 заявку!")

    row_id = row_id[0]
    async with db:
        record = await db.get_row_by_id(row_id)
        if not record:
            raise RuntimeError(f"Запись с id: {row_id} не найдена.")

    approver_id = update.effective_chat.id
    department = await check_department(approver_id)
    if department not in ("head", "finance"):
        raise PermissionError("Вы не можете менять статус заявок!")

    action = "approve"
    approver = f"@{update.message.from_user.username}"
    amount = record.get("amount")

    await approval_process(context, update, action, row_id, approver, department, amount)


async def show_not_paid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Возвращает инициатору в тг-чат неоплаченные заявки на платежи из таблицы "approvals" в удобном формате
    """

    async with db:
        rows = await db.find_not_paid()
    messages = []

    for i, record in enumerate(rows, start=1):
        line = ", ".join([f"{key}: {value}" for key, value in record.items()])
        message_line = f"{i}. {line}"
        wrapped_message = textwrap.fill(message_line, width=4096)
        messages.append(wrapped_message)

    final_text = "\n\n".join(messages)

    if final_text:
        await update.message.reply_text(final_text)
    else:
        await update.message.reply_text("Заявок не обнаружено")

    return

import traceback

async def error_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик ошибок для логирования и уведомления пользователя с детальной информацией об ошибке."""

    try:
        error_text = str(context.error)
        error_traceback = traceback.format_exc()
        message_text = f'{error_text}. {error_traceback}'
        await context.bot.send_message(update.effective_chat.id, message_text)
        await context.bot.send_message(Config.developer_chat_id, message_text)
        logger.error(f"{message_text}")

    except Exception as e:
        message_text = f"Ошибка при отправке уведомления об ошибке: {e}."

        logger.error(message_text, error_traceback)
        await context.bot.send_message(Config.developer_chat_id, message_text)
