import json
import pandas as pd
import io
import logging
import pickle
import os
from typing import List, Dict, Any, Sequence
from fastapi import HTTPException
from sqlalchemy.orm import Session
from models.prediction import Prediction
from models.model import Model
from db.db_model import DBModel
from services.db_operations import create_prediction, update_prediction_result, get_model_by_id

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Пути к моделям, импутерам и энкодерам
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # На уровень выше от services к ml_service
MODEL_DIR = os.path.join(BASE_DIR, "ml_models", "trained_ml_models")
IMPUTER_DIR = os.path.join(BASE_DIR, "ml_models", "imputers")
ENCODER_DIR = os.path.join(BASE_DIR, "ml_models", "label_encoders")

# Проверка существования директорий
for directory in [MODEL_DIR, IMPUTER_DIR, ENCODER_DIR]:
    if not os.path.exists(directory):
        logger.error(f"Не найдена директория: {directory}")
        raise FileNotFoundError(f"Directory not found: {directory}")
    
# Список всех признаков
REQUIRED_COLUMNS = [
    "cap-diameter", "cap-shape", "cap-surface", "cap-color", "does-bruise-or-bleed",
    "gill-attachment", "gill-spacing", "gill-color", "stem-height", "stem-width",
    "stem-surface", "stem-color", "has-ring", "ring-type", "habitat", "season"
]

NUMERICAL_COLUMNS = ["cap-diameter", "stem-height", "stem-width"]
CATEGORICAL_COLUMNS = [col for col in REQUIRED_COLUMNS if col not in NUMERICAL_COLUMNS]

# Список моделей
MODELS = [
    Model(id=1, name="RandomForest", cost=1.0, file_path=f"{MODEL_DIR}/RandomForest.pkl"),
    Model(id=2, name="GradientBoosting", cost=2.0, file_path=f"{MODEL_DIR}/GradientBoosting.pkl"),
    Model(id=3, name="NeuralNetwork", cost=3.0, file_path=f"{MODEL_DIR}/NeuralNetwork.pkl")
]

def get_available_models(db: Session) -> List[Model]:
    """
    Возвращает список доступных ML-моделей из базы данных.

    Args:
        db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.

    Returns:
        List[Model]: Список объектов моделей в формате Pydantic.
    """
    logger.info("Получение списка доступных моделей")
    db_models = db.query(DBModel).all()
    return [Model(id=m.id, name=m.name, cost=m.cost, file_path=m.file_path) for m in db_models]

def read_input_file(file: bytes, file_type: str) -> Sequence[Dict[str, Any]]:
    """
    Читает входной файл (CSV или XLSX) и возвращает данные в формате списка словарей.

    Args:
        file (bytes): Содержимое файла в виде байтов.
        file_type (str): Тип файла ('csv' или 'xlsx').

    Returns:
        Sequence[Dict[str, Any]]: Данные в формате списка словарей.

    Raises:
        HTTPException: Если тип файла не поддерживается или произошла ошибка чтения.
    """
    # Чтение входных данных (xlsx/csv)
    try:
        logger.info(f"Чтение файла типа: {file_type}")
        file_stream = io.BytesIO(file) # Для корректного чтения файлов
        if file_type == "csv":
            df = pd.read_csv(file_stream)
        elif file_type == "xlsx":
            df = pd.read_excel(file_stream)
        else:
            logger.error(f"Неподдерживаемый тип файла: {file_type}")
            raise HTTPException(status_code=400, detail="Неподдерживаемый тип файла. Поддерживаются только CSV и XLSX файлы.")
        data = df.to_dict(orient="records")
        logger.info(f"Успешно прочитано строк: {len(data)}")
        return data
    except Exception as e:
        logger.error(f"Ошибка чтения файла: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Ошибка чтения файла: {str(e)}")

def validate_input_data(data: Sequence[Dict[str, Any]]) -> Sequence[Dict[str, Any]]:
    """
    Проверяет входные данные на наличие всех необходимых столбцов.

    Args:
        data (Sequence[Dict[str, Any]]): Входные данные в формате списка словарей.

    Returns:
        Sequence[Dict[str, Any]]: Проверенные данные.

    Raises:
        HTTPException: Если отсутствуют необходимые столбцы.
    """
    logger.info("Валидация входных данных")
    for row in data:
        for col in REQUIRED_COLUMNS:
            if col not in row:
                logger.error(f"Пропущена колонка: {col}")
                raise HTTPException(status_code=400, detail=f"Missing column: {col}")
    logger.info("Входные данные успешно провалидированы")
    return data

