import logging
from fastapi import HTTPException, status
from passlib.context import CryptContext
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta, timezone
from jose import jwt
from models.user import User

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Настройки JWT
SECRET_KEY = "secret-key"  # Секретный ключ для подписи JWT-токенов
ALGORITHM = "HS256"  # Алгоритм шифрования (HMAC SHA-256)
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # Время жизни токена в минутах

# Настройка хэширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")  # Использует bcrypt для хэширования 

# Временное хранилище пользователей (заменится БД)
# db = {
#     "testuser": {
#         "id": 1,
#         "username": "testuser",
#         "email": "testuser@example.com",
#         "hashed_password": pwd_context.hash("password123"),
#         "balance": 10.0,
#         "disabled": False,
#         "created_at": datetime.now(timezone.utc)
#     }
# }

db = {}

class Token(BaseModel):
    access_token: str  # JWT-токен, тип bearer
    token_type: str  # Тип токена

class TokenData(BaseModel):
    username: Optional[str] = None  # Данные, которые удалось извлечь из токена

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверяет соответствие введённого пароля хэшированному.

    Args:
        plain_password (str): Введённый пароль.
        hashed_password (str): Хэшированный пароль из базы.

    Returns:
        bool: True, если пароли совпадают, иначе False.
    """
    return pwd_context.verify(plain_password, hashed_password)

def get_user(username: str) -> Optional[User]:
    """
    Получает пользователя по имени из базы данных.

    Args:
        username (str): Имя пользователя.

    Returns:
        Optional[User]: Объект пользователя или None, если не найден.
    """
    if username in db:
        user_dict = db[username]
        return User(**user_dict)
    logger.warning(f"Пользователь не найден: {username}")
    return None

def authenticate_user(username: str, password: str) -> Optional[User]:
    """
    Аутентифицирует пользователя по имени и паролю.

    Args:
        username (str): Имя пользователя.
        password (str): Пароль.

    Returns:
        Optional[User]: Объект пользователя или None, если аутентификация не удалась.
    """
    user = get_user(username)
    if not user:
        logger.error(f"Аутентификация провалена: Пользователь {username} не найден")
        return None
    if not verify_password(password, user.hashed_password):
        logger.error(f"Аутентификация провалена: Неправильный пароль для пользователя {username}")
        return None
    logger.info(f"Пользователь {username} успешно аутентифицирован")
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Создаёт JWT-токен для аутентификации.

    Args:
        data (dict): Данные для кодирования в токен (например, username).
        expires_delta (timedelta): Время жизни токена.

    Returns:
        str: Закодированный JWT-токен.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    logger.info(f"Создан токен для {data['sub']}, истекает: {expire.isoformat()}, сейчас {datetime.now(timezone.utc)}")
    return encoded_jwt

def register_user(username: str, email: str, password: str) -> User:
    """
    Регистрирует нового пользователя в системе.

    Args:
        username (str): Имя пользователя.
        email (str): Email пользователя.
        password (str): Пароль пользователя.

    Returns:
        User: Объект зарегистрированного пользователя.

    Raises:
        HTTPException: Если пользователь с таким именем уже существует.
    """
    if username in db:
        logger.error(f"Регистрация провалена: Пользователь {username} уже существует")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь уже существует"
        )
    
    user_id = len(db) + 1
    hashed_password = pwd_context.hash(password)

    user = User(
        id=user_id,
        username=username,
        email=email,
        hashed_password=hashed_password,
        balance=10.0,  # Бонусные кредиты
        disabled=False,
        created_at=datetime.now(timezone.utc)
    )
    db[username] = user.model_dump()
    logger.info(f"Пользователь {username} успешно зарегистрирован")
    return user

def deduct_balance(username: str, amount: float) -> User:
    """
    Списывает указанное количество кредитов с баланса пользователя.

    Args:
        username (str): Имя пользователя.
        amount (float): Сумма для списания.

    Returns:
        User: Обновлённый объект пользователя.

    Raises:
        HTTPException: Если пользователь не найден или недостаточно средств.
    """
    user = get_user(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.balance < amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    user.balance -= amount
    db[username]["balance"] = user.balance
    logger.info(f"Сняли {amount} токенов у {username}. Новый баланс: {user.balance}")
    return user