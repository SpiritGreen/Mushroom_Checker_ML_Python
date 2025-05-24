# Схема базы данных

## Таблицы

### Users (Пользователи)
Хранит информацию о пользователях и их балансе.
- `id`: INTEGER (PRIMARY KEY, AUTO_INCREMENT) — уникальный идентификатор пользователя.
- `username`: VARCHAR(255) (UNIQUE, INDEX) — имя пользователя.
- `email`: VARCHAR(255) (UNIQUE) — email пользователя.
- `hashed_password`: VARCHAR(255) — хэш пароля.
- `balance`: FLOAT (DEFAULT 10.0) — текущий баланс кредитов.
- `disabled`: BOOLEAN (DEFAULT False) — статус активности (True — отключён, False — активен).
- `created_at`: DATETIME — дата и время создания записи (по умолчанию текущая дата в UTC).

### Models (Модели)
Хранит данные о моделях машинного обучения.
- `id`: INTEGER (PRIMARY KEY, AUTO_INCREMENT, INDEX) — уникальный идентификатор модели.
- `name`: VARCHAR(255) (UNIQUE) — название модели.
- `cost`: FLOAT — стоимость использования модели в кредитах.
- `file_path`: VARCHAR(255) — путь к файлу модели на диске.

### Predictions (Предсказания)
Хранит информацию о предсказаниях, сделанных пользователями.
- `id`: INTEGER (PRIMARY KEY, AUTO_INCREMENT, INDEX) — уникальный идентификатор предсказания.
- `user_id`: INTEGER (FOREIGN KEY → Users.id) — ссылка на пользователя.
- `model_id`: INTEGER (FOREIGN KEY → Models.id) — ссылка на модель.
- `input_data`: JSON — входные данные для предсказания.
- `result`: JSON (NULLABLE) — результат предсказания.
- `status`: VARCHAR(255) (DEFAULT "pending") — статус выполнения ("pending", "completed", "failed").
- `created_at`: DATETIME — дата и время создания записи (по умолчанию текущая дата в UTC).

### Transactions (Транзакции)
Хранит историю операций с балансом.
- `id`: INTEGER (PRIMARY KEY, AUTO_INCREMENT, INDEX) — уникальный идентификатор транзакции.
- `user_id`: INTEGER (FOREIGN KEY → Users.id) — ссылка на пользователя.
- `amount`: FLOAT — сумма транзакции (положительная для пополнения, отрицательная для списания).
- `description`: VARCHAR(255) — описание транзакции (например, "Prediction using model RandomForest").
- `created_at`: DATETIME — дата и время создания записи (по умолчанию текущая дата в UTC).
- `prediction_id`: INTEGER (FOREIGN KEY → Predictions.id, NULLABLE) — ссылка на предсказание, если транзакция связана с ним.

## Примечания
- Баланс хранится в таблице `Users` и обновляется при операциях через `deduct_balance` и `increase_balance`.
- Транзакции связываются с предсказаниями через поле `prediction_id`, если это списание за предсказание.
- Все временные метки (`created_at`) используют UTC.