def make_prediction(db: Session, prediction: Prediction) -> Prediction:
    """
    Выполняет предсказание с использованием обученной ML-модели и сохраняет результат в базе данных.

    Args:
        db (Session): Сессия SQLAlchemy для взаимодействия с базой данных.
        prediction (Prediction): Объект предсказания с входными данными.

    Returns:
        Prediction: Обновлённый объект предсказания с результатами и статусом.

    Raises:
        HTTPException: Если модель не найдена, файл модели отсутствует или произошла ошибка предсказания.
    """
    try:
        logger.info(f"Создание предсказания для модели ID: {prediction.model_id}")
        # Сохранение предсказания в БД
        db_prediction = create_prediction(
            db,
            user_id=prediction.user_id,
            model_id=prediction.model_id,
            input_data=prediction.input_data
        )

        # Проверка модели
        db_model = get_model_by_id(db, prediction.model_id)
        if not db_model:
            update_prediction_result(db, db_prediction.id, [], "failed")
            logger.error(f"Модель не найдена: {prediction.model_id}")
            raise HTTPException(status_code=400, detail="Invalid model ID")

        # Загрузка модели
        model_path = os.path.join(MODEL_DIR, f"{db_model.name}.pkl")
        if not os.path.exists(model_path):
            update_prediction_result(db, db_prediction.id, [], "failed")
            logger.error(f"Не найден файл модели: {model_path}")
            raise HTTPException(status_code=500, detail=f"Model file not found: {model_path}")
        with open(model_path, 'rb') as f:
            model = pickle.load(f)
        logger.debug(f"Loaded model: {type(model)}, random_state: {getattr(model, 'random_state', None)}")

        # Загрузка импутеров и энкодеров
        imputers = {}
        encoders = {}
        for col in NUMERICAL_COLUMNS:
            imputer_path = os.path.join(IMPUTER_DIR, f'imputer_{col}.pkl')
            if not os.path.exists(imputer_path):
                update_prediction_result(db, db_prediction.id, [], "failed")
                logger.error(f"Не найден файл импутера: {imputer_path}")
                raise HTTPException(status_code=500, detail=f"Imputer file not found: {imputer_path}")
            imputers[col] = pickle.load(open(imputer_path, 'rb'))

        for col in CATEGORICAL_COLUMNS:
            imputer_path = os.path.join(IMPUTER_DIR, f'imputer_{col}.pkl')
            encoder_path = os.path.join(ENCODER_DIR, f'le_{col}.pkl')
            if not os.path.exists(imputer_path):
                update_prediction_result(db, db_prediction.id, [], "failed")
                logger.error(f"Не найден файл импутера: {imputer_path}")
                raise HTTPException(status_code=500, detail=f"Imputer file not found: {imputer_path}")
            if not os.path.exists(encoder_path):
                update_prediction_result(db, db_prediction.id, [], "failed")
                logger.error(f"Не найден файл энкодера: {encoder_path}")
                raise HTTPException(status_code=500, detail=f"Encoder file not found: {encoder_path}")
            imputers[col] = pickle.load(open(imputer_path, 'rb'))
            encoders[col] = pickle.load(open(encoder_path, 'rb'))
        le_class_path = os.path.join(ENCODER_DIR, 'le_class.pkl')
        if not os.path.exists(le_class_path):
            update_prediction_result(db, db_prediction.id, [], "failed")
            logger.error(f"Не найден файл энкодера классов: {le_class_path}")
            raise HTTPException(status_code=500, detail=f"Class encoder file not found: {le_class_path}")
        le_class = pickle.load(open(le_class_path, 'rb'))

        # Валидация данных
        data = validate_input_data(prediction.input_data)

        # Подготовка данных для предсказания
        df = pd.DataFrame(data)

        # Обработка NaN
        for col in NUMERICAL_COLUMNS:
            df[col] = imputers[col].transform(df[[col]]).ravel()
        for col in CATEGORICAL_COLUMNS:
            df[col] = imputers[col].transform(df[[col]].astype(str)).ravel()

        # Обработка неизвестных категориальных значений
        for col in CATEGORICAL_COLUMNS:
            known_classes = set(encoders[col].classes_)
            df[col] = df[col].apply(lambda x: x if x in known_classes else 'unknown')

        # Кодирование категориальных признаков
        for col in CATEGORICAL_COLUMNS:
            try:
                df[col] = encoders[col].transform(df[col].astype(str))
            except ValueError as e:
                update_prediction_result(db, db_prediction.id, [], "failed")
                logger.error(f"Ошибка кодирования признака {col}: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Неверные данные в колонке {col}: {str(e)}")

        # Выполнение предсказания
        predictions = model.predict(df[REQUIRED_COLUMNS])
        result = le_class.inverse_transform(predictions).tolist()

        # Обновление предсказания в БД
        db_prediction = update_prediction_result(db, db_prediction.id, json.dumps(result), "completed")

        logger.info("Предсказание успешно завершено")
        # Парсим result из строки JSON в список перед созданием объекта Prediction, чтобы избежать ошибки ValueError
        parsed_result = json.loads(db_prediction.result) if db_prediction.result else None
        return Prediction(
            id=db_prediction.id,
            user_id=db_prediction.user_id,
            model_id=db_prediction.model_id,
            input_data=db_prediction.input_data,
            result=parsed_result,
            status=db_prediction.status,
            created_at=db_prediction.created_at
        )
    except HTTPException as e:
        logger.error(f"Предсказание завершилось ошибкой: {str(e)}")
        raise
    except ValueError as e:
        update_prediction_result(db, db_prediction.id, json.dumps([]), "failed")
        logger.error(f"Ошибка предсказания: Неверные данные: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid data: {str(e)}")
    except Exception as e:
        update_prediction_result(db, db_prediction.id, json.dumps([]), "failed")
        logger.error(f"Неожиданная ошибка предсказания: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")