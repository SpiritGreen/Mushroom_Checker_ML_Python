import logging
from fastapi import HTTPException, status, Depends
from passlib.context import CryptContext
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta, timezone
from jose import jwt
from sqlalchemy.orm import Session
from models.user import User
from db.db_user import DBUser
from database import get_db

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Настройки JWT
SECRET_KEY = "secret-key"  # Секретный ключ для подписи JWT-токенов
ALGORITHM = "HS256"  # Алгоритм шифрования (HMAC SHA-256)
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # Время жизни токена в минутах

# Настройка хэширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")  # Использует bcrypt для хэширования 

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

def get_user(db: Session = Depends(get_db), username: str = None) -> Optional[User]:
    """
    Получает пользователя по имени из базы данных.

    Args:
        db (Session): Сессия SQLAlchemy для работы с БД.
        username (str): Имя пользователя.

    Returns:
        Optional[User]: Объект пользователя или None, если не найден.
    """
    db_user = db.query(DBUser).filter(DBUser.username == username).first()
    if db_user:
        return User(
            id=db_user.id,
            username=db_user.username,
            email=db_user.email,
            hashed_password=db_user.hashed_password,
            balance=db_user.balance,
            disabled=db_user.disabled,
            created_at=db_user.created_at
        )
    logger.warning(f"Пользователь не найден: {username}")
    return None

def authenticate_user(db: Session = Depends(get_db), username: str = None, password: str = None) -> Optional[User]:
    """
    Аутентифицирует пользователя по имени и паролю.

    Args:
        db (Session): Сессия SQLAlchemy для работы с БД.
        username (str): Имя пользователя.
        password (str): Пароль.

    Returns:
        Optional[User]: Объект пользователя или None, если аутентификация не удалась.
    """
    user = get_user(db, username)
    if not user or not verify_password(password, user.hashed_password):
        logger.error(f"Аутентификация провалена: Пользователь {username}")
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
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    logger.info(f"Создан токен для {data['sub']}, истекает: {expire.isoformat()}")
    return encoded_jwt

def register_user(db: Session = Depends(get_db), username: str = None, email: str = None, password: str = None) -> User:
    """
    Регистрирует нового пользователя в системе, сохраняя его в базе данных.

    Args:
        db (Session): Сессия SQLAlchemy для работы с БД.
        username (str): Имя пользователя, должно быть уникальным.
        email (str): Email пользователя, должен быть уникальным.
        password (str): Пароль пользователя, будет хэширован перед сохранением.

    Returns:
        User: Объект зарегистрированного пользователя в формате Pydantic-модели.

    Raises:
        HTTPException: Если пользователь с таким именем или email уже существует (status_code=400).
    """
    if db.query(DBUser).filter((DBUser.username == username) | (DBUser.email == email)).first():
        logger.error(f"Регистрация провалена: Пользователь {username} или email {email} уже существует")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь или email уже существует"
        )
    hashed_password = pwd_context.hash(password)
    db_user = DBUser(username=username, email=email, hashed_password=hashed_password, balance=10.0, disabled=False)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    logger.info(f"Пользователь {username} успешно зарегистрирован")
    return User(
        id=db_user.id,
        username=db_user.username,
        email=db_user.email,
        hashed_password=db_user.hashed_password,
        balance=db_user.balance,
        disabled=db_user.disabled,
        created_at=db_user.created_at
    )

def deduct_balance(db: Session = Depends(get_db), username: str = None, amount: float = None) -> User:
    """
    Списывает указанное количество кредитов с баланса пользователя.

    Args:
        db (Session): Сессия SQLAlchemy для работы с БД.
        username (str): Имя пользователя.
        amount (float): Сумма для списания.

    Returns:
        User: Обновлённый объект пользователя.

    Raises:
        HTTPException: Если пользователь не найден (404) или недостаточно средств (400).
    """
    db_user = db.query(DBUser).filter(DBUser.username == username).first()
    if not db_user:
        logger.error(f"Списание провалено: Пользователь {username} не найден")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    if db_user.balance < amount:
        logger.error(f"Списание провалено: Недостаточно средств у {username}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Недостаточно средств")
    db_user.balance -= amount
    db.commit()
    db.refresh(db_user)
    logger.info(f"Снято {amount} токенов у {username}. Новый баланс: {db_user.balance}")
    return User(
        id=db_user.id,
        username=db_user.username,
        email=db_user.email,
        hashed_password=db_user.hashed_password,
        balance=db_user.balance,
        disabled=db_user.disabled,
        created_at=db_user.created_at
    )