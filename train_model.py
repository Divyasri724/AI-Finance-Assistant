import os
import pandas as pd
import joblib

from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_PATH = os.path.join(BASE_DIR, "data", "transactions.csv")
MODEL_DIR = os.path.join(BASE_DIR, "ml_models")
MODEL_PATH = os.path.join(MODEL_DIR, "expense_category_model.pkl")

os.makedirs(MODEL_DIR, exist_ok=True)

data = pd.read_csv(DATA_PATH)

model = Pipeline([
    ("vectorizer", TfidfVectorizer(ngram_range=(1, 2))),
    ("classifier", LogisticRegression(
        max_iter=1000,
        class_weight="balanced"
    ))
])

model.fit(data["description"], data["category"])

joblib.dump(model, MODEL_PATH)

print("Expense category model trained successfully.")
print("Model saved at:", MODEL_PATH)