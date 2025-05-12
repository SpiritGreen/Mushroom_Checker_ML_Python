import pytest
import sys
import os
import pandas as pd
import io
import time
from unittest.mock import patch

# Попытка починить импорты
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app
from services.auth import db, create_access_token
from datetime import timedelta

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def clean_db():
    db.clear()
    yield
    db.clear()

@pytest.fixture
def registered_user(client, clean_db):
    client.post("/register", data={"username": "testuser", "password": "password123", "email": "testuser@example.com"})
    token_response = client.post("/token", data={"username": "testuser", "password": "password123"})
    token = token_response.json()["access_token"]
    return {"username": "testuser", "token": token}

def test_register(client, clean_db):
    response = client.post("/register", data={"username": "testuser", "password": "password123", "email": "testuser@example.com"})
    assert response.status_code == 200
    assert response.json()["username"] == "testuser"
    assert response.json()["balance"] == 10.0

def test_register_existing_user(client, clean_db):
    client.post("/register", data={"username": "testuser", "password": "password123", "email": "testuser@example.com"})
    response = client.post("/register", data={"username": "testuser", "password": "password123", "email": "testuser@example.com"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Пользователь уже существует"

def test_token(client, clean_db):
    client.post("/register", data={"username": "testuser", "password": "password123", "email": "testuser@example.com"})
    response = client.post("/token", data={"username": "testuser", "password": "password123"})
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

def test_token_invalid_credentials(client, clean_db):
    client.post("/register", data={"username": "testuser", "password": "password123", "email": "testuser@example.com"})
    response = client.post("/token", data={"username": "testuser", "password": "wrongpassword"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Неверное имя пользователя или пароль"

def test_token_nonexistent_user(client, clean_db):
    response = client.post("/token", data={"username": "nonexistent", "password": "password123"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Неверное имя пользователя или пароль"

def test_token_expired(client, clean_db):
    client.post("/register", data={"username": "testuser", "password": "password123", "email": "testuser@example.com"})
    expired_token = create_access_token(
        data={"sub": "testuser"},
        expires_delta=timedelta(seconds=-1)
    )
    response = client.get("/users/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Не удалось проверить учетные данные"

def test_get_models(client, clean_db, registered_user):
    response = client.get("/models", headers={"Authorization": f"Bearer {registered_user['token']}"})
    assert response.status_code == 200
    assert len(response.json()) == 3
    assert response.json()[0]["name"] == "RandomForest"

def test_get_models_invalid_token(client, clean_db):
    response = client.get("/models", headers={"Authorization": "Bearer invalid_token"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Не удалось проверить учетные данные"

def test_users_me(client, clean_db, registered_user):
    response = client.get("/users/me", headers={"Authorization": f"Bearer {registered_user['token']}"})
    assert response.status_code == 200
    assert response.json()["username"] == "testuser"
    assert response.json()["balance"] == 10.0

def test_users_me_invalid_token(client, clean_db):
    response = client.get("/users/me", headers={"Authorization": "Bearer invalid_token"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Не удалось проверить учетные данные"

def test_predict_csv(client, clean_db, registered_user, tmp_path):
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

def test_predict_xlsx(client, clean_db, registered_user, tmp_path):
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

def test_predict_invalid_file_type(client, clean_db, registered_user, tmp_path):
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

def test_predict_missing_columns(client, clean_db, registered_user, tmp_path):
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

def test_predict_invalid_model_id(client, clean_db, registered_user, tmp_path):
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

def test_predict_insufficient_balance(client, clean_db, registered_user, tmp_path):
    db["testuser"]["balance"] = 0.0
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

def test_predict_balance_deduction(client, clean_db, registered_user, tmp_path):
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
    user = db["testuser"]
    assert user["balance"] == 9.0  # Баланс уменьшился на 1.0 (стоимость RandomForest)

def test_predict_missing_model_file(client, clean_db, registered_user, tmp_path):
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
    assert response.json()["detail"].startswith("Prediction error: Model file not found")

def test_predict_unknown_categorical_value(client, clean_db, registered_user, tmp_path):
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