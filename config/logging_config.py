import logging
import os
from logging.handlers import RotatingFileHandler

LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
LOG_DIR = "./logs"
LOG_FILE = os.path.join(LOG_DIR, "app.log")
MAX_SIZE = 10 * 1024 * 1024
MAX_FILES = 5


def configure_logging(max_bytes=MAX_SIZE, backup_count=MAX_FILES):
    """Обработчик логгирования в проекте"""
    # Создаем обработчик файлового логгера
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8')
    file_handler.setLevel(logging.getLevelName(LOG_LEVEL))
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    # Настраиваем корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.getLevelName(LOG_LEVEL))
    root_logger.addHandler(file_handler)

    # Создаем потоковый обработчик для консоли
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.getLevelName(LOG_LEVEL))
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    # Создаем глобальный логгер
    logger = logging.getLogger("budget_automation_bot")
    logger.setLevel(logging.getLevelName(LOG_LEVEL))
    logger.addHandler(console_handler)

    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    return logger


logger = configure_logging()
