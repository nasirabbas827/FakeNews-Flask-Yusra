import pandas as pd
import numpy as np
import joblib
import re
import os
import unicodedata
import warnings

from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# ────────────────────────────────────────────────
#              TEXT CLEANING
# ────────────────────────────────────────────────
def clean_text(text):
    if pd.isna(text) or not isinstance(text, (str, bytes)):
        return ""
    
    text = str(text).lower().strip()
    
    # Normalize unicode / remove accents
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    
    # Remove URLs, mentions, hashtags
    text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'@\w+|#\w+', '', text)
    
    # Remove emojis and most punctuation
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # Keep only letters and spaces
    text = re.sub(r'[^a-z\s]', ' ', text)
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


# ────────────────────────────────────────────────
#              PREPROCESS DATASET
# ────────────────────────────────────────────────
def preprocess_dataset(df):
    print(f"Original shape: {df.shape}")
    
    # Keep only needed columns
    if 'text' not in df.columns or 'target' not in df.columns:
        raise ValueError("CSV must contain columns: 'text' and 'target'")
    
    df = df[['text', 'target']].copy()
    
    # Standardize target labels
    df['target'] = df['target'].astype(str).str.strip().str.upper()
    # Map common variations → numeric (1=REAL, 0=FAKE)
    mapping = {
        'REAL': 1, 'TRUE': 1, '1': 1,
        'FAKE': 0, 'FALSE': 0, '0': 0
    }
    df['target'] = df['target'].map(mapping)
    
    # Drop rows where target could not be mapped
    before = len(df)
    df = df[df['target'].isin([0, 1])]
    print(f"Dropped {before - len(df)} rows due to invalid target values")
    
    # Drop missing text
    df = df.dropna(subset=['text'])
    df['text'] = df['text'].astype(str).str.strip()
    
    # Remove very short / empty
    df = df[df['text'].str.len() >= 15]   # lowered a bit from 20
    
    # Clean text
    print("Cleaning text...")
    df['text'] = df['text'].apply(clean_text)
    
    # Remove rows that became empty after cleaning
    before = len(df)
    df = df[df['text'].str.strip() != ""]
    print(f"Removed {before - len(df)} rows that became empty after cleaning")
    
    print(f"Final shape after preprocessing: {df.shape}")
    
    # Show class distribution
    if len(df) > 0:
        print("\nClass distribution:")
        print(df['target'].value_counts(dropna=False))
        print("\nPercentages:")
        print(df['target'].value_counts(normalize=True).mul(100).round(1))
    
    return df


# ────────────────────────────────────────────────
#              TRAIN MODEL
# ────────────────────────────────────────────────
def train_model(dataset_path, max_features=12000, ngram_range=(1,2)):
    # ─── Load file ───────────────────────────────────────
    try:
        df = pd.read_csv(dataset_path, encoding='utf-8', low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(dataset_path, encoding='latin1', low_memory=False)
    except Exception as e:
        raise ValueError(f"Could not read file: {e}")
    
    df = preprocess_dataset(df)
    
    if len(df) == 0:
        raise ValueError("No valid rows left after preprocessing")
    
    if df['target'].nunique() < 2:
        print("WARNING: Only one class present in the data!")
    
    X = df['text']
    y = df['target']
    
    class_counts = y.value_counts()
    min_class_count = class_counts.min()
    total = len(y)
    
    print(f"\nMin class size = {min_class_count} / {total} samples")
    
    # ─── Very small or dangerous imbalance cases ───────────
    if total < 10 or min_class_count < 2:
        print("→ Very small / imbalanced dataset → training on ALL data (no split)")
        vectorizer = TfidfVectorizer(
            max_features=max_features,
            ngram_range=ngram_range,
            stop_words='english',
            min_df=1,
            max_df=0.98
        )
        X_vec = vectorizer.fit_transform(X)
        
        model = LogisticRegression(
            max_iter=4000,
            class_weight='balanced',
            random_state=42
        )
        model.fit(X_vec, y)
        
        joblib.dump(model, 'trained_model.pkl')
        joblib.dump(vectorizer, 'vectorizer.pkl')
        print("Model & vectorizer saved (full dataset training)")
        return None
    
    # ─── Decide whether we can use stratified split ────────
    use_stratify = min_class_count >= 2
    
    if not use_stratify:
        print("→ Stratified split not possible (min class < 2) → using regular split")
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.20,
        random_state=42,
        stratify=y if use_stratify else None
    )
    
    print(f"Train size: {len(X_train)}   Test size: {len(X_test)}")
    
    # Vectorize
    vectorizer = TfidfVectorizer(
        max_features=max_features,
        ngram_range=ngram_range,
        stop_words='english',
        min_df=2,
        max_df=0.95
    )
    
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec  = vectorizer.transform(X_test)
    
    # Model
    model = LogisticRegression(
        max_iter=4000,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    model.fit(X_train_vec, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test_vec)
    
    acc  = accuracy_score(y_test, y_pred) * 100
    prec = precision_score(y_test, y_pred, average='weighted', zero_division=0) * 100
    rec  = recall_score(y_test, y_pred, average='weighted', zero_division=0) * 100
    f1   = f1_score(y_test, y_pred, average='weighted', zero_division=0) * 100
    
    print("\n" + "="*50)
    print(f"  Accuracy : {acc:5.2f}%")
    print(f"  Precision: {prec:5.2f}%")
    print(f"  Recall   : {rec:5.2f}%")
    print(f"  F1       : {f1:5.2f}%")
    print("="*50)
    
    # Save
    joblib.dump(model, 'trained_model.pkl')
    joblib.dump(vectorizer, 'vectorizer.pkl')
    print("Model and vectorizer saved.")
    
    return round(acc,2), round(prec,2), round(rec,2), round(f1,2)


# ────────────────────────────────────────────────
#              PREDICT FUNCTION
# ────────────────────────────────────────────────
def run_ai_model(text):
    if not os.path.exists('trained_model.pkl') or not os.path.exists('vectorizer.pkl'):
        raise FileNotFoundError("Model or vectorizer not found. Train first.")
    
    if not text or len(str(text).strip()) < 5:
        return "Invalid / too short input", 0.0
    
    model = joblib.load('trained_model.pkl')
    vectorizer = joblib.load('vectorizer.pkl')
    
    cleaned = clean_text(text)
    if not cleaned:
        return "Empty after cleaning", 0.0
    
    # Truncate long inputs
    words = cleaned.split()
    if len(words) > 500:
        cleaned = " ".join(words[:500])
    
    X_vec = vectorizer.transform([cleaned])
    
    pred = model.predict(X_vec)[0]
    proba = model.predict_proba(X_vec)[0]
    confidence = float(np.max(proba)) * 100
    
    label = "REAL" if pred == 1 else "FAKE"
    
    return label, round(confidence, 2)

