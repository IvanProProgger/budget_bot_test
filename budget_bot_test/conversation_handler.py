import re
from datetime import datetime

from telegram import Update, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler, ContextTypes

from config.config import Config
from config.logging_config import logger
from budget_bot_test.handlers import submit_record_command
from budget_bot_test.sheets import GoogleSheetsManager

(
    INPUT_SUM,
    INPUT_ITEM,
    INPUT_GROUP,
    INPUT_PARTNER,
    INPUT_COMMENT,
    INPUT_DATES,
    INPUT_PAYMENT_TYPE,
    CONFIRM_COMMAND,
) = range(8)

payment_types: list[str] = ["нал", "безнал", "крипта"]


async def create_keyboard(massive: list[str]) -> InlineKeyboardMarkup:
    """Функция для создания клавиатуры. Каждый кнопка создаётся с новой строки."""

    keyboard = []
    for number, item in enumerate(massive):
        button = InlineKeyboardButton(item, callback_data=number)
        keyboard.append([button])

    return InlineKeyboardMarkup(keyboard)


async def enter_record(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало диалога. Ввод суммы и получение данных о статьях, группах, партнёрах."""

    context.user_data["chat_id"] = update.effective_chat.id
    if context.user_data["chat_id"] not in Config.initiators_chat_ids:
        raise PermissionError("Команда запрещена! Вы не находитесь в списке инициаторов.")

    manager = GoogleSheetsManager()
    await manager.initialize_google_sheets()
    options_dict, items = await manager.get_data()
    context.user_data["options"], context.user_data["items"] = options_dict, items


    bot_message = await update.message.reply_text(
        "Введите сумму:",
        reply_markup=ForceReply(selective=True),
    )
    context.user_data["enter_sum_message_id"] = bot_message.message_id

    return INPUT_SUM


async def input_sum(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода суммы и выбор категории."""

    user_sum = update.message.text
    pattern = r"^[0-9]+(?:\.[0-9]+)?$"

    await update.message.from_user.delete_message(update.message.message_id)

    if not re.fullmatch(pattern, user_sum):
        await update.message.reply_text("Некорректная сумма. Попробуйте ещё раз.")
        bot_message = await update.message.reply_text(
            "Введите сумму:",
            reply_markup=ForceReply(selective=True),
        )
        context.user_data["enter_sum_message_id"] = bot_message.message_id
        return INPUT_SUM

    del context.user_data["enter_sum_message_id"]

    context.user_data["sum"] = user_sum
    await update.message.reply_text(f"Введена сумма: {user_sum}")

    items = context.user_data["items"]

    reply_markup = await create_keyboard(items)

    await update.message.reply_text(
        "Выберите статью расхода:", reply_markup=reply_markup
    )

    return INPUT_ITEM


async def input_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик выбора категории счёта."""

    query = update.callback_query
    selected_item = context.user_data["items"][int(query.data)]
    logger.info(f"Выбрана статья расхода: {selected_item}")
    await query.edit_message_text(f"Выбрана статья расхода: {selected_item}")

    context.user_data["item"] = selected_item
    context.user_data["options"] = context.user_data["options"].get(selected_item)
    groups = list(context.user_data["options"].keys())
    context.user_data["groups"] = groups

    del context.user_data["items"]

    if len(groups) == 1:

        selected_group = context.user_data["groups"][0]
        logger.info(f"Выбрана группа расхода: {selected_group}")
        context.user_data["group"] = selected_group
        partners = context.user_data["options"].get(selected_group)
        context.user_data["partners"] = context.user_data["options"].get(selected_group)
        del context.user_data["options"]
        del context.user_data["groups"]

        await context.bot.send_message(
            context.user_data["chat_id"], f"Выбрана группа расхода: {selected_group}"
        )

        if len(partners) == 1:
            selected_partner = context.user_data["partners"][0]
            logger.info(f"Выбран партнёр расхода: {selected_partner}")
            context.user_data["partner"] = selected_partner
            del context.user_data["partners"]

            await context.bot.send_message(
                context.user_data["chat_id"], f"Выбран партнёр: {selected_partner}"
            )

            await query.message.reply_text(
                "Введите комментарий для отчёта:",
                reply_markup=ForceReply(selective=True),
            )
            return INPUT_COMMENT

        reply_markup = await create_keyboard(context.user_data["partners"])
        await query.message.reply_text("Выберите партнёра:", reply_markup=reply_markup)

        return INPUT_PARTNER

    reply_markup = await create_keyboard(groups)
    await query.message.reply_text(
        "Выберите группу расхода:", reply_markup=reply_markup
    )

    return INPUT_GROUP


async def input_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик выбора группы расходов."""

    query = update.callback_query
    selected_group = context.user_data["groups"][int(query.data)]
    logger.info(f"Выбрана группа расхода: {selected_group}")
    await query.edit_message_text(f"Выбрана группа расхода: {selected_group}")

    context.user_data["group"] = selected_group
    partners = context.user_data["options"].get(selected_group)
    context.user_data["partners"] = partners
    del context.user_data["options"]
    del context.user_data["groups"]

    if len(partners) == 1:
        selected_partner = context.user_data["partners"][0]
        logger.info(f"Выбран партнёр расхода: {selected_partner}")
        context.user_data["partner"] = selected_partner
        del context.user_data["partners"]
        await context.bot.send_message(
            context.user_data["chat_id"], f"Выбран партнёр: {selected_partner}"
        )

        await query.message.reply_text(
            "Введите комментарий для отчёта:",
            reply_markup=ForceReply(selective=True),
        )
        return INPUT_COMMENT

    reply_markup = await create_keyboard(context.user_data["partners"])
    await query.message.reply_text("Выберите партнёра:", reply_markup=reply_markup)

    return INPUT_PARTNER


async def input_partner(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик выбора партнёра к группе расходов счёта и создание цитирования для ввода комментария"""

    query = update.callback_query
    selected_partner = context.user_data["partners"][int(query.data)]
    logger.info(f"Выбран партнёр расхода: {selected_partner}")
    await query.edit_message_text(f"Выбран партнёр: {selected_partner}")

    context.user_data["partner"] = selected_partner
    del context.user_data["partners"]

    await query.message.reply_text(
        "Введите комментарий для отчёта:",
        reply_markup=ForceReply(selective=True),
    )
    return INPUT_COMMENT


async def input_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода комментария к счёту и создание цитирования для ввода дат"""

    user_comment = update.message.text

    pattern = r"^\S.*"
    if not re.fullmatch(pattern, user_comment):
        await update.message.reply_text("Некорректный комментарий. Попробуйте ещё раз")
        return ConversationHandler.END

    logger.info(f"Введён комментарий {user_comment}")
    context.user_data["comment"] = user_comment

    await update.message.from_user.delete_message(update.message.message_id)

    await update.message.reply_text(f"Введён комментарий: {user_comment}")
    await update.message.reply_text(
        'Введите месяц и год начисления счёта строго через пробел в формате mm.yy (Например "09.22 11.22"):',
        reply_markup=ForceReply(selective=True),
    )

    return INPUT_DATES


async def input_dates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода дат начисления счёта и создание кнопок для выбора типа оплаты"""

    user_dates = update.message.text

    try:
        pattern = r"(\d{2}\.\d{2}\s*)+"
        match = re.search(pattern, user_dates)
        if not re.fullmatch(pattern, user_dates):
            await update.message.reply_text("Неверный формат дат.")
        period_dates = match.group(0).split()
        _ = [
            datetime.strptime(f"01.{date}", "%d.%m.%y").strftime("%Y-%m-%d")
            for date in period_dates
        ]

    except Exception:
        await update.message.reply_text(
            f'Неверный формат дат. Введите даты начисления счетов в формате mm.yy строго через'
            ' пробел(например: "03.21 07.21 12.22"). Попробуйте ещё раз.',
            reply_markup=ForceReply(selective=True),
        )
        return INPUT_DATES

    context.user_data["dates"] = user_dates
    logger.info(f"Введены даты: {user_dates}")
    await update.message.reply_text(f"Введены даты: {user_dates}")

    await update.message.from_user.delete_message(update.message.message_id)

    reply_markup = await create_keyboard(payment_types)
    await update.message.reply_text("Выберите тип оплаты:", reply_markup=reply_markup)

    return INPUT_PAYMENT_TYPE


async def input_payment_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик выбора типа оплаты и создание итогового сообщения для подтверждения или отклонения счёта"""

    query = update.callback_query
    await query.answer()
    payment_type = payment_types[int(query.data)]
    logger.info(f"Выбран тип счёта: {payment_type}")
    await query.edit_message_text(f"Выбран тип счёта: {payment_type}")

    final_command = (
        f"{context.user_data['sum']}; {context.user_data['item']}; "
        f"{context.user_data['group']}; {context.user_data['partner']}; {context.user_data['comment']}; "
        f"{context.user_data['dates']}; {payment_type}"
    )

    context.user_data["final_command"] = final_command

    buttons = [
        [InlineKeyboardButton("Подтвердить", callback_data="Подтвердить")],
        [InlineKeyboardButton("Отмена", callback_data="Отмена")],
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    await query.message.reply_text(
        text=f"Полученная информация о счёте:\n1)Сумма: {context.user_data['sum']}\n"
             f"2)Статья: {context.user_data['item']}\n3)Группа: {context.user_data['group']}\n"
             f"4)Партнёр: {context.user_data['partner']}\n5)Комментарий: {context.user_data['comment']}\n"
             f"6)Даты начисления: {context.user_data['dates']}\n"
             f"7)Форма оплаты: {payment_type}\nПроверьте правильность введённых данных!",
        reply_markup=reply_markup,
    )

    return CONFIRM_COMMAND


async def confirm_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик подтверждения и отклонения итоговой команды."""

    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)

    if query.data == "Подтвердить":
        context.args = context.user_data.get("final_command").split()
        context.user_data.clear()
        logger.info(f"счёта подтверждён @{query.from_user.username}")
        await submit_record_command(update, context)
        return ConversationHandler.END


    elif query.data == "Отмена":
        logger.info(f"счёта отменён @{query.from_user.username}")
        await stop_dialog(update, context)


async def stop_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /stop."""

    context.user_data.clear()

    await update.message.reply_text(
        "Диалог был остановлен. Начните заново с командой /enter_record",
        reply_markup=InlineKeyboardMarkup([]),
    )

    return ConversationHandler.END
