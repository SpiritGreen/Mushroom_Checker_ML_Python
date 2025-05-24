# Переменные
UVICORN_PID = uvicorn.pid
REDIS_PID = redis.pid
CELERY_WORKER_PID = celery_worker.pid
CELERY_FLOWER_PID = celery_flower.pid
BOT_PID = telegram_bot.pid

LOG_DIR = logs
UVICORN_LOG = $(LOG_DIR)/uvicorn.log
REDIS_LOG = $(LOG_DIR)/redis.log
CELERY_WORKER_LOG = $(LOG_DIR)/celery_worker.log
CELERY_FLOWER_LOG = $(LOG_DIR)/celery_flower.log
BOT_LOG = $(LOG_DIR)/telegram_bot.log
INIT_MODELS_LOG = $(LOG_DIR)/init_models.log
INSTALL_DEPS_LOG = $(LOG_DIR)/install_deps.log

# Путь к requirements.txt (экранируем пробелы)
REQUIREMENTS_FILE = ./requirements.txt

# Создание директории для логов
$(shell mkdir -p $(LOG_DIR))

# Цель по умолчанию
.PHONY: all
all: run

# Проверка установленных зависимостей
.PHONY: check_deps
check_deps:
	@echo "Checking dependencies..."
	@command -v redis-server >/dev/null 2>&1 || { echo "redis-server not found"; exit 1; }
	@command -v celery >/dev/null 2>&1 || { echo "celery not found"; exit 1; }
	@command -v uvicorn >/dev/null 2>&1 || { echo "uvicorn not found"; exit 1; }
	@python -c "import telegram" >/dev/null 2>&1 || { echo "python-telegram-bot not found"; exit 1; }

# Запуск всех сервисов
.PHONY: run
run: check_deps install_deps init_models redis celery_worker celery_flower uvicorn bot
	@echo "All services started. Use 'make stop' to terminate."

# Установка зависимостей
.PHONY: install_deps
install_deps:
	@echo "Installing dependencies from $(REQUIREMENTS_FILE)..."
	@if [ ! -f "$(REQUIREMENTS_FILE)" ]; then \
		echo "Error: $(REQUIREMENTS_FILE) not found"; \
		exit 1; \
	fi
	@command -v pip >/dev/null 2>&1 || { echo "pip not found"; exit 1; }
	@pip install -r "$(REQUIREMENTS_FILE)" > $(INSTALL_DEPS_LOG) 2>&1 || { echo "Failed to install dependencies"; cat $(INSTALL_DEPS_LOG); exit 1; }
	@echo "Dependencies installed successfully"

# Инициализация моделей
.PHONY: init_models
init_models:
	@echo "Initializing models..."
	@python init_models.py > $(INIT_MODELS_LOG) 2>&1 || { echo "Failed to initialize models"; exit 1; }

# Запуск redis-server
.PHONY: redis
redis:
	@echo "Checking redis-server..."
	@if ! pgrep -x "redis-server" > /dev/null; then \
		echo "Starting redis-server..."; \
		redis-server > $(REDIS_LOG) 2>&1 & echo $$! > $(REDIS_PID); \
	else \
		echo "redis-server already running, skipping..."; \
		echo "Existing PID: $$(pgrep -x redis-server)" >> $(REDIS_LOG); \
	fi

# Запуск uvicorn
.PHONY: uvicorn
uvicorn:
	@echo "Starting uvicorn..."
	@uvicorn main:app --reload > $(UVICORN_LOG) 2>&1 & echo $$! > $(UVICORN_PID)

# Запуск celery worker
.PHONY: celery_worker
celery_worker: redis
	@echo "Starting celery worker..."
	@celery -A celery_app worker --loglevel=info -E > $(CELERY_WORKER_LOG) 2>&1 & echo $$! > $(CELERY_WORKER_PID)

# Запуск celery flower
.PHONY: celery_flower
celery_flower: redis
	@echo "Starting celery flower..."
	@celery -A celery_app flower > $(CELERY_FLOWER_LOG) 2>&1 & echo $$! > $(CELERY_FLOWER_PID)

# Запуск telegram bot
.PHONY: bot
bot:
	@echo "Starting telegram bot..."
	@python telegram_bot.py > $(BOT_LOG) 2>&1 & echo $$! > $(BOT_PID)

# Остановка всех сервисов
.PHONY: stop
stop:
	@echo "Stopping all services..."
	@if [ -f $(UVICORN_PID) ]; then \
		kill -15 $$(cat $(UVICORN_PID)) && rm $(UVICORN_PID) || echo "Failed to stop uvicorn"; \
	fi
	@if [ -f $(CELERY_WORKER_PID) ]; then \
		kill -15 $$(cat $(CELERY_WORKER_PID)) && rm $(CELERY_WORKER_PID) || echo "Failed to stop celery worker"; \
	fi
	@if [ -f $(CELERY_FLOWER_PID) ]; then \
		kill -15 $$(cat $(CELERY_FLOWER_PID)) && rm $(CELERY_FLOWER_PID) || echo "Failed to stop celery flower"; \
	fi
	@if [ -f $(BOT_PID) ]; then \
		kill -15 $$(cat $(BOT_PID)) && rm $(BOT_PID) || echo "Failed to stop telegram bot"; \
	fi
	@echo "Attempting to stop redis-server..."
	@if [ -f $(REDIS_PID) ]; then \
		sudo kill -15 $$(cat $(REDIS_PID)) && rm $(REDIS_PID) || echo "Failed to stop redis-server (check permissions)"; \
	fi
	@if pgrep -x "redis-server" > /dev/null; then \
		echo "Found running redis-server, attempting to stop with sudo..."; \
		sudo pkill -15 -x redis-server || echo "Failed to stop redis-server (may require manual intervention)"; \
	else \
		echo "No redis-server process found"; \
	fi
	@echo "All services stopped."

# Очистка логов и PID-файлов
.PHONY: clean
clean:
	@echo "Cleaning up..."
	@rm -rf $(LOG_DIR) *.pid

# Перезапуск
.PHONY: restart
restart: stop run
	@echo "All services restarted."