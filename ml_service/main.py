from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from typing import Optional
from sqlalchemy.orm import Session
from services.auth import User, Token, TokenData, authenticate_user, create_access_token, register_user, get_user, deduct_balance
from services.prediction_service import read_input_file, make_prediction, get_available_models
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

# Настройки
SECRET_KEY = "secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Создание таблиц при запуске
Base.metadata.create_all(bind=engine)

app = FastAPI()

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
@app.post("/register", response_model=User)
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
@app.post("/token", response_model=Token)
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
@app.get("/users/me", response_model=User)
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
@app.get("/models", response_model=list[Model])
async def get_models(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Возвращает список доступных ML-моделей.

    Args:
        current_user (User): Объект текущего пользователя для аутентификации.
        db (Session): Сессия SQLAlchemy для доступа к базе данных.

    Returns:
        list[Model]: Список объектов моделей с их ID, именем и стоимостью.

    Raises:
        HTTPException: Если пользователь не аутентифицирован (401).
    """
    return get_available_models(db)

@app.post("/predict", response_model=Prediction)
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
    # Проверка расширения файла
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    file_type = file.filename.split(".")[-1].lower()
   
    if file_type not in ["csv", "xlsx"]:
        raise HTTPException(status_code=400, detail="Only CSV or XLSX files are supported")
    
    # Чтение файла
    content = await file.read()
    input_data = read_input_file(content, file_type)

    # Проверка модели
    models = get_available_models(db)
    selected_model = next((m for m in models if m.id == model_id), None)
    if not selected_model:
        raise HTTPException(status_code=400, detail="Invalid model ID")
    
    # Проверка баланса
    if current_user.balance < selected_model.cost:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
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
    celery_app.send_task("services.tasks.predict_task", args=[db_prediction.id])
    
    # Возвращаем объект Prediction с текущим статусом
    return Prediction(
        id=db_prediction.id,
        user_id=db_prediction.user_id,
        model_id=db_prediction.model_id,
        input_data=db_prediction.input_data,
        result=db_prediction.result,
        status=db_prediction.status,
        created_at=db_prediction.created_at
    )