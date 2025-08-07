import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
BOT_TOKEN = os.getenv('BOT_TOKEN')

# OpenAI API Key (если понадобится для дополнительных функций)
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Папка для сохранения диалогов
DIALOGS_FOLDER = "dialogs"

# Создаем папку если её нет
if not os.path.exists(DIALOGS_FOLDER):
    os.makedirs(DIALOGS_FOLDER) 