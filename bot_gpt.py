import asyncio
import logging
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

from config import BOT_TOKEN, DIALOGS_FOLDER, OPENAI_API_KEY
from neuro_salesman_gpt import NeuroSalesmanGPT
from dialog_logger import DialogLogger

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Инициализация нейропродажника с GPT и логгера
neuro_salesman = NeuroSalesmanGPT(api_key=OPENAI_API_KEY)
dialog_logger = DialogLogger(DIALOGS_FOLDER)

# Словарь для отслеживания активных диалогов
active_dialogs = {}

# Словарь для отслеживания пользователей, ожидающих отзыв
waiting_for_feedback = {}

# Настройки таймаута
TIMEOUT_MINUTES = 10
CLEANUP_INTERVAL_SECONDS = 60  # Проверяем каждую минуту

# Создаем клавиатуру с кнопкой остановки диалога
def get_stop_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛑 Остановить диалог", callback_data="stop_dialog")]
    ])
    return keyboard

@dp.callback_query(lambda c: c.data == "stop_dialog")
async def process_stop_dialog_callback(callback_query: types.CallbackQuery):
    """Обработчик нажатия кнопки остановки диалога"""
    user_id = callback_query.from_user.id
    
    # Завершаем диалог
    json_filepath, docx_filepath = dialog_logger.finish_dialog(user_id, reason="button_stop")
    if json_filepath:
        logger.info(f"Диалог пользователя {user_id} завершен через кнопку и сохранен в {json_filepath}")
    if docx_filepath:
        logger.info(f"DOCX файл пользователя {user_id} создан: {docx_filepath}")
    
    # Удаляем из активных диалогов
    if user_id in active_dialogs:
        del active_dialogs[user_id]
    
    # Отправляем запрос на отзыв
    await callback_query.message.answer("🎯 Диалог завершен! Пожалуйста, напишите ваш отзыв о работе бота:")
    waiting_for_feedback[user_id] = True
    
    # Отвечаем на callback
    await callback_query.answer("Диалог остановлен")


async def cleanup_inactive_dialogs():
    """Фоновая задача для очистки неактивных диалогов"""
    while True:
        try:
            # Получаем список неактивных диалогов
            inactive_users = dialog_logger.get_inactive_dialogs(TIMEOUT_MINUTES)
            
            for user_id in inactive_users:
                if user_id in active_dialogs:
                    logger.info(f"Завершение неактивного диалога пользователя {user_id} (таймаут {TIMEOUT_MINUTES} минут)")
                    
                    # Завершаем диалог
                    json_filepath, docx_filepath = dialog_logger.finish_dialog(user_id, reason="timeout")
                    if json_filepath:
                        logger.info(f"Диалог пользователя {user_id} сохранен в {json_filepath}")
                    if docx_filepath:
                        logger.info(f"DOCX файл пользователя {user_id} создан: {docx_filepath}")
                    
                    # Удаляем из активных диалогов
                    del active_dialogs[user_id]
                    
                    # Отправляем уведомление пользователю и запрос на отзыв
                    try:
                        await bot.send_message(
                            user_id, 
                            f"Диалог автоматически завершен из-за неактивности ({TIMEOUT_MINUTES} минут). Пожалуйста, напишите ваш отзыв о работе бота:"
                        )
                        waiting_for_feedback[user_id] = True
                    except Exception as e:
                        logger.warning(f"Не удалось отправить уведомление пользователю {user_id}: {e}")
            
            # Ждем до следующей проверки
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
            
        except Exception as e:
            logger.error(f"Ошибка в фоновой задаче очистки: {e}")
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    
    # Приветственное сообщение
    welcome_text = """Этот бот предназначен для тестирования промта нейропродажника, проведите с ботом ролевой диалог в котором вы выступаете в качестве HR специалиста или работника кадров. Для завершения диалога напишите СТОП или нажмите кнопку 'Остановить диалог'. После завершения диалога вы можете оставить отзыв и комментарии о работе бота, что понравилось или какие бот допустил ошибки. Начнем диалог через пару секунд!"""
    
    await message.answer(welcome_text, reply_markup=get_stop_keyboard())
    
    # Отмечаем начало диалога
    active_dialogs[user_id] = True
    
    # Сбрасываем предыдущую историю для этого пользователя
    neuro_salesman.reset_conversation(user_id)
    
    # Генерируем первое сообщение от нейропродажника
    first_message = """Привет! 👋

Отлично, что вы завершили тестовый период — это уже первый шаг к автоматизации найма! 

Сейчас самое время адаптировать AI-рекрутера под ваши конкретные задачи. Я задам несколько быстрых вопросов — не "для галочки", а чтобы подобрать самый подходящий тариф и результат без лишних затрат или перегруза функционалом.

Как прошел ваш пробный период, все ли функции удалось протестировать?"""
    
    # Обрабатываем первое сообщение через нейропродажника
    response, agent_communication = neuro_salesman.process_message(user_id, "начало диалога")
    
    # Логируем первое сообщение (response уже содержит только текст для пользователя)
    dialog_logger.add_message(user_id, "начало диалога", response, agent_communication)
    
    await message.answer(response, reply_markup=get_stop_keyboard())

