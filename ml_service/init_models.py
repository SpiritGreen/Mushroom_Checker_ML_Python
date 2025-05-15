# init_models.py
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
from db.db_model import DBModel
from db.db_user import DBUser
from db.db_prediction import DBPrediction
from db.db_transaction import DBTransaction

# Создание всех таблиц
Base.metadata.create_all(bind=engine)

def init_models():
    db: Session = SessionLocal()
    try:
        models = [
            DBModel(id=1, name="RandomForest", cost=1.0, file_path="ml_models/trained_ml_models/RandomForest.pkl"),
            DBModel(id=2, name="GradientBoosting", cost=2.0, file_path="ml_models/trained_ml_models/GradientBoosting.pkl"),
            DBModel(id=3, name="NeuralNetwork", cost=3.0, file_path="ml_models/trained_ml_models/NeuralNetwork.pkl")
        ]
        db.add_all(models)
        db.commit()
        print("Models initialized successfully.")
    except Exception as e:
        print(f"Error initializing models: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_models()