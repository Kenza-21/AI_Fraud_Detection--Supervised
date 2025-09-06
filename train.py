import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
import joblib
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier
from sklearn.preprocessing import StandardScaler
import os

# ---------------- Configuration ----------------
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# Configuration
np.random.seed(42)
random.seed(42)

# Pays blacklistés pour transactions frauduleuses
BLACKLIST_COUNTRIES = ['NG', 'TR', 'RU', 'UA', 'PK', 'IN', 'CN', 'VN', 'BR', 'CO', 'SY', 'IR', 'KP', 'SD', 'YE']
BLACKLIST_CITIES = ['Dubai', 'Istanbul', 'Beirut', 'Lima', 'Panama City', 'Lagos', 'Moscow', 'Karachi']

# Données pour le Maroc
MOROCCAN_CITIES = {
    'Casablanca': ['20000', '20200', '20300', '20400'],
    'Rabat': ['10000', '10100', '10200'],
    'Marrakech': ['40000', '40100', '40200'],
    'Fès': ['30000', '30100', '30200'],
    'Tanger': ['90000', '90100', '90200'],
    'Agadir': ['80000', '80100', '80200'],
    'Meknès': ['50000', '50100'],
    'Oujda': ['60000', '60100'],
    'Kenitra': ['14000', '14100'],
    'Tétouan': ['93000', '93100']
}

MOROCCAN_BANKS = [
    'ATTIJARIWAFA BANK', 'BANQUE POPULAIRE', 'BMCE BANK', 'CREDIT DU MAROC',
    'SOCIETE GENERALE MAROC', 'BANK AL MAGHRIB', 'CREDIT AGRICOLE MAROC',
    'BMCI', 'ARAB BANK MAROC', 'CIH BANK'
]

# Entreprises marocaines par secteur avec fourchettes de montants réalistes
COMPANIES = {
    'INDUSTRIEL': {
        'companies': ['OCP SA', 'SONASID', 'LAFARGE MAROC', 'CIMAR', 'COSUMAR', 'LESIEUR CRISTAL', 'SAFIEC', 'MANAGEM'],
        'min_amount': 50000,
        'max_amount': 20000000,
        'typical_range': (100000, 5000000)
    },
    'DISTRIBUTION': {
        'companies': ['MARJANE HOLDING', 'AUCHAN MAROC', 'CARREFOUR MAROC', 'METRO MAROC', 'LABEL VIE', 'ACIMA'],
        'min_amount': 1000,
        'max_amount': 500000,
        'typical_range': (5000, 200000)
    },
    'TEXTILE': {
        'companies': ['TEXMAROC', 'COTEF MAROC', 'SOMITEX', 'STAFIL', 'DELTA INDUSTRIE', 'MANATEX'],
        'min_amount': 5000,
        'max_amount': 1000000,
        'typical_range': (10000, 300000)
    },
    'SERVICES': {
        'companies': ['LYDEC', 'REDAL', 'ONEE', 'MAROC TELECOM', 'INWI', 'ORANGE MAROC', 'BARID AL MAGHRIB'],
        'min_amount': 1000,
        'max_amount': 200000,
        'typical_range': (3000, 80000)
    }
}

# Entreprises suspectes internationales par pays
SUSPECT_INTERNATIONAL_COMPANIES = {
    'NG': ['NIGERIAN OIL LTD', 'LAGOS TRADING', 'AFRICA IMPORT EXPORT'],
    'TR': ['ISTANBUL TRADING', 'TURKISH TEXTILE', 'BOSPHORUS EXPORTS'],
    'RU': ['MOSCOW TRADING', 'RUSSIAN GAS LTD', 'SIBERIAN MINERALS'],
    'UA': ['UKRAINIAN STEEL', 'KYIV INDUSTRIES', 'BLACK SEA TRADING'],
    'PK': ['PAKISTAN TEXTILE', 'KARACHI EXPORTS', 'ISLAMABAD TRADING'],
    'IN': ['INDIAN SOFTWARE', 'BOMBAY TRADING', 'DELHI IMPORTS'],
    'CN': ['CHINA MANUFACTURING', 'SHENZHEN ELECTRONICS', 'BEIJING TRADING'],
    'VN': ['VIETNAM GARMENTS', 'HANOI TEXTILE', 'SAIGON EXPORTS'],
    'BR': ['BRAZIL COMMODITIES', 'RIO TRADING', 'SAO PAULO EXPORTS'],
    'CO': ['COLOMBIAN COFFEE', 'BOGOTA TRADING', 'MEDELLIN EXPORTS']
}

