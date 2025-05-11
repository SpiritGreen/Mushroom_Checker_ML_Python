import pandas as pd
import pickle
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score
from sklearn.impute import SimpleImputer
from tqdm import tqdm
import logging
import os
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Пути к датасету и моделям относительно папки ml_service
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "..", "data", "train.csv")
MODEL_DIR = os.path.join(BASE_DIR, "ml_models", "trained_ml_models")
IMPUTER_DIR = os.path.join(BASE_DIR, "ml_models", "imputers")
ENCODER_DIR = os.path.join(BASE_DIR, "ml_models", "label_encoders")

# Создаём директории для моделей, имьютеров и энкодеров
os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(IMPUTER_DIR, exist_ok=True)
os.makedirs(ENCODER_DIR, exist_ok=True)

# Список всех категориальных и числовых признаков
CATEGORICAL_COLUMNS = [
    "cap-shape", "cap-surface", "cap-color", "does-bruise-or-bleed",
    "gill-attachment", "gill-spacing", "gill-color",
    "stem-surface", "stem-color", "has-ring", "ring-type", "habitat", "season"
]
NUMERICAL_COLUMNS = ["cap-diameter", "stem-height", "stem-width"]

# Столбцы, которые удаляем из-за высокого процента NaN
DROP_COLUMNS = ["veil-type", "veil-color", "stem-root", "spore-print-color"]

def load_data():
    """
    Загружает и подготавливает датасет грибов, кодируя категориальные признаки и обрабатывая NaN.

    Returns:
        tuple: (X, y, encoders) - признаки, целевая переменная, словарь энкодеров.
    
    Raises:
        Exception: Если не удалось загрузить или обработать данные.
    """
    try:
        df = pd.read_csv(DATA_PATH)
        logger.info(f"Загружен датасет с {len(df)} строками")
        
        # Проверяем наличие NaN
        nan_counts = df.isna().sum()
        for col, count in nan_counts.items():
            if count > 0:
                logger.warning(f"Column {col} has {count} NaN values")
        
        # Удаляем столбец id и столбцы с высоким процентом NaN
        columns_to_drop = ['id'] if 'id' in df.columns else []
        columns_to_drop.extend([col for col in DROP_COLUMNS if col in df.columns])
        df = df.drop(columns=columns_to_drop)
        logger.info(f"Удалены столбцы: {columns_to_drop}")
        
        # Обработка NaN
        # Числовые столбцы: заполняем медианой
        num_imputer = SimpleImputer(strategy='median')
        for col in NUMERICAL_COLUMNS:
            if col in df.columns:
                df[col] = num_imputer.fit_transform(df[[col]]).ravel()
                with open(os.path.join(IMPUTER_DIR, f'imputer_{col}.pkl'), 'wb') as f:
                    pickle.dump(num_imputer, f)
                logger.info(f"Сохранён imputer для {col}")
        
        # Категориальные столбцы: заполняем 'unknown'
        cat_imputer = SimpleImputer(strategy='constant', fill_value='unknown')
        for col in CATEGORICAL_COLUMNS:
            if col in df.columns:
                df[col] = cat_imputer.fit_transform(df[[col]].astype(str)).ravel()
                with open(os.path.join(IMPUTER_DIR, f'imputer_{col}.pkl'), 'wb') as f:
                    pickle.dump(cat_imputer, f)
                logger.info(f"Сохранён imputer для {col}")
        
        # Кодирование категориальных признаков
        encoders = {}
        for col in CATEGORICAL_COLUMNS:
            if col in df.columns:
                le = LabelEncoder()
                # Гарантируем, что 'unknown' включён в категории, 
                # чтобы не возникало ошибки с новыми значениями
                unique_values = np.append(df[col].unique(), 'unknown')
                le.fit(unique_values)
                df[col] = le.transform(df[col].astype(str))
                encoders[col] = le
                with open(os.path.join(ENCODER_DIR, f'le_{col}.pkl'), 'wb') as f:
                    pickle.dump(le, f)
                logger.info(f"Сохранён encoder для {col}")
        
        # Кодирование целевой переменной
        le_class = LabelEncoder()
        df['class'] = le_class.fit_transform(df['class'])
        with open(os.path.join(ENCODER_DIR, 'le_class.pkl'), 'wb') as f:
            pickle.dump(le_class, f)
        logger.info("Сохранён encoder для class")
        
        # Разделяем признаки и целевую переменную
        X = df.drop(columns=['class'])
        y = df['class']
        return X, y, encoders
    except Exception as e:
        logger.error(f"Возникла ошибка при загрузке данных: {str(e)}")
        raise

def train_model(model, X_train, y_train, model_name):
    """
    Обучает модель и сохраняет её в .pkl файл.

    Args:
        model: Модель машинного обучения (например, RandomForestClassifier).
        X_train: Обучающие признаки.
        y_train: Обучающие метки.
        model_name (str): Имя модели для сохранения.

    Returns:
        object: Обученная модель.
    """
    logger.info(f"Training {model_name}")
    with tqdm(total=100, desc=f"Training {model_name}", unit="%") as pbar:
        model.fit(X_train, y_train)
        pbar.update(100)
    
    model_path = os.path.join(MODEL_DIR, f"{model_name}.pkl")
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    logger.info(f"Saved model to {model_path}")
    return model

def main():
    """Основная функция для обучения и оценки моделей."""
    X, y, encoders = load_data()
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    models = [
        (RandomForestClassifier(n_estimators=100, random_state=42), "RandomForest"),
        (GradientBoostingClassifier(n_estimators=100, random_state=42), "GradientBoosting"),
        (MLPClassifier(hidden_layer_sizes=(100,), max_iter=500, random_state=42), "NeuralNetwork")
    ]
    
    for model, name in models:
        trained_model = train_model(model, X_train, y_train, name)
        y_pred = trained_model.predict(X_test)
        f1 = f1_score(y_test, y_pred, average='weighted')
        logger.info(f"{name} F1-score: {f1:.4f}")

if __name__ == "__main__":
    main()