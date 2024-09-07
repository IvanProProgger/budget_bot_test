from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters
)

from config.config import Config

from marketing_budget_tennisi_bot.conversation_handler import (
    enter_record,
    input_sum,
    input_item,
    input_group,
    input_partner,
    input_comment,
    input_dates,
    input_payment_type,
    confirm_command,
    stop_dialog,
)
from marketing_budget_tennisi_bot.handlers import (
    check_access,
    start_command,
    submit_record_command,
    approval_handler,
    payment_handler,
    show_not_paid_command,
    approve_record_command,
    reject_record_command,
    error_callback
)

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


def main() -> None:
    """Основная функция для запуска бота."""
    application = Application.builder().token(Config.telegram_bot_token).build()
    application.add_handler(MessageHandler(~filters.User(user_id=Config.white_list), check_access))
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("submit_record", submit_record_command))
    application.add_handler(CommandHandler("reject_record", reject_record_command))
    application.add_handler(CommandHandler("approve_record", approve_record_command))
    application.add_handler(CommandHandler("show_not_paid", show_not_paid_command))
    application.add_handler(CallbackQueryHandler(approval_handler, pattern="^approval_.*"))
    application.add_handler(CallbackQueryHandler(payment_handler, pattern="^payment_.*"))
    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler("enter_record", enter_record)],
        states={
            INPUT_SUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_sum)],
            INPUT_ITEM: [CallbackQueryHandler(input_item)],
            INPUT_GROUP: [CallbackQueryHandler(input_group)],
            INPUT_PARTNER: [CallbackQueryHandler(input_partner)],
            INPUT_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_comment)],
            INPUT_DATES: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_dates)],
            INPUT_PAYMENT_TYPE: [CallbackQueryHandler(input_payment_type)],
            CONFIRM_COMMAND: [CallbackQueryHandler(confirm_command)],
        },
        fallbacks=[
            CommandHandler("stop", stop_dialog),
        ],
    )
    application.add_handler(conversation_handler)
    application.add_error_handler(error_callback)
    application.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
