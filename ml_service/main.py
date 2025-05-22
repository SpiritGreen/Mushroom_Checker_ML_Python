import json
from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from typing import Optional
from sqlalchemy.orm import Session
import os

from services.auth import (
    User, 
    Token, 
    TokenData, 
    authenticate_user, 
    create_access_token, 
    register_user, 
    get_user, 
    deduct_balance, 
    increase_balance)

from services.prediction_service import read_input_file, make_prediction, get_available_models, validate_input_data
from models.transaction import Transaction
from services.db_operations import create_transaction
from models.prediction import Prediction
from models.model import Model
from datetime import timedelta, datetime, timezone
from database import engine, Base, get_db
from celery_app import app as celery_app
from services.db_operations import create_prediction

# SQLAlchemy-модели
from db.db_user import DBUser
from db.db_model import DBModel
from db.db_prediction import DBPrediction
from db.db_transaction import DBTransaction

import logging
logger = logging.getLogger(__name__)

# Настройки
SECRET_KEY = "1c56bc27814669ed3c54fb2729a9523fa99b30d31d9f5f549cd3525cd0e8c34a"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

MAX_FILE_SIZE = 200 * 1024 * 1024  # 200 MB

# Создание таблиц при запуске
Base.metadata.create_all(bind=engine)

# app = FastAPI()
app = FastAPI(
    title="ML Service API",
    description="API для работы с ML-сервисом: аутентификация, предсказания и управление счетом.",
    version="1.0.0",
    openapi_tags=[
        {"name": "auth", "description": "Аутентификация и управление пользователями"},
        {"name": "models", "description": "Получение списка доступных ML-моделей"},
        {"name": "predictions", "description": "Запрос и получение предсказаний"},
        {"name": "account", "description": "Управление балансом и транзакциями"},
    ]
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Зависимость для аутентификации и получения текущего пользователя
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Аутентифицирует пользователя по JWT-токену и возвращает объект User.

    Args:
        token (str): JWT-токен из заголовка Authorization.
        db (Session): Сессия SQLAlchemy для доступа к базе данных.

    Returns:
        User: Объект текущего пользователя.

    Raises:
        HTTPException: Если токен недействителен или пользователь не найден (401).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось проверить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user(db, token_data.username)
    if user is None:
        raise credentials_exception
    return user

# Регистрация нового пользователя
@app.post("/register", response_model=User, tags=["auth"])
async def register(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Регистрирует нового пользователя в системе.

    Args:
        form_data (OAuth2PasswordRequestForm): Данные формы с именем пользователя и паролем.
        db (Session): Сессия SQLAlchemy для доступа к базе данных.

    Returns:
        User: Объект зарегистрированного пользователя.

    Raises:
        HTTPException: Если пользователь с таким именем или email уже существует (400).
    """
    user = register_user(db, form_data.username, f"{form_data.username}@example.com", form_data.password)
    return user

# Аутентификация пользователя
@app.post("/token", response_model=Token, tags=["auth"])
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Аутентифицирует пользователя и выдает JWT-токен.

    Args:
        form_data (OAuth2PasswordRequestForm): Данные формы с именем пользователя и паролем.
        db (Session): Сессия SQLAlchemy для доступа к базе данных.

    Returns:
        dict: Словарь с access_token и типом токена ("bearer").

    Raises:
        HTTPException: Если имя пользователя или пароль неверны (401).
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Получение текущего пользователя
# Эндпоинт для получения данных текущего пользователя
@app.get("/users/me", response_model=User, tags=["auth"])
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Возвращает данные текущего аутентифицированного пользователя.

    Args:
        current_user (User): Объект пользователя, полученный через get_current_user.

    Returns:
        User: Данные пользователя (username, balance и т.д.).
    """
    return current_user

# Получение списка доступных моделей
@app.get("/models", response_model=list[Model], tags=["models"])
async def get_models(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Возвращает список всех доступных ML-моделей для предсказаний.

    Args:
        current_user (User): Аутентифицированный пользователь.
        db (Session): Сессия SQLAlchemy для доступа к базе данных.

    Returns:
        list[Model]: Список объектов моделей с их ID, именем и стоимостью.

    Raises:
        HTTPException: Если пользователь не аутентифицирован (401).
    """
    return get_available_models(db)

# Запрос на получение предсказания
@app.post("/predict", response_model=Prediction, tags=["predictions"])
async def predict(
    model_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Запускает асинхронное предсказание с использованием ML-модели.

    Args:
        model_id (int): ID выбранной ML-модели.
        file (UploadFile): Загружаемый файл (CSV или XLSX) с входными данными.
        current_user (User): Объект текущего пользователя для аутентификации.
        db (Session): Сессия SQLAlchemy для доступа к базе данных.

    Returns:
        Prediction: Объект предсказания с текущим статусом ("pending").

    Raises:
        HTTPException: Если файл отсутствует, имеет неверный формат, модель не найдена,
                       баланс недостаточен или пользователь не аутентифицирован (400, 401).
    """
    if file.size is None or file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large or invalid, max 200MB. Please upload a valid CSV or XLSX file.")

    # Проверка расширения файла
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided. Please upload a CSV or XLSX file.")
    
    file_type = file.filename.split(".")[-1].lower()
   
    if file_type not in ["csv", "xlsx"]:
        raise HTTPException(status_code=400, detail=f"Unsupported file format: {file_type}. Use CSV or XLSX.")
    
    # Чтение файла
    content = await file.read()
    input_data = read_input_file(content, file_type)

    # Валидация входных данных
    validate_input_data(input_data)

    # Проверка модели
    models = get_available_models(db)
    selected_model = next((m for m in models if m.id == model_id), None)
    if not selected_model:
        raise HTTPException(status_code=400, detail=f"Model ID {model_id} not found. Check available models with GET /models.")
    
    # Проверка существования файла модели
    model_path = os.path.join("ml_models", "trained_ml_models", f"{selected_model.name}.pkl")
    if not os.path.exists(model_path):
        raise HTTPException(status_code=500, detail=f"Model file not found: {model_path}")
    
    # Проверка баланса
    if current_user.balance < selected_model.cost:
        raise HTTPException(status_code=400, detail=f"Insufficient balance: {current_user.balance}. Required: {selected_model.cost}. Increase balance via POST /payment.")
    
    # Создание записи предсказания со статусом "pending"
    db_prediction = create_prediction(
        db,
        user_id=current_user.id,
        model_id=model_id,
        input_data=input_data,
        status="pending"
    )

    # Списание токенов и запись транзакции
    deduct_balance(db, current_user.username, selected_model.cost)
    create_transaction(
        db,
        user_id=current_user.id,
        amount=-selected_model.cost,
        description=f"Prediction using model {selected_model.name}"
    )

    # Запуск асинхронной задачи
    try:
        task = celery_app.send_task("services.tasks.predict_task", args=[db_prediction.id])
        logger.info(f"Задача отправлена: predict_task with prediction_id={db_prediction.id}, task_id={task.id}")
    except Exception as e:
        logger.error(f"Не удалось отправить задачу для prediction_id={db_prediction.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to queue task: {str(e)}")
    
    # Возвращаем объект Prediction с текущим статусом
    return Prediction(
        id=db_prediction.id,
        user_id=db_prediction.user_id,
        model_id=db_prediction.model_id,
        input_data=db_prediction.input_data,
        result=db_prediction.result,
        status=db_prediction.status,
        created_at=db_prediction.created_at,
        task_id=str(task.id)
    )

# Получение статуса конкретного предсказания
@app.get("/predictions/{prediction_id}", tags=["predictions"])
def get_prediction(prediction_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Получение статуса и результата конкретного предсказания.

    Этот эндпоинт позволяет аутентифицированным пользователям получить информацию о предсказании
    по его идентификатору. Возвращает идентификатор, статус и результат предсказания, если он доступен.

    Аргументы:
        - prediction_id (int): ID предсказания.
        - current_user (User): Аутентифицированный пользователь.
        - db (Session): Сессия SQLAlchemy.

    Возвращает:
        - Prediction: Объект предсказания.

    Исключения:
    - HTTPException(404): Если предсказание с указанным ID не найдено.
    - HTTPException(401): Если пользователь не аутентифицирован или токен недействителен.

    Пример:
    - GET /predictions/1
      Ответ:
      {
          "id": 1,
          "status": "completed",
          "result": ["p", "e"]
      }
    """

    prediction = db.query(DBPrediction).filter(
        DBPrediction.id == prediction_id,
        DBPrediction.user_id == current_user.id
    ).first()

    if not prediction:
        raise HTTPException(status_code=404, detail=f"Prediction ID {prediction_id} not found or not owned by user.")
    
    logger.debug(f"Retrieved prediction {prediction_id} for user {current_user.username}")
    
    result = []
    if prediction.result is not None:
        if isinstance(prediction.result, str):
            try:
                result = json.loads(prediction.result)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse prediction.result: {prediction.result}, error: {str(e)}")
                raise HTTPException(status_code=500, detail="Invalid JSON in prediction result")
        elif isinstance(prediction.result, (list, dict)):
            result = prediction.result
        else:
            logger.error(f"Unexpected type for prediction.result: {type(prediction.result)}")
            raise HTTPException(status_code=500, detail="Invalid prediction result type")
    
    logger.debug(f"Parsed result: {result}")

    return Prediction(
        id=prediction.id,
        user_id=prediction.user_id,
        model_id=prediction.model_id,
        input_data=prediction.input_data,
        result=result,
        status=prediction.status,
        created_at=prediction.created_at
    )

# Пополнение счета аккаунта
@app.post("/payment", response_model=User, tags=["account"])
async def payment(
    amount: float,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Пополняет баланс текущего пользователя.

    Args:
        amount (float): Сумма для пополнения.
        current_user (User): Текущий аутентифицированный пользователь.
        db (Session): Сессия SQLAlchemy.

    Returns:
        User: Обновлённый объект пользователя с новым балансом.

    Raises:
        HTTPException: Если сумма некорректна или пользователь не найден.
    """
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Сумма должна быть положительной")
    updated_user = increase_balance(db, current_user.username, amount)
    logger.info(f"Пользователь {current_user.username} пополнил баланс на {amount}")
    create_transaction(
        db,
        user_id=current_user.id,
        amount=amount,
        description=f"Increase balance by {amount}"
    )
    return updated_user

# Получение текущего баланса
@app.get("/balance", tags=["account"])
async def get_balance(current_user: User = Depends(get_current_user)):
    """
    Возвращает текущий баланс пользователя.

    Args:
        current_user (User): Аутентифицированный пользователь.

    Returns:
        dict: Словарь с текущим балансом.

    Raises:
        HTTPException: Если пользователь не аутентифицирован.
    """
    logger.info(f"User {current_user.username} checked balance: {current_user.balance}")
    return {"balance": current_user.balance}

@app.get("/transactions", response_model=list[Transaction], tags=["account"])
async def get_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Возвращает историю транзакций пользователя.

    Args:
        current_user (User): Аутентифицированный пользователь.
        db (Session): Сессия SQLAlchemy.

    Returns:
        list[Transaction]: Список транзакций пользователя.

    Raises:
        HTTPException: Если пользователь не аутентифицирован.
    """
    transactions = db.query(DBTransaction).filter(DBTransaction.user_id == current_user.id).all()
    logger.info(f"User {current_user.username} retrieved transaction history")
    return [Transaction(
        id=t.id,
        user_id=t.user_id,
        amount=t.amount,
        description=t.description,
        created_at=t.created_at
    ) for t in transactions]