@dp.message()
async def handle_message(message: Message):
    """Обработчик всех остальных сообщений"""
    user_id = message.from_user.id
    user_message = message.text
    
    # Проверяем, ожидается ли отзыв от пользователя
    if user_id in waiting_for_feedback:
        # Сохраняем отзыв в DOCX файл
        try:
            feedback_saved = dialog_logger.add_feedback_to_docx(user_id, user_message)
            if feedback_saved:
                await message.answer("✅ Спасибо за ваш отзыв! Он сохранен в истории диалога.")
            else:
                await message.answer("⚠️ Не удалось сохранить отзыв, но спасибо за обратную связь!")
        except Exception as e:
            logger.error(f"Ошибка при сохранении отзыва: {e}")
            await message.answer("⚠️ Произошла ошибка при сохранении отзыва, но спасибо за обратную связь!")
        
        # Удаляем из ожидающих отзыв
        del waiting_for_feedback[user_id]
        
        # Отправляем DOCX файл пользователю
        try:
            docx_filepath = dialog_logger.get_latest_docx_path(user_id)
            if docx_filepath and os.path.exists(docx_filepath):
                with open(docx_filepath, 'rb') as docx_file:
                    await message.answer_document(
                        types.BufferedInputFile(
                            docx_file.read(),
                            filename=f"dialog_{user_id}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.docx"
                        ),
                        caption="📄 История вашего диалога с нейропродажником (включая ваш отзыв)"
                    )
            else:
                await message.answer("📄 DOCX файл с историей диалога будет доступен позже.")
        except Exception as e:
            logger.error(f"Ошибка при отправке DOCX файла: {e}")
            await message.answer("📄 История диалога сохранена, но возникла проблема с отправкой файла.")
        
        # Предлагаем пройти переписку еще раз
        await message.answer("🎯 Хотите пройти переписку еще раз? Нажмите /start для начала нового диалога.")
        return
    
    # Проверяем, активен ли диалог
    if user_id not in active_dialogs:
        await message.answer("Пожалуйста, начните диалог с команды /start")
        return
    
    try:
        # Проверяем, не написал ли пользователь "стоп"
        if user_message.lower().strip() == "стоп":
            # Завершаем диалог
            json_filepath, docx_filepath = dialog_logger.finish_dialog(user_id, reason="user_stop")
            if json_filepath:
                logger.info(f"Диалог пользователя {user_id} завершен по команде 'стоп' и сохранен в {json_filepath}")
            if docx_filepath:
                logger.info(f"DOCX файл пользователя {user_id} создан: {docx_filepath}")
            
            # Удаляем из активных диалогов
            if user_id in active_dialogs:
                del active_dialogs[user_id]
            
            # Отправляем запрос на отзыв
            await message.answer("🎯 Диалог завершен! Пожалуйста, напишите ваш отзыв о работе бота:")
            waiting_for_feedback[user_id] = True
            return
        
        # Обрабатываем сообщение через нейропродажника с GPT
        response, agent_communication = neuro_salesman.process_message(user_id, user_message)
        
        # Логируем сообщение (response уже содержит только текст для пользователя)
        dialog_logger.add_message(user_id, user_message, response, agent_communication)
        
        # Отправляем ответ пользователю с кнопкой остановки
        await message.answer(response, reply_markup=get_stop_keyboard())
        
        # Проверяем, не завершился ли диалог (например, пользователь согласился на покупку)
        # Используем только слово "стоп" для завершения диалога
        if "стоп" in response.lower():
            # Завершаем диалог
            json_filepath, docx_filepath = dialog_logger.finish_dialog(user_id, reason="success")
            if json_filepath:
                logger.info(f"Диалог пользователя {user_id} сохранен в {json_filepath}")
            if docx_filepath:
                logger.info(f"DOCX файл пользователя {user_id} создан: {docx_filepath}")
            
            # Удаляем из активных диалогов
            if user_id in active_dialogs:
                del active_dialogs[user_id]
            
            # Отправляем запрос на отзыв
            await message.answer("🎯 Диалог завершен! Пожалуйста, напишите ваш отзыв о работе бота:")
            waiting_for_feedback[user_id] = True
                
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения: {e}")
        await message.answer("Извините, произошла ошибка. Попробуйте еще раз.")

