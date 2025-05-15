import pytest
import sys
import os
import pandas as pd
import io
from unittest.mock import patch
from sqlalchemy.sql import text
from sqlalchemy import inspect

# Попытка починить импорты
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app
from services.auth import create_access_token
from services.db_operations import create_user, update_user_balance
from db.db_user import DBUser
from db.db_model import DBModel
from db.db_prediction import DBPrediction
from db.db_transaction import DBTransaction
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from database import Base, get_db
from datetime import timedelta
# Импортируем все модели для создания таблиц
from models.user import User
from models.model import Model
from models.prediction import Prediction

# Фикстура для SQLite в памяти
@pytest.fixture(scope="function")
def test_db():    
    # Не слишком хороший метод, но только так сработали тесты
    # в тестах в какой-то момент терялся доступ к таблице в памяти
    engine = create_engine("sqlite:///ml_service.db", connect_args={"check_same_thread": False})
    # engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    # Отладка: проверяем зарегистрированные таблицы
    print("Registered tables in Base.metadata:", list(Base.metadata.tables.keys()))

    # Создаём все таблицы
    Base.metadata.create_all(bind=engine)

    # Отладка: проверяем созданные таблицы
    inspector = inspect(engine)
    print("Tables in database:", inspector.get_table_names())

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    # Отладка: проверяем, что сессия видит таблицу users
    try:
        session.execute(text("SELECT 1 FROM users LIMIT 1"))
    except Exception as e:
        print("Session check for users table failed:", str(e))

    yield session
    session.rollback()
    session.close()
    Base.metadata.drop_all(bind=engine) # Очистка базы после каждого теста

# Фикстура для клиента FastAPI
@pytest.fixture
def client(test_db):
    def override_get_db():
        try:
            yield test_db
        finally:
            test_db.rollback()
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()

# Фикстура для зарегистрированного пользователя
@pytest.fixture
def registered_user(client, test_db):
    # Отладка: проверяем, что сессия test_db используется
    print("Creating user with session:", test_db)

    create_user(test_db, username="testuser", email="testuser@example.com", password="password123")
    token_response = client.post("/token", data={"username": "testuser", "password": "password123"})
    token = token_response.json()["access_token"]
    return {"username": "testuser", "token": token}

    # Тест для проверки создания таблиц
def test_tables_created(test_db):
    # Проверяем, что таблица 'users' существует
    result = test_db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")).fetchone()
    assert result is not None, "Таблица 'users' не была создана"
    
    # Проверяем, что таблица 'models' существует
    result = test_db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='models'")).fetchone()
    assert result is not None, "Таблица 'models' не была создана"

def test_register(client, test_db):
    response = client.post("/register", data={"username": "testuser", "password": "password123", "email": "testuser@example.com"})
    assert response.status_code == 200
    assert response.json()["username"] == "testuser"
    assert response.json()["balance"] == 10.0

