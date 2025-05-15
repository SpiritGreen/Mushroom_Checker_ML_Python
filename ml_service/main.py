from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from typing import Optional
from pydantic import BaseModel
from services.auth import User, Token, TokenData, authenticate_user, create_access_token, register_user, get_user, deduct_balance
from services.prediction_service import read_input_file, make_prediction, get_available_models
from models.prediction import Prediction
from models.model import Model
from datetime import timedelta, datetime, timezone
from database import engine, Base

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

async def get_current_user(token: str = Depends(oauth2_scheme)):
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
    user = get_user(token_data.username)
    if user is None:
        raise credentials_exception
    return user

# Регистрация нового пользователя
@app.post("/register", response_model=User)
async def register(form_data: OAuth2PasswordRequestForm = Depends()):
    user = register_user(form_data.username, f"{form_data.username}@example.com", form_data.password)
    return user

# Аутентификация пользователя
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
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
@app.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

# Получение списка доступных моделей
@app.get("/models", response_model=list[Model])
async def get_models(current_user: User = Depends(get_current_user)):
    return get_available_models()

@app.post("/predict", response_model=Prediction)
async def predict(
    model_id: int,
    file: UploadFile = File(...), 
    current_user: User = Depends(get_current_user)):
    # Проверка расширения файла
    file_type = file.filename.split(".")[-1].lower()
    if file_type not in ["csv", "xlsx"]:
        raise HTTPException(status_code=400, detail="Only CSV or XLSX files are supported")
    
    # Чтение файла
    content = await file.read()
    input_data = read_input_file(content, file_type)

    # Проверка модели
    models = get_available_models()
    selected_model = next((m for m in models if m.id == model_id), None)
    if not selected_model:
        raise HTTPException(status_code=400, detail="Invalid model ID")
    
    # Проверка баланса
    if current_user.balance < selected_model.cost:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
    # Создание предсказания
    prediction = Prediction(
        user_id=current_user.id,
        model_id=model_id,  
        input_data=input_data,
        status="pending",
        created_at=datetime.now(timezone.utc)
    )
    
    # Выполнение предсказания
    prediction = make_prediction(prediction)

    # Списание токенов
    deduct_balance(current_user.username, selected_model.cost)

    return prediction