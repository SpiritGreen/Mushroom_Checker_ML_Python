from sqlalchemy.orm import Session
from db.db_user import DBUser
from db.db_prediction import DBPrediction
from db.db_transaction import DBTransaction
from db.db_model import DBModel
from passlib.context import CryptContext
from datetime import datetime, timezone
from typing import List, Optional

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_user(db: Session, username: str, email: str, password: str) -> DBUser:
    """
    Создаёт нового пользователя в базе данных.

    Args:
        db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.
        username (str): Уникальное имя пользователя.
        email (str): Уникальный email пользователя.
        password (str): Пароль пользователя (будет хэширован).

    Returns:
        DBUser: Объект созданного пользователя.

    Raises:
        None: Ошибки обрабатываются на уровне вызывающего кода.
    """
    hashed_password = pwd_context.hash(password)
    db_user = DBUser(
        username=username,
        email=email,
        hashed_password=hashed_password,
        balance=10.0,
        disabled=False,
        created_at=datetime.now(timezone.utc)
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user_by_username(db: Session, username: str) -> Optional[DBUser]:
    """
    Получает пользователя по имени из базы данных.

    Args:
        db (Session): Сессия SQLAlchemy.
        username (str): Имя пользователя для поиска.

    Returns:
        Optional[DBUser]: Объект пользователя или None, если пользователь не найден.
    """
    return db.query(DBUser).filter(DBUser.username == username).first()

def update_user_balance(db: Session, username: str, amount: float) -> Optional[DBUser]:
    """
    Обновляет баланс пользователя, добавляя или вычитая указанную сумму.

    Args:
        db (Session): Сессия SQLAlchemy.
        username (str): Имя пользователя.
        amount (float): Сумма для добавления (положительная) или списания (отрицательная).

    Returns:
        Optional[DBUser]: Обновлённый объект пользователя или None, если пользователь не найден.
    """
    db_user = db.query(DBUser).filter(DBUser.username == username).first()
    if db_user:
        db_user.balance = db_user.balance + amount
        db.commit()
        db.refresh(db_user)
    return db_user

def create_prediction(db: Session, user_id: int, model_id: int, input_data: List[dict], status: str = "pending") -> DBPrediction:
    """
    Создаёт запись о предсказании в базе данных.

    Args:
        db (Session): Сессия SQLAlchemy.
        user_id (int): Идентификатор пользователя, инициировавшего предсказание.
        model_id (int): Идентификатор модели машинного обучения.
        input_data (List[dict]): Входные данные для предсказания в формате списка словарей.
        status (str, optional): Статус предсказания (по умолчанию "pending").

    Returns:
        DBPrediction: Объект созданной записи предсказания.
    """
    db_prediction = DBPrediction(
        user_id=user_id,
        model_id=model_id,
        input_data=input_data,
        status=status,
        created_at=datetime.now(timezone.utc)
    )
    db.add(db_prediction)
    db.commit()
    db.refresh(db_prediction)
    return db_prediction

def update_prediction_result(db: Session, prediction_id: int, result: List[str], status: str) -> Optional[DBPrediction]:
    """
    Обновляет результат и статус предсказания в базе данных.

    Args:
        db (Session): Сессия SQLAlchemy.
        prediction_id (int): Идентификатор предсказания.
        result (List[str]): Результат предсказания в формате списка строк.
        status (str): Новый статус предсказания ("completed" или "failed").

    Returns:
        Optional[DBPrediction]: Обновлённая запись предсказания или None, если запись не найдена.
    """
    db_prediction = db.query(DBPrediction).filter(DBPrediction.id == prediction_id).first()
    if db_prediction:
        db_prediction.result = result
        db_prediction.status = status
        db.commit()
        db.refresh(db_prediction)
    return db_prediction

def create_transaction(db: Session, user_id: int, amount: float, description: str) -> DBTransaction:
    """
    Создаёт запись о транзакции в базе данных.

    Args:
        db (Session): Сессия SQLAlchemy.
        user_id (int): Идентификатор пользователя.
        amount (float): Сумма транзакции (отрицательная для списания).
        description (str): Описание транзакции.

    Returns:
        DBTransaction: Объект созданной записи транзакции.
    """
    db_transaction = DBTransaction(
        user_id=user_id,
        amount=amount,
        description=description,
        created_at=datetime.now(timezone.utc)
    )
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction

def get_model_by_id(db: Session, model_id: int) -> Optional[DBModel]:
    """
    Получает модель машинного обучения по её идентификатору.

    Args:
        db (Session): Сессия SQLAlchemy.
        model_id (int): Идентификатор модели.

    Returns:
        Optional[DBModel]: Объект модели или None, если модель не найдена.
    """
    return db.query(DBModel).filter(DBModel.id == model_id).first()