def generate_realistic_amount(sector, is_fraud=False):
    """Génère des montants réalistes selon le secteur, avec anomalies pour les fraudes"""
    sector_info = COMPANIES[sector]
    if is_fraud:
        # Différents types de fraudes sur les montants
        fraud_type = random.choice(['very_high', 'very_low', 'borderline_high', 'borderline_low', 'sector_mismatch'])
        if fraud_type == 'very_high':
            return random.randint(sector_info['max_amount'] * 3, sector_info['max_amount'] * 10)
        elif fraud_type == 'very_low':
            return random.randint(1, sector_info['min_amount'] // 10)
        elif fraud_type == 'borderline_high':
            # Montant juste au-dessus du max normal
            return random.randint(sector_info['max_amount'] + 1, int(sector_info['max_amount'] * 1.5))
        elif fraud_type == 'borderline_low':
            # Montant juste en dessous du min normal
            return random.randint(int(sector_info['min_amount'] * 0.5), sector_info['min_amount'] - 1)
        else: # sector_mismatch
            # Montant normal pour un autre secteur
            other_sector = random.choice([s for s in COMPANIES.keys() if s != sector])
            other_sector_info = COMPANIES[other_sector]
            return random.randint(other_sector_info['min_amount'], other_sector_info['max_amount'])
    else:
        typical_min, typical_max = sector_info['typical_range']
        return random.randint(typical_min, typical_max)

def generate_realistic_transactions(n_samples=10000, fraud_ratio=0.05):
    """Génère un dataset réaliste de transactions avec un ratio de fraude spécifié"""
    data = []
    fraud_count = 0
    normal_count = 0
    
    while len(data) < n_samples:
        is_fraud = np.random.random() < fraud_ratio
        date = datetime.now() - timedelta(days=random.randint(1, 730))
        debtor_city = random.choice(list(MOROCCAN_CITIES.keys()))
        debtor_postcode = random.choice(MOROCCAN_CITIES[debtor_city])
        debtor_country = 'MA'
        sector = random.choice(list(COMPANIES.keys()))
        debtor_name = random.choice(COMPANIES[sector]['companies'])
        amount = generate_realistic_amount(sector, is_fraud)

        # Vérification que les montants frauduleux sont vraiment anormaux
        if is_fraud:
            sector_min = COMPANIES[sector]['min_amount']
            sector_max = COMPANIES[sector]['max_amount']
            if sector_min <= amount <= sector_max:
                # Si le montant est dans la fourchette normale, on saute cette itération
                continue
            fraud_count += 1
        else:
            normal_count += 1

        # Génération des informations du créancier
        if is_fraud:
            # Transactions frauduleuses: 90% vers des pays blacklistés, 10% vers des entités suspectes locales
            if random.random() < 0.9:
                creditor_country = random.choice(BLACKLIST_COUNTRIES)
                creditor_city = random.choice(BLACKLIST_CITIES)
                creditor_postcode = str(random.randint(10000, 99999))
                creditor_name = random.choice(SUSPECT_INTERNATIONAL_COMPANIES.get(creditor_country, ['SUSPECT COMPANY']))
            else:
                creditor_country = 'MA'
                creditor_city = random.choice(list(MOROCCAN_CITIES.keys()))
                creditor_postcode = random.choice(MOROCCAN_CITIES[creditor_city])
                creditor_name = random.choice(['CASH WITHDRAWAL', 'UNREGISTERED TRADER', 'FAMILY TRANSFER'])
        else:
            # Transactions normales: 85% locales, 15% internationales vers des pays non blacklistés
            if random.random() < 0.15:
                creditor_country = random.choice(['FR', 'ES', 'US', 'DE', 'GB', 'IT', 'NL', 'BE'])
                creditor_city = random.choice(['Paris', 'Madrid', 'New York', 'Frankfurt', 'London', 'Milan', 'Amsterdam', 'Brussels'])
                creditor_postcode = str(random.randint(10000, 99999))
                creditor_name = f"{creditor_city.split()[0]}_TRADING_{creditor_country}"
            else:
                creditor_country = 'MA'
                creditor_city = random.choice(list(MOROCCAN_CITIES.keys()))
                creditor_postcode = random.choice(MOROCCAN_CITIES[creditor_city])
                creditor_name = random.choice(MOROCCAN_BANKS + COMPANIES[random.choice(list(COMPANIES.keys()))]['companies'])

        # Calcul de la distance (approximative)
        if debtor_country != creditor_country:
            distance_km = random.randint(1000, 10000)  # Distance internationale
        else:
            # Distance nationale basée sur l'index des villes
            city_index_diff = abs(list(MOROCCAN_CITIES.keys()).index(debtor_city) - 
                                 list(MOROCCAN_CITIES.keys()).index(creditor_city))
            distance_km = city_index_diff * 100 + random.randint(10, 200)
        
        is_international = 1 if debtor_country != creditor_country else 0
        debtor_blacklisted = 1 if debtor_country in BLACKLIST_COUNTRIES or debtor_city in BLACKLIST_CITIES else 0
        creditor_blacklisted = 1 if creditor_country in BLACKLIST_COUNTRIES or creditor_city in BLACKLIST_CITIES else 0
        
        # Définition des features pour l'apprentissage automatique
        extreme_amount = 1 if is_fraud else 0
        amount_high = 1 if amount > COMPANIES[sector]['max_amount'] else 0
        amount_low = 1 if amount < COMPANIES[sector]['min_amount'] else 0
        
        # Incohérences postales pour certaines fraudes
        postal_incoherence = 0
        if is_fraud and random.random() < 0.3:
            postal_incoherence = 1
        
        if postal_incoherence and creditor_country == 'MA':
            creditor_postcode = str(random.randint(10000, 99999))  # Code postal incohérent
        
        # Heures inhabituelles pour certaines fraudes
        if is_fraud and random.random() < 0.3:
            date = date.replace(hour=random.choice([2, 3, 4]))  # Tôt le matin

        data.append({
            'transaction_id': f"TXN_{len(data):06d}",
            'timestamp': date,
            'intrbk_sttlm_amt': amount,
            'debtor_name': debtor_name,
            'debtor_country': debtor_country,
            'debtor_city': debtor_city,
            'debtor_postcode': debtor_postcode,
            'creditor_name': creditor_name,
            'creditor_country': creditor_country,
            'creditor_city': creditor_city,
            'creditor_postcode': creditor_postcode,
            'distance_km': distance_km,
            'is_international': is_international,
            'debtor_blacklisted': debtor_blacklisted,
            'creditor_blacklisted': creditor_blacklisted,
            'extreme_amount': extreme_amount,
            'amount_high': amount_high,
            'amount_low': amount_low,
            'postal_incoherence': postal_incoherence,
            'sector': sector,
            'is_fraud': int(is_fraud)
        })
    
    print(f"Génération terminée: {fraud_count} fraudes, {normal_count} normales")
    return pd.DataFrame(data)

# Génération du dataset
print("Génération d'un dataset de 10000 transactions avec 5% de fraude...")
df = generate_realistic_transactions(n_samples=10000, fraud_ratio=0.05)

# Sauvegarde du dataset
df.to_csv('moroccan_transactions_dataset.csv', index=False)
print("Dataset sauvegardé sous 'moroccan_transactions_dataset.csv'")

# Affichage de quelques exemples
print("\nQuelques exemples de transactions frauduleuses:")
fraud_examples = df[df['is_fraud'] == 1].head(3)
for _, row in fraud_examples.iterrows():
    print(f"ID: {row['transaction_id']}, Montant: {row['intrbk_sttlm_amt']:,} MAD, " +
          f"Débiteur: {row['debtor_name']}, Créancier: {row['creditor_name']} ({row['creditor_country']})")

print("\nQuelques exemples de transactions normales:")
normal_examples = df[df['is_fraud'] == 0].head(3)
for _, row in normal_examples.iterrows():
    print(f"ID: {row['transaction_id']}, Montant: {row['intrbk_sttlm_amt']:,} MAD, " +
          f"Débiteur: {row['debtor_name']}, Créancier: {row['creditor_name']} ({row['creditor_country']})")

def prepare_features_for_training(df):
    df = df.copy()
    df['intrbk_sttlm_amt_log'] = np.log1p(df['intrbk_sttlm_amt'].clip(lower=0) + 1e-6)
    
    if 'amount_low' not in df.columns:
        df['amount_low'] = 0
        for sector, info in COMPANIES.items():
            sector_mask = df['sector'] == sector
            df.loc[sector_mask, 'amount_low'] = (df.loc[sector_mask, 'intrbk_sttlm_amt'] < info['min_amount']).astype(int)
    
    # La feature 'postal_incoherence' est intentionnellement exclue de la liste des features pour l'entraînement.
    features = [
        'intrbk_sttlm_amt_log',
        'is_international',
        'distance_km',
        'debtor_blacklisted',
        'creditor_blacklisted',
        'extreme_amount',
        'amount_high',
        'amount_low',
    ]
    
    valid_features = [f for f in features if f in df.columns]
    
    return df[valid_features], df['is_fraud']

def train_and_save_model():
    print("Génération du dataset équilibré et diversifié pour les montants...")
    
    normal_df = generate_realistic_transactions(n_samples=8000, fraud_ratio=0.02)
    fraud_df = generate_realistic_transactions(n_samples=2000, fraud_ratio=0.98)
    
    df = pd.concat([normal_df, fraud_df], ignore_index=True)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    
    print(f"Distribution des classes: {df['is_fraud'].value_counts()}")
    df.to_csv('moroccan_transactions_dataset_v3.csv', index=False)

    X, y = prepare_features_for_training(df)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Meilleure configuration XGBoost pour une meilleure sensibilité aux montants
    model = XGBClassifier(
        n_estimators=300, # Augmenter le nombre d'estimateurs pour une meilleure précision
        max_depth=6,      # Augmenter la profondeur pour capturer des interactions plus complexes
        learning_rate=0.03, # Réduire le learning rate
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        scale_pos_weight=len(y_train[y_train==0]) / len(y_train[y_train==1]),
        eval_metric='logloss',
        use_label_encoder=False,
        reg_alpha=0.3, # Plus de régularisation pour éviter l'overfitting
        reg_lambda=0.3,
        early_stopping_rounds=40 # Plus de marge pour l'early stopping
    )

    model.fit(X_train_scaled, y_train, eval_set=[(X_test_scaled, y_test)], verbose=10)

    os.makedirs('models', exist_ok=True)
    joblib.dump(model, 'models/xgboost_fraud_v1.joblib')
    joblib.dump(scaler, 'models/scaler_fraud_v1.joblib')

    feature_info = {
        'expected_features': X.columns.tolist(),
        'feature_importances': dict(zip(X.columns, model.feature_importances_)),
        'blacklist_countries': BLACKLIST_COUNTRIES,
        'blacklist_cities': BLACKLIST_CITIES,
        'sector_norms': {sector: {'min': COMPANIES[sector]['min_amount'], 
                                 'max': COMPANIES[sector]['max_amount']} 
                        for sector in COMPANIES}
    }
    joblib.dump(feature_info, 'models/feature_info.joblib')

    print("✅ Nouveau modèle équilibré sauvegardé !")
    return model, scaler, df

def load_fraud_model():
    try:
        model = joblib.load('models/xgboost_fraud_v1.joblib')
        scaler = joblib.load('models/scaler_fraud_v1.joblib')
        feature_info = joblib.load('models/feature_info.joblib')
        print("✅ Modèle, scaler et features chargés avec succès !")
        return model, scaler, feature_info
    except Exception as e:
        print(f"Erreur lors du chargement: {e}")
        return None, None, None
        
if __name__ == "__main__":
    print("=== ENTRAÎNEMENT DU MODÈLE ===")
    model, scaler, dataset = train_and_save_model()

    print("\n=== TEST DU MODÈLE ===")
    model, scaler, feature_info = load_fraud_model()
    if model:
        test_df = generate_realistic_transactions(n_samples=10, fraud_ratio=0.5)
        X_test, y_test = prepare_features_for_training(test_df)
        
        X_test_model_ready = pd.DataFrame(index=X_test.index)
        for feature in feature_info['expected_features']:
            if feature in X_test.columns:
                X_test_model_ready[feature] = X_test[feature]
            else:
                X_test_model_ready[feature] = 0
        
        X_test_scaled = scaler.transform(X_test_model_ready)
        predictions = model.predict(X_test_scaled)
        probabilities = model.predict_proba(X_test_scaled)[:, 1]
        test_df['predicted_fraud'] = predictions
        test_df['fraud_probability'] = probabilities
        print(test_df[['transaction_id', 'intrbk_sttlm_amt', 'predicted_fraud', 'fraud_probability']])