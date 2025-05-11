# Mushroom Checker

  Учебный проект для курса "Практикум по созданию ML-сервисов на Python"

  ## Структура проекта

  - `main.py`: Входная точка для запуска приложения.
  - `services/`: Бизнес-логика для регистрации и аутентификации пользователей и получения предсказаний ML-моделей.
  - `models/`: Pydantic модели.
  - `docs/`: Документация и схема.

  ## Запуск

  1. Клонирование репозитория:
     ```bash
     git clone https://github.com/SpiritGreen/Mushroom_Checker_ML_Python.git
     cd Mushroom_Checker_ML_Python
     ```

  2. Создание виртуального пространства:
     ```bash
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```

  3. Установка зависимостей:
     ```bash
     pip install -r requirements.txt
     ```

  4. Запуск сервера:
      1. Откройте терминал.
      2. Перейдите в директорию `ml_service`
      3. Запустите `Makefile`:
         ```bash
         make run
         ```
      
      Также можно воспользоваться этой командой:
         ```bash
         uvicorn main:app --host 0.0.0.0 --port 8000 --reload
         ```

  ## Использование

  - Регистрация пользователя: `POST /register`
  - Получение токена: `POST /token`
  - Получение данных текущего пользователя: `GET /users/me`
  - Получение списка доступных моделей: `GET /models`
  - Получение предсказания: `POST /predict?model_id=<id>`