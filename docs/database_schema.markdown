# Схема базы данных

     ## Таблицы

     ### Users (Пользователи)
     Хранит информацию о пользователях и их баланс.
     - `id`: INTEGER (PRIMARY KEY, AUTO_INCREMENT) — уникальный идентификатор пользователя.
     - `username`: VARCHAR(50) (UNIQUE) — имя пользователя.
     - `email`: VARCHAR(100) (UNIQUE) — email пользователя.
     - `hashed_password`: VARCHAR(255) — хэш пароля.
     - `balance`: DECIMAL(10,2) — текущий баланс кредитов (по умолчанию 10.00).
     - `disabled`: BOOLEAN — статус активности (True — отключён, False — активен).
     - `created_at`: DATETIME — дата и время создания записи.

     ### Models (Модели)
     Хранит данные о моделях машинного обучения.
     - `id`: INTEGER (PRIMARY KEY, AUTO_INCREMENT) — уникальный идентификатор модели.
     - `name`: VARCHAR(50) — название модели.
     - `cost`: DECIMAL(10,2) — стоимость использования модели в кредитах.
     - `file_path`: VARCHAR(255) — путь к файлу модели на диске.

     ### Predictions (Предсказания)
     Хранит информацию о предсказаниях, сделанных пользователями.
     - `id`: INTEGER (PRIMARY KEY, AUTO_INCREMENT) — уникальный идентификатор предсказания.
     - `user_id`: INTEGER (FOREIGN KEY → Users.id) — ссылка на пользователя.
     - `model_id`: INTEGER (FOREIGN KEY → Models.id) — ссылка на модель.
     - `input_data`: JSON — входные данные для предсказания.
     - `result`: JSON — результат предсказания.
     - `status`: VARCHAR(20) — статус выполнения ("pending", "completed", "failed").
     - `created_at`: DATETIME — дата и время создания записи.

     ### Transactions (Транзакции)
     Хранит историю операций с балансом.
     - `id`: INTEGER (PRIMARY KEY, AUTO_INCREMENT) — уникальный идентификатор транзакции.
     - `user_id`: INTEGER (FOREIGN KEY → Users.id) — ссылка на пользователя.
     - `amount`: DECIMAL(10,2) — сумма транзакции (положительная или отрицательная).
     - `description`: VARCHAR(255) — описание транзакции (например, "Списание за предсказание").
     - `created_at`: DATETIME — дата и время создания записи.

     ## Примечания
     - Баланс хранится в таблице `Users` и обновляется при транзакциях.