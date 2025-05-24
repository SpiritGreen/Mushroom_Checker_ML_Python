import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    JobQueue,
    CallbackQueryHandler,
)
import httpx
from typing import Dict
import io

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Конфигурация
API_BASE_URL = "http://localhost:8000"  # FastAPI сервер
BOT_TOKEN = "7915019188:AAGDDX6Pi0MOhGmc6Q_5Dq0l_P3IuOrR9r0"  

# Токенохранилище
user_tokens: Dict[int, str] = {}  # {telegram_id: jwt_token}

# Состояния для ConversationHandler
REGISTER_USERNAME, REGISTER_PASSWORD, LOGIN_USERNAME, LOGIN_PASSWORD, PREDICT_MODEL_ID, PREDICT_FILE, PAYMENT = range(7)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start: приветствие и инструкции."""
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}! \n"
        "Я бот для классификации грибов 🍄. \n"
        "Доступные команды:\n"
        "/register — зарегистрироваться\n"
        "/login — войти\n"
        "/models — посмотреть доступные модели\n"
        "/predict — сделать предсказание\n"
        "/balance — проверить баланс\n"
        "/transactions — история транзакций\n"
        "/payment — пополнить баланс"
    )

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /register: запрашивает username и password."""
    await update.message.reply_text("Введите username:")
    return REGISTER_USERNAME

async def register_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает username и запрашивает пароль."""
    context.user_data["username"] = update.message.text
    await update.message.reply_text("Введите пароль:")
    return REGISTER_PASSWORD

async def register_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет запрос на регистрацию."""
    username = context.user_data["username"]
    password = update.message.text
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{API_BASE_URL}/register",
                data={"username": username, "password": password}
            )
            response.raise_for_status()
            await update.message.reply_text("Регистрация успешна! Используйте /login для входа.")
        except httpx.HTTPStatusError as e:
            await update.message.reply_text(f"Ошибка регистрации: {response.json().get('detail', 'Попробуйте снова')}")
    context.user_data.clear()  # Очищаем данные после регистрации
    return ConversationHandler.END

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /login: запрашивает username и password."""
    await update.message.reply_text("Введите username:")
    return LOGIN_USERNAME

async def login_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает username и запрашивает пароль."""
    context.user_data["username"] = update.message.text
    await update.message.reply_text("Введите пароль:")
    return LOGIN_PASSWORD

async def login_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет запрос на аутентификацию и сохраняет токен."""
    username = context.user_data["username"]
    password = update.message.text
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{API_BASE_URL}/token",
                data={"username": username, "password": password}
            )
            response.raise_for_status()
            token = response.json()["access_token"]
            user_tokens[update.effective_user.id] = token
            await update.message.reply_text("Вход успешен! Теперь вы можете использовать другие команды.")
        except httpx.HTTPStatusError as e:
            await update.message.reply_text(f"Ошибка входа: {response.json().get('detail', 'Попробуйте снова')}")
    context.user_data.clear()  # Очищаем данные после входа
    return ConversationHandler.END

async def predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /predict: запрашивает model_id и файл."""
    if update.effective_user.id not in user_tokens:
        await update.message.reply_text("Пожалуйста, войдите с помощью /login.")
        return ConversationHandler.END
    reply_text = (
        "Выберите модель для классификации грибов 🍄:\n"
        "1️⃣ Random Forest (1 токен) — быстрый и надёжный выбор для точных предсказаний.\n"
        "2️⃣ Gradient Boosting (2 токена) — более мощная модель для сложных данных.\n"
        "3️⃣ Neural Network (3 токена) — глубокое обучение для максимальной точности.\n\n"
        "Введите номер модели (1, 2 или 3):"
    )
    await update.message.reply_text(reply_text)
    return PREDICT_MODEL_ID

