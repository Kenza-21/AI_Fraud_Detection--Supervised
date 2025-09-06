# [file name]: check_model.py
import joblib
import os
from app.ml_model import create_fraud_model

def check_model_status():
    """Vérifie l'état des fichiers de modèle"""
    model_path = "models/xgboost_fraud_model.joblib"
    scaler_path = "models/scaler.joblib"
    
    print("=== VÉRIFICATION DES MODÈLES ===")
    print(f"Modèle existe: {os.path.exists(model_path)}")
    print(f"Scaler existe: {os.path.exists(scaler_path)}")
    
    if os.path.exists(model_path):
        try:
            model = joblib.load(model_path)
            print(f"Modèle chargé - Classes: {getattr(model, 'classes_', 'N/A')}")
            print(f"Modèle entraîné: {hasattr(model, 'classes_')}")
        except Exception as e:
            print(f"Erreur chargement modèle: {e}")
    
    if os.path.exists(scaler_path):
        try:
            scaler = joblib.load(scaler_path)
            print(f"Scaler chargé - Mean: {getattr(scaler, 'mean_', 'N/A')}")
            print(f"Scaler entraîné: {hasattr(scaler, 'mean_')}")
        except Exception as e:
            print(f"Erreur chargement scaler: {e}")
    
    # Test avec le modèle
    fraud_model = create_fraud_model()
    print(f"\nModèle XGBoost chargé: {fraud_model.model is not None}")
    print(f"Modèle XGBoost entraîné: {hasattr(fraud_model.model, 'classes_') if fraud_model.model else False}")
    print(f"Scaler entraîné: {hasattr(fraud_model.scaler, 'mean_') if fraud_model.scaler else False}")

if __name__ == "__main__":
    check_model_status()