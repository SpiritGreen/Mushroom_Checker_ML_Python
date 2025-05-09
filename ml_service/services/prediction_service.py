import pandas as pd
import io
import logging
from typing import List, Dict, Any
from sklearn.ensemble import RandomForestClassifier  # ЗАГЛУШКА
from models.prediction import Prediction
from fastapi import HTTPException
from models.model import Model

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Встроенные модели (ЗАГЛУШКА)
MODELS = [
    Model(id=1, name="RandomForest", cost=1.0),
    Model(id=2, name="GradientBoosting", cost=2.0),
    Model(id=3, name="NeuralNetwork", cost=3.0)
]

# Получение списка имеющихся моделей:
def get_available_models() -> List[Model]:
    logger.info("Отображены доступные модели")
    return MODELS

# Чтение файла, который нам отправили:
def read_input_file(file: bytes, file_type: str) -> List[Dict[str, Any]]:
    # Чтение входных данных (xlsx/csv)
    try:
        file_stream = io.BytesIO(file) # Для корректного чтения файлов
        if file_type == "csv":
            df = pd.read_csv(file_stream)
        elif file_type == "xlsx":
            df = pd.read_excel(file_stream)
        else:
            raise HTTPException(status_code=400, detail="Неподдерживаемый тип файла")
        data = df.to_dict(orient="records")
        logger.info(f"Успешно прочитан файл: {len(data)}")
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка во время чтения файла: {str(e)}")

# Валидация входных данных:
def validate_input_data(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    required_columns = ["cap-diameter", "cap-shape", "cap-surface"]  # ДОПОЛНИТЬ
    logger.info("Валидация входных данных")
    for row in data:
        for col in required_columns:
            if col not in row:
                raise HTTPException(status_code=400, detail=f"Нет колонки: {col}")
    logger.info("Входные данные успешно провалидированы")
    return data

# Получение модели:
def get_model(model_id: int) -> Model:
    logger.info(f"Пытаемся получить модель с id: {model_id}")
    # Поиск модели по id
    for model in MODELS:
        if model.id == model_id:
            return model
    logger.error(f"Модель не найдена: {model_id}")
    raise HTTPException(status_code=404, detail="Модель не найдена")

# Предсказание:
def make_prediction(prediction: Prediction) -> Prediction:
    try:
        logger.info(f"Создание предсказаний для модели: {prediction.model_id}")
        # Получить модель
        model = get_model(prediction.model_id)
        
        # Преобразование данных
        data = validate_input_data(prediction.input_data)
        X = pd.DataFrame(data)  # Дополнить предобработкой

        # Фиктивное предсказание (заглушка)
        predictions = ["edible" if i % 2 == 0 else "poisonous" for i in range(len(data))]
        
        # Выполнение предсказания
        # model_instance = model_instances.get(prediction.model_id)
        # if not model_instance:
        #     raise HTTPException(status_code=500, detail="Model instance not found")
        # predictions = model_instance.predict(X)  # Заменить на реальную модель
        
        prediction.result = predictions
        prediction.status = "completed"
        logger.info("Предсказание успешно завершено")
    except HTTPException as e:
        logger.error(f"Предсказание завершилось ошибкой: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Неожиданная ошибка во время предсказания: {str(e)}")
        prediction.status = "failed"
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")
    return prediction