async def predict_model_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает model_id и запрашивает файл."""
    try:
        context.user_data["model_id"] = int(update.message.text)
        await update.message.reply_text("Отправьте CSV или XLSX файл с данными:")
        return PREDICT_FILE
    except ValueError:
        await update.message.reply_text("ID модели должен быть числом. Попробуйте снова:")
        return PREDICT_MODEL_ID

async def predict_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет файл на предсказание."""
    logger.info(f"User {update.effective_user.id} sent a file for prediction")
    if not update.message.document:
        logger.warning("No document received in predict_file")
        await update.message.reply_text("Пожалуйста, отправьте CSV или XLSX файл.")
        return PREDICT_FILE

    model_id = context.user_data["model_id"]
    token = user_tokens.get(update.effective_user.id)
    document = update.message.document
    logger.info(f"Processing file: {document.file_name}, model_id: {model_id}")

    # Проверяем расширение файла
    if not document.file_name.lower().endswith(('.csv', '.xlsx')):
        logger.warning(f"Invalid file type: {document.file_name}")
        await update.message.reply_text("Ошибка: файл должен быть в формате CSV или XLSX.")
        return PREDICT_FILE

    async with httpx.AsyncClient() as client:
        try:
            file = await document.get_file()
            file_content = await file.download_as_bytearray()
            file_stream = io.BytesIO(file_content)
            files = {"file": (document.file_name, file_stream, "multipart/form-data")}
            logger.info(f"Sending predict request to {API_BASE_URL}/predict?model_id={model_id}")
            response = await client.post(
                f"{API_BASE_URL}/predict?model_id={model_id}",
                headers={"Authorization": f"Bearer {token}"},
                files=files
            )
            response.raise_for_status()
            prediction = response.json()
            logger.info(f"Prediction response: {prediction}")

            # Проверяем наличие необходимых полей
            required_fields = ["id", "task_id", "status"]
            missing_fields = [field for field in required_fields if field not in prediction]
            if missing_fields:
                logger.error(f"Missing fields in prediction response: {missing_fields}")
                await update.message.reply_text("Ошибка: Некорректный ответ от сервера. Попробуйте позже.")
                return ConversationHandler.END

            # Формируем сообщение
            prediction_id = prediction["id"]
            message = (
                f"Предсказание создано! ID: {prediction_id}, Task ID: {prediction['task_id']}, Статус: {prediction['status']}\n"
            )

            # Создаём кнопку для проверки статуса
            keyboard = [[InlineKeyboardButton("Проверить статус", callback_data=f"status_{prediction_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Проверяем наличие JobQueue
            if context.job_queue is not None:
                context.job_queue.run_repeating(
                    check_prediction_status,
                    interval=10,
                    first=10,
                    data={"prediction_id": prediction_id, "user_id": update.effective_user.id},
                    chat_id=update.effective_chat.id,
                    user_id=update.effective_user.id
                )
                message += "Я уведомлю вас, когда предсказание будет готово, или нажмите кнопку ниже."
            else:
                logger.warning("JobQueue is not available, skipping status check")
                message += "Пожалуйста, проверьте статус с помощью кнопки ниже или команды /status."

            await update.message.reply_text(message, reply_markup=reply_markup)

        except httpx.HTTPStatusError as e:
            error_detail = response.json().get('detail', 'Попробуйте снова')
            logger.error(f"Prediction HTTP error: {e}, Status: {response.status_code}, Detail: {error_detail}")
            await update.message.reply_text(f"Ошибка предсказания: {error_detail}")
        except httpx.RequestError as e:
            logger.error(f"Network error in predict_file: {str(e)}")
            await update.message.reply_text("Ошибка сети. Проверьте подключение и попробуйте снова.")
        except Exception as e:
            logger.error(f"Unexpected error in predict_file: {str(e)}")
            await update.message.reply_text(f"Произошла ошибка: {str(e)}. Попробуйте снова.")

    context.user_data.clear()
    return ConversationHandler.END

async def check_prediction_status(context: ContextTypes.DEFAULT_TYPE):
    """Периодически проверяет статус предсказания."""
    job = context.job
    prediction_id = job.data["prediction_id"]
    user_id = job.data["user_id"]
    token = user_tokens.get(user_id)
    if not token:
        logger.warning(f"No token found for user {user_id}, stopping status check")
        job.schedule_removal()
        return

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{API_BASE_URL}/predictions/{prediction_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            prediction = response.json()
            logger.info(f"Status check for prediction {prediction_id}: {prediction['status']}")
            if prediction["status"] in ["completed", "failed"]:
                result = prediction.get("result", "Ошибка: результат отсутствует")
                await context.bot.send_message(
                    chat_id=job.chat_id,
                    text=(
                        f"Предсказание {prediction_id} завершено!\n"
                        f"Статус: {prediction['status']}\n"
                        f"Результат: {result}"
                    )
                )
                job.schedule_removal()  # Останавливаем проверку
        except httpx.HTTPStatusError as e:
            error_detail = response.json().get('detail', 'Попробуйте снова')
            logger.error(f"Status check error for prediction {prediction_id}: {error_detail}")
            if response.status_code == 401:  # Токен истёк
                await context.bot.send_message(
                    chat_id=job.chat_id,
                    text="Сессия истекла. Пожалуйста, войдите снова с помощью /login."
                )
                job.schedule_removal()
        except Exception as e:
            logger.error(f"Unexpected error in status check for prediction {prediction_id}: {str(e)}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /status: проверяет статус предсказания."""
    if update.effective_user.id not in user_tokens:
        await update.message.reply_text("Пожалуйста, войдите с помощью /login.")
        return
    try:
        prediction_id = int(context.args[0])
        token = user_tokens[update.effective_user.id]
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE_URL}/predictions/{prediction_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            prediction = response.json()
            result = prediction.get("result", "Результат ещё не готов")
            await update.message.reply_text(
                f"Статус предсказания {prediction_id}:\n"
                f"Статус: {prediction['status']}\n"
                f"Результат: {result}"
            )
    except (IndexError, ValueError):
        await update.message.reply_text("Использование: /status <prediction_id>")
    except httpx.HTTPStatusError as e:
        await update.message.reply_text(f"Ошибка: {response.json().get('detail', 'Попробуйте снова')}")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /balance: показывает текущий баланс."""
    if update.effective_user.id not in user_tokens:
        await update.message.reply_text("Пожалуйста, войдите с помощью /login.")
        return
    token = user_tokens[update.effective_user.id]
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{API_BASE_URL}/balance",
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            data = response.json()
            await update.message.reply_text(f"Ваш баланс: {data['balance']} токенов")
        except httpx.HTTPStatusError as e:
            await update.message.reply_text(f"Ошибка: {response.json().get('detail', 'Попробуйте снова')}")

async def transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /transactions: показывает историю транзакций."""
    if update.effective_user.id not in user_tokens:
        await update.message.reply_text("Пожалуйста, войдите с помощью /login.")
        return
    token = user_tokens[update.effective_user.id]
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{API_BASE_URL}/transactions",
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            transactions = response.json()
            if not transactions:
                await update.message.reply_text("Транзакций пока нет.")
                return
            message = "История транзакций:\n"
            for t in transactions:
                message += f"ID: {t['id']}, Сумма: {t['amount']}, Описание: {t['description']}, Дата: {t['created_at']}\n"
            await update.message.reply_text(message)
        except httpx.HTTPStatusError as e:
            await update.message.reply_text(f"Ошибка: {response.json().get('detail', 'Попробуйте снова')}")

async def payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /payment: запрашивает сумму для пополнения."""
    if update.effective_user.id not in user_tokens:
        await update.message.reply_text("Пожалуйста, войдите с помощью /login.")
        return
    await update.message.reply_text("Введите сумму для пополнения (например, 5.0):")
    return PAYMENT

async def payment_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет запрос на пополнение баланса."""
    try:
        amount = float(update.message.text)
        token = user_tokens[update.effective_user.id]
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE_URL}/payment?amount={amount}",
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            user = response.json()
            await update.message.reply_text(f"Баланс пополнен! Новый баланс: {user['balance']} токенов")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Сумма должна быть числом (например, 5.0). Попробуйте снова:")
        return PAYMENT
    except httpx.HTTPStatusError as e:
        await update.message.reply_text(f"Ошибка: {response.json().get('detail', 'Попробуйте снова')}")
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет текущий диалог."""
    await update.message.reply_text("Действие отменено.")
    return ConversationHandler.END

async def models(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in user_tokens:
        await update.message.reply_text("Пожалуйста, войдите с помощью /login.")
        return
    token = user_tokens[update.effective_user.id]
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{API_BASE_URL}/models",
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            models = response.json()
            if not models:
                await update.message.reply_text("Модели пока недоступны.")
                return
            message = "Доступные модели:\n"
            for m in models:
                message += f"ID: {m['id']}, Название: {m['name']}, Стоимость: {m['cost']} токенов\n"
            await update.message.reply_text(message)
        except httpx.HTTPStatusError as e:
            await update.message.reply_text(f"Ошибка: {response.json().get('detail', 'Попробуйте снова')}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатия на инлайн-кнопку."""
    query = update.callback_query
    await query.answer()
    if query.data.startswith("status_"):
        try:
            prediction_id = int(query.data.replace("status_", ""))
            token = user_tokens.get(update.effective_user.id)
            if not token:
                await query.message.reply_text("Пожалуйста, войдите с помощью /login.")
                return
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{API_BASE_URL}/predictions/{prediction_id}",
                    headers={"Authorization": f"Bearer {token}"}
                )
                response.raise_for_status()
                prediction = response.json()
                result = prediction.get("result", "Результат ещё не готов")
                await query.message.reply_text(
                    f"Статус предсказания {prediction_id}:\n"
                    f"Статус: {prediction['status']}\n"
                    f"Результат: {result}"
                )
        except httpx.HTTPStatusError as e:
            await query.message.reply_text(f"Ошибка: {response.json().get('detail', 'Попробуйте снова')}")
        except Exception as e:
            logger.error(f"Error in button_callback: {str(e)}")
            await query.message.reply_text(f"Произошла ошибка: {str(e)}. Попробуйте снова.")

def main():
    """Запуск бота."""
    try:
        # Создаём Application
        builder = Application.builder().token(BOT_TOKEN)
        logger.info("Building Application with token")
        application = builder.build()
        logger.info(f"Application created: {application}")
        
        # Проверяем JobQueue
        if application.job_queue is None:
            logger.error("JobQueue is not initialized. Attempting manual initialization.")
            # Пробуем вручную создать JobQueue
            application.job_queue = JobQueue()
            application.job_queue.set_application(application)
            logger.info("Manually initialized JobQueue")
        
        # Проверяем, что JobQueue теперь доступен
        if application.job_queue is None:
            logger.error("Failed to initialize JobQueue. Configuration details:")
            logger.error(f"Application: {application}")
            logger.error(f"Bot token valid: {application.bot.token == BOT_TOKEN}")
            raise RuntimeError("JobQueue is not initialized. Check python-telegram-bot version (>=20.0) and configuration.")
        
        logger.info("JobQueue initialized successfully")
        application.add_handler(CommandHandler("models", models))

        # Обработчики диалогов
        register_conv = ConversationHandler(
            entry_points=[CommandHandler("register", register)],
            states={
                REGISTER_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_username)],
                REGISTER_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_password)],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
        )

        login_conv = ConversationHandler(
            entry_points=[CommandHandler("login", login)],
            states={
                LOGIN_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_username)],
                LOGIN_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_password)],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
        )

        predict_conv = ConversationHandler(
            entry_points=[CommandHandler("predict", predict)],
            states={
                PREDICT_MODEL_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, predict_model_id)],
                PREDICT_FILE: [MessageHandler(filters.Document.ALL, predict_file)],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
        )

        payment_conv = ConversationHandler(
            entry_points=[CommandHandler("payment", payment)],
            states={
                PAYMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_amount)],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
        )

        # Добавление обработчиков
        application.add_handler(register_conv)
        application.add_handler(login_conv)
        application.add_handler(predict_conv)
        application.add_handler(payment_conv)
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("status", status))
        application.add_handler(CommandHandler("balance", balance))
        application.add_handler(CommandHandler("transactions", transactions))
        application.add_handler(CallbackQueryHandler(button_callback))

        # Запуск бота
        application.run_polling()
    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}")
        raise


if __name__ == "__main__":
    main()