def test_register_existing_user(client, test_db):
    create_user(test_db, username="testuser", email="testuser@example.com", password="password123")
    response = client.post("/register", data={"username": "testuser", "password": "password123", "email": "testuser@example.com"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Пользователь или email уже существует"

def test_token(client, test_db):
    create_user(test_db, username="testuser", email="testuser@example.com", password="password123")
    response = client.post("/token", data={"username": "testuser", "password": "password123"})
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

def test_token_invalid_credentials(client, test_db):
    create_user(test_db, username="testuser", email="testuser@example.com", password="password123")
    response = client.post("/token", data={"username": "testuser", "password": "wrongpassword"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Неверное имя пользователя или пароль"

def test_token_nonexistent_user(client, test_db):
    response = client.post("/token", data={"username": "nonexistent", "password": "password123"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Неверное имя пользователя или пароль"

def test_token_expired(client, test_db):
    create_user(test_db, username="testuser", email="testuser@example.com", password="password123")
    expired_token = create_access_token(
        data={"sub": "testuser"},
        expires_delta=timedelta(seconds=-1)
    )
    response = client.get("/users/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Не удалось проверить учетные данные"

def test_get_models(client, test_db, registered_user):
    test_db.add(DBModel(id=1, name="RandomForest", cost=1.0, file_path="ml_models/trained_ml_models/RandomForest.pkl"))
    test_db.commit()
    response = client.get("/models", headers={"Authorization": f"Bearer {registered_user['token']}"})
    assert response.status_code == 200
    assert len(response.json()) >= 1
    assert response.json()[0]["name"] == "RandomForest"

def test_get_models_invalid_token(client):
    response = client.get("/models", headers={"Authorization": "Bearer invalid_token"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Не удалось проверить учетные данные"

def test_users_me(client, registered_user):
    response = client.get("/users/me", headers={"Authorization": f"Bearer {registered_user['token']}"})
    assert response.status_code == 200
    assert response.json()["username"] == "testuser"
    assert response.json()["balance"] == 10.0

def test_users_me_invalid_token(client):
    response = client.get("/users/me", headers={"Authorization": "Bearer invalid_token"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Не удалось проверить учетные данные"

def test_predict_csv(client, test_db, registered_user, tmp_path):
    test_db.add(DBModel(id=1, name="RandomForest", cost=1.0, file_path="ml_models/trained_ml_models/RandomForest.pkl"))
    test_db.commit()
    test_csv = """
cap-diameter,cap-shape,cap-surface,cap-color,does-bruise-or-bleed,gill-attachment,gill-spacing,gill-color,stem-height,stem-width,stem-surface,stem-color,has-ring,ring-type,habitat,season
5.0,convex,scaly,brown,false,adnate,close,white,6.0,2.0,fibrous,white,true,pendant,forest,spring
"""
    csv_file = tmp_path / "test_data.csv"
    csv_file.write_text(test_csv)
    
    with open(csv_file, "rb") as f:
        response = client.post(
            "/predict?model_id=1",
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            files={"file": ("test_data.csv", f, "text/csv")}
        )
    
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert len(response.json()["result"]) == 1
    assert response.json()["result"][0] in ["e", "p"]

def test_predict_xlsx(client, test_db, registered_user, tmp_path):
    test_db.add(DBModel(id=1, name="RandomForest", cost=1.0, file_path="ml_models/trained_ml_models/RandomForest.pkl"))
    test_db.commit()
    test_data = {
        "cap-diameter": [5.0],
        "cap-shape": ["convex"],
        "cap-surface": ["scaly"],
        "cap-color": ["brown"],
        "does-bruise-or-bleed": [False],
        "gill-attachment": ["adnate"],
        "gill-spacing": ["close"],
        "gill-color": ["white"],
        "stem-height": [6.0],
        "stem-width": [2.0],
        "stem-surface": ["fibrous"],
        "stem-color": ["white"],
        "has-ring": [True],
        "ring-type": ["pendant"],
        "habitat": ["forest"],
        "season": ["spring"]
    }
    df = pd.DataFrame(test_data)
    excel_file = tmp_path / "test_data.xlsx"
    df.to_excel(excel_file, index=False)
    
    with open(excel_file, "rb") as f:
        response = client.post(
            "/predict?model_id=1",
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            files={"file": ("test_data.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
    
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert len(response.json()["result"]) == 1
    assert response.json()["result"][0] in ["e", "p"]

def test_predict_invalid_file_type(client, test_db, registered_user, tmp_path):
    test_db.add(DBModel(id=1, name="RandomForest", cost=1.0, file_path="ml_models/trained_ml_models/RandomForest.pkl"))
    test_db.commit()
    txt_file = tmp_path / "test_data.txt"
    txt_file.write_text("invalid data")
    
    with open(txt_file, "rb") as f:
        response = client.post(
            "/predict?model_id=1",
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            files={"file": ("test_data.txt", f, "text/plain")}
        )
    
    assert response.status_code == 400
    assert response.json()["detail"] == "Only CSV or XLSX files are supported"

def test_predict_missing_columns(client, test_db, registered_user, tmp_path):
    test_db.add(DBModel(id=1, name="RandomForest", cost=1.0, file_path="ml_models/trained_ml_models/RandomForest.pkl"))
    test_db.commit()
    test_csv = """
cap-diameter,cap-shape
5.0,convex
"""
    csv_file = tmp_path / "test_data.csv"
    csv_file.write_text(test_csv)
    
    with open(csv_file, "rb") as f:
        response = client.post(
            "/predict?model_id=1",
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            files={"file": ("test_data.csv", f, "text/csv")}
        )
    
    assert response.status_code == 400
    assert response.json()["detail"].startswith("Missing column")

def test_predict_invalid_model_id(client, test_db, registered_user, tmp_path):
    test_db.add(DBModel(id=1, name="RandomForest", cost=1.0, file_path="ml_models/trained_ml_models/RandomForest.pkl"))
    test_db.commit()
    test_csv = """
cap-diameter,cap-shape,cap-surface,cap-color,does-bruise-or-bleed,gill-attachment,gill-spacing,gill-color,stem-height,stem-width,stem-surface,stem-color,has-ring,ring-type,habitat,season
5.0,convex,scaly,brown,false,adnate,close,white,6.0,2.0,fibrous,white,true,pendant,forest,spring
"""
    csv_file = tmp_path / "test_data.csv"
    csv_file.write_text(test_csv)
    
    with open(csv_file, "rb") as f:
        response = client.post(
            "/predict?model_id=999",
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            files={"file": ("test_data.csv", f, "text/csv")}
        )
    
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid model ID"

def test_predict_insufficient_balance(client, test_db, registered_user, tmp_path):
    test_db.add(DBModel(id=1, name="RandomForest", cost=1.0, file_path="ml_models/trained_ml_models/RandomForest.pkl"))
    test_db.commit()
    update_user_balance(test_db, "testuser", -10.0)  # Обнуляем баланс
    test_csv = """
cap-diameter,cap-shape,cap-surface,cap-color,does-bruise-or-bleed,gill-attachment,gill-spacing,gill-color,stem-height,stem-width,stem-surface,stem-color,has-ring,ring-type,habitat,season
5.0,convex,scaly,brown,false,adnate,close,white,6.0,2.0,fibrous,white,true,pendant,forest,spring
"""
    csv_file = tmp_path / "test_data.csv"
    csv_file.write_text(test_csv)
    
    with open(csv_file, "rb") as f:
        response = client.post(
            "/predict?model_id=1",
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            files={"file": ("test_data.csv", f, "text/csv")}
        )
    
    assert response.status_code == 400
    assert response.json()["detail"] == "Insufficient balance"

def test_predict_balance_deduction(client, test_db, registered_user, tmp_path):
    test_db.add(DBModel(id=1, name="RandomForest", cost=1.0, file_path="ml_models/trained_ml_models/RandomForest.pkl"))
    test_db.commit()
    test_csv = """
cap-diameter,cap-shape,cap-surface,cap-color,does-bruise-or-bleed,gill-attachment,gill-spacing,gill-color,stem-height,stem-width,stem-surface,stem-color,has-ring,ring-type,habitat,season
5.0,convex,scaly,brown,false,adnate,close,white,6.0,2.0,fibrous,white,true,pendant,forest,spring
"""
    csv_file = tmp_path / "test_data.csv"
    csv_file.write_text(test_csv)
    
    with open(csv_file, "rb") as f:
        response = client.post(
            "/predict?model_id=1",
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            files={"file": ("test_data.csv", f, "text/csv")}
        )
    
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    user = test_db.query(DBUser).filter(DBUser.username == "testuser").first()
    assert user.balance == 9.0  # Баланс уменьшился на 1.0 (стоимость RandomForest)

def test_predict_missing_model_file(client, test_db, registered_user, tmp_path):
    test_db.add(DBModel(id=1, name="RandomForest", cost=1.0, file_path="ml_models/trained_ml_models/RandomForest.pkl"))
    test_db.commit()
    test_csv = """
cap-diameter,cap-shape,cap-surface,cap-color,does-bruise-or-bleed,gill-attachment,gill-spacing,gill-color,stem-height,stem-width,stem-surface,stem-color,has-ring,ring-type,habitat,season
5.0,convex,scaly,brown,false,adnate,close,white,6.0,2.0,fibrous,white,true,pendant,forest,spring
"""
    csv_file = tmp_path / "test_data.csv"
    csv_file.write_text(test_csv)
    
    with patch("os.path.exists") as mock_exists:
        mock_exists.return_value = False
        with open(csv_file, "rb") as f:
            response = client.post(
                "/predict?model_id=1",
                headers={"Authorization": f"Bearer {registered_user['token']}"},
                files={"file": ("test_data.csv", f, "text/csv")}
            )
    
    assert response.status_code == 500
    assert response.json()["detail"].startswith("Model file not found")

def test_predict_unknown_categorical_value(client, test_db, registered_user, tmp_path):
    test_db.add(DBModel(id=1, name="RandomForest", cost=1.0, file_path="ml_models/trained_ml_models/RandomForest.pkl"))
    test_db.commit()
    test_csv = """
cap-diameter,cap-shape,cap-surface,cap-color,does-bruise-or-bleed,gill-attachment,gill-spacing,gill-color,stem-height,stem-width,stem-surface,stem-color,has-ring,ring-type,habitat,season
5.0,invalid_shape,scaly,brown,false,adnate,close,white,6.0,2.0,fibrous,white,true,pendant,forest,spring
"""
    csv_file = tmp_path / "test_data.csv"
    csv_file.write_text(test_csv)
    
    with open(csv_file, "rb") as f:
        response = client.post(
            "/predict?model_id=1",
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            files={"file": ("test_data.csv", f, "text/csv")}
        )
    
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert len(response.json()["result"]) == 1
    assert response.json()["result"][0] in ["e", "p"]