@dp.message(Command("stop"))
async def cmd_stop(message: Message):
    """Обработчик команды /stop для завершения диалога"""
    user_id = message.from_user.id
    
    # Всегда пытаемся завершить диалог, даже если его нет в active_dialogs
    json_filepath, docx_filepath = dialog_logger.finish_dialog(user_id, reason="manual")
    if json_filepath:
        logger.info(f"Диалог пользователя {user_id} сохранен в {json_filepath}")
    if docx_filepath:
        logger.info(f"DOCX файл пользователя {user_id} создан: {docx_filepath}")
    else:
        # Проверяем, есть ли диалог в логгере
        summary = dialog_logger.get_dialog_summary(user_id)
        if summary:
            logger.error(f"Не удалось сохранить диалог пользователя {user_id}")
    
    # Удаляем из активных диалогов
    if user_id in active_dialogs:
        del active_dialogs[user_id]
    
    # Отправляем запрос на отзыв
    await message.answer("🎯 Диалог завершен! Пожалуйста, напишите ваш отзыв о работе бота:")
    waiting_for_feedback[user_id] = True

@dp.message(Command("status"))
async def cmd_status(message: Message):
    """Обработчик команды /status для проверки статуса диалога"""
    user_id = message.from_user.id
    
    if user_id in active_dialogs:
        summary = dialog_logger.get_dialog_summary(user_id)
        if summary:
            # Вычисляем время до автоматического завершения
            if summary.get('last_activity'):
                from datetime import datetime, timedelta
                last_activity = datetime.fromisoformat(summary['last_activity'])
                time_since_activity = datetime.now() - last_activity
                time_until_timeout = timedelta(minutes=TIMEOUT_MINUTES) - time_since_activity
                
                if time_until_timeout.total_seconds() > 0:
                    minutes_left = int(time_until_timeout.total_seconds() // 60)
                    seconds_left = int(time_until_timeout.total_seconds() % 60)
                    timeout_info = f"⏰ Автоматическое завершение через: {minutes_left}м {seconds_left}с"
                else:
                    timeout_info = "⚠️ Диалог будет завершен автоматически"
            else:
                timeout_info = "⏰ Таймаут не отслеживается"
            
            status_text = f"""Статус диалога:
ID пользователя: {summary['user_id']}
Время начала: {summary['start_time']}
Количество сообщений: {summary['message_count']}
{timeout_info}"""
            await message.answer(status_text)
        else:
            await message.answer("Диалог активен, но информация недоступна")
    elif user_id in waiting_for_feedback:
        await message.answer("⏳ Ожидается ваш отзыв о работе бота. Пожалуйста, напишите ваш отзыв.")
    else:
        await message.answer("Активный диалог не найден")

@dp.message(Command("profile"))
async def cmd_profile(message: Message):
    """Обработчик команды /profile для показа профиля пользователя"""
    user_id = message.from_user.id
    
    profile = neuro_salesman.get_user_profile(user_id)
    if profile:
        profile_text = "📊 Ваш профиль:\n"
        for key, value in profile.items():
            profile_text += f"• {key}: {value}\n"
        await message.answer(profile_text)
    else:
        await message.answer("Профиль пока не заполнен")

@dp.message(Command("history"))
async def cmd_history(message: Message):
    """Обработчик команды /history для показа истории диалога"""
    user_id = message.from_user.id
    
    history = neuro_salesman.get_conversation_history(user_id)
    if history:
        history_text = "📝 История диалога:\n"
        for i, msg in enumerate(history[-5:], 1):  # Показываем последние 5 сообщений
            role = "👤" if msg["role"] == "user" else "🤖"
            history_text += f"{i}. {role} {msg['content'][:50]}...\n"
        await message.answer(history_text)
    else:
        await message.answer("История диалога пуста")

@dp.message(Command("reset"))
async def cmd_reset(message: Message):
    """Обработчик команды /reset для сброса диалога"""
    user_id = message.from_user.id
    
    # Сбрасываем диалог
    neuro_salesman.reset_conversation(user_id)
    
    # Удаляем из активных диалогов и ожидающих отзыв
    if user_id in active_dialogs:
        del active_dialogs[user_id]
    if user_id in waiting_for_feedback:
        del waiting_for_feedback[user_id]
    
    await message.answer("Диалог сброшен. Используйте /start для начала нового диалога.")

@dp.message(Command("timeout"))
async def cmd_timeout(message: Message):
    """Обработчик команды /timeout для проверки неактивных диалогов (админская команда)"""
    # Завершаем все неактивные диалоги
    saved_files = dialog_logger.cleanup_inactive_dialogs(TIMEOUT_MINUTES)
    
    if saved_files:
        files_text = "\n".join([f"• {os.path.basename(f)}" for f in saved_files])
        await message.answer(f"⏰ Завершены неактивные диалоги:\n{files_text}")
    else:
        await message.answer("⏰ Неактивных диалогов не найдено")

@dp.message(Command("finish"))
async def cmd_finish(message: Message):
    """Обработчик команды /finish для принудительного завершения всех диалогов"""
    user_id = message.from_user.id
    
    # Завершаем диалог пользователя
    json_filepath, docx_filepath = dialog_logger.finish_dialog(user_id, reason="force_finish")
    if json_filepath:
        logger.info(f"Диалог пользователя {user_id} принудительно завершен и сохранен в {json_filepath}")
    if docx_filepath:
        logger.info(f"DOCX файл пользователя {user_id} создан: {docx_filepath}")
    else:
        logger.info(f"Диалог для завершения не найден для пользователя {user_id}")
    
    # Удаляем из активных диалогов
    if user_id in active_dialogs:
        del active_dialogs[user_id]
    
    # Отправляем запрос на отзыв
    await message.answer("🎯 Диалог завершен! Пожалуйста, напишите ваш отзыв о работе бота:")
    waiting_for_feedback[user_id] = True

@dp.message(Command("debug"))
async def cmd_debug(message: Message):
    """Обработчик команды /debug для отладочной информации"""
    user_id = message.from_user.id
    
    debug_info = f"""🔍 Отладочная информация:
ID пользователя: {user_id}
В active_dialogs: {user_id in active_dialogs}
"""
    
    # Проверяем состояние диалога в логгере
    summary = dialog_logger.get_dialog_summary(user_id)
    if summary:
        debug_info += f"""В dialog_logger: ✅
Количество сообщений: {summary['message_count']}
Время начала: {summary['start_time']}
"""
    else:
        debug_info += "В dialog_logger: ❌\n"
    
    # Проверяем папку dialogs
    dialogs_count = len([f for f in os.listdir("dialogs") if f.endswith('.json')]) if os.path.exists("dialogs") else 0
    debug_info += f"Файлов диалогов в папке: {dialogs_count}"
    
    await message.answer(debug_info)
    user_id = message.from_user.id
    
    # Проверяем, есть ли активные диалоги
    if active_dialogs:
        inactive_users = dialog_logger.get_inactive_dialogs(TIMEOUT_MINUTES)
        if inactive_users:
            timeout_text = f"⏰ Неактивные диалоги (более {TIMEOUT_MINUTES} минут):\n"
            for uid in inactive_users:
                summary = dialog_logger.get_dialog_summary(uid)
                if summary and summary.get('last_activity'):
                    from datetime import datetime
                    last_activity = datetime.fromisoformat(summary['last_activity'])
                    time_since = datetime.now() - last_activity
                    minutes = int(time_since.total_seconds() // 60)
                    timeout_text += f"• Пользователь {uid}: {minutes} минут назад\n"
            await message.answer(timeout_text)
        else:
            await message.answer("Нет неактивных диалогов")
    else:
        await message.answer("Нет активных диалогов")

async def main():
    """Главная функция"""
    logger.info("Запуск бота с GPT...")
    logger.info(f"Таймаут неактивности: {TIMEOUT_MINUTES} минут")
    
    # Запускаем фоновую задачу очистки неактивных диалогов
    asyncio.create_task(cleanup_inactive_dialogs())
    
    # Запускаем бота
    await dp.start_polling(bot)

    asyncio.run(main()) 