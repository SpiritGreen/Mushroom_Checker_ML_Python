from celery import Celery
from sqlalchemy.orm import Session
from db.db_prediction import DBPrediction
from services.prediction_service import make_prediction
from database import SessionLocal
from celery.utils.log import get_task_logger
from celery_app import app

# Явное логгирование:
logger = get_task_logger(__name__)

# Получение сессии БД:
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Задача для выполнения предсказания:
@app.task(bind=True, max_retries=3, retry_backoff=True)
def predict_task(self, prediction_id: int):
    """
    Асинхронная задача для выполнения предсказания ML-моделью.

    Args:
        prediction_id (int): ID записи предсказания в таблице Predictions.

    Returns:
        dict: Результат предсказания и статус.
    Raises:
        Exception: Если предсказание не удалось, задача повторяется до max_retries.
    """
    logger.info(f"Начинаем задачу предсказания для prediction_id={prediction_id}")

    # Validate prediction_id
    if not isinstance(prediction_id, int) or prediction_id <= 0:
        logger.error(f"Invalid prediction_id: {prediction_id}")
        return {"status": "failed", "result": None, "error": "Invalid prediction ID"}
    
    db = next(get_db())
    try:
        # Получаем запись предсказания:
        prediction = db.query(DBPrediction).filter(DBPrediction.id == prediction_id).first()
        if not prediction:
            logger.error(f"Предсказание {prediction_id} не найдено")
            return {"status": "failed", "result": None, "error": "Prediction not found"}
        
        # Выполняем предсказание:
        updated_prediction = make_prediction(db, prediction)
        
        # Обновляем статус и результат:
        prediction.result = updated_prediction.result
        prediction.status = updated_prediction.status
        db.commit()
        
        logger.info(f"Предсказание {prediction_id} завершено со статусом={prediction.status}")
        return {"status": prediction.status, "result": prediction.result}
    
    except Exception as exc:
        logger.error(f"Error in prediction {prediction_id}: {str(exc)}")
        raise self.retry(exc=exc)  # Повторяем задачу при ошибке
    
    finally:
        db.close()  # Закрываем сессию