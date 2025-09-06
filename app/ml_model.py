from sklearn.ensemble import IsolationForest
from xgboost import XGBClassifier
from sklearn.preprocessing import StandardScaler
import joblib
import os
import pandas as pd
import numpy as np
import logging
from customization import get_custom_rules
from geo_utils import geocode_and_get_postcode

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths pour les modèles
MODEL_DIR = "models"
MODEL_PATH = os.path.join(MODEL_DIR, "xgboost_fraud_v1.joblib")
SCALER_PATH = os.path.join(MODEL_DIR, "scaler_fraud_v1.joblib")

# Listes noires et règles métier
NATIONAL_BANKS = {
    'MA': {
        'ATTIJARIWAFA BANK': 'MA',
        'BANQUE POPULAIRE': 'MA',
        'BMCE BANK': 'MA',
        'CREDIT DU MAROC': 'MA',
        'SOCIETE GENERALE MAROC': 'MA'
    },
    'FR': {
        'BNP PARIBAS': 'FR',
        'SOCIETE GENERALE': 'FR',
        'CREDIT AGRICOLE': 'FR',
        'BPCE': 'FR',
        'HSBC FRANCE': 'FR'
    },
}

SECTOR_NORMS = {
    'INDUSTRIEL': {'min': 50000, 'max': 20000000},
    'DISTRIBUTION': {'min': 1000, 'max': 500000},
    'TEXTILE': {'min': 5000, 'max': 1000000},
    'SERVICES': {'min': 1000, 'max': 200000}
}

# Donner plus de poids aux vraies red flags
RISK_WEIGHTS = {
    'blacklisted_country': 4.0,
    'international_high_amount': 2.0,
    'extreme_amount_sector': 3.0,
    'domestic_low_amount': 0.5,
    'postal_incoherence': 1.0
}

def is_truly_suspicious(transaction):
    if (transaction['debtor_country'] == 'MA' and 
        transaction['creditor_country'] == 'MA' and
        transaction['amount'] < 50000):
        return max(0.3, transaction['score'])
    return transaction['score']

def is_amount_normal(amount, debtor_name, creditor_name):
    """Vérifie si le montant est normal pour le secteur"""
    sector = detect_sector(debtor_name, creditor_name)
    norms = SECTOR_NORMS.get(sector, {'min': 1000, 'max': 1000000})
    
    return norms['min'] <= amount <= norms['max']

def detect_sector(name1, name2):
    """Détecte le secteur d'activité avec plus de précision"""
    name = (str(name1) + ' ' + str(name2)).lower()
    
    # Industries lourdes
    if any(word in name for word in ['industr', 'atlas', 'matières', 'premières', 'ocp', 'ciment', 'acier', 'chimie']):
        return 'INDUSTRIEL'
    # Distribution
    elif any(word in name for word in ['distrib', 'ventes', 'commerce', 'marjane', 'auchan', 'carrefour', 'supermarkt']):
        return 'DISTRIBUTION'
    # Textile
    elif any(word in name for word in ['textile', 'habillement', 'coton', 'vêtement', 'confection']):
        return 'TEXTILE'
    # Services
    elif any(word in name for word in ['service', 'logistique', 'gestion', 'solution', 'technologie', 'informatique']):
        return 'SERVICES'
    else:
        return 'SERVICES'  # Par défaut

def normalize_city_name(city):
    """Normalise le nom de la ville pour la correspondance"""
    if not isinstance(city, str):
        return city
    city = city.strip().lower()
    variations = {
        'casablanca': 'Casablanca',
        'tanger': 'Tanger',
        'fes': 'Fès',
        'fès': 'Fès',
        'rabat': 'Rabat',
        'marrakech': 'Marrakech',
        'agadir': 'Agadir',
        'oujda': 'Oujda'
    }
    return variations.get(city, city.title())

def normalize_postcode(postcode, country):
    """Normalise le code postal pour la comparaison - FONCTION CRITIQUE"""
    if pd.isna(postcode) or postcode in [None, '', 'NaN', 'NaT']:
        return ''
    
    postcode = str(postcode).strip()
    
    # Supprimer les espaces, tirets et autres séparateurs
    postcode = ''.join(filter(str.isdigit, postcode))
    
    # Format spécifique par pays
    if country == 'MA':  # Maroc - 5 chiffres
        if len(postcode) > 5:
            postcode = postcode[:5]
        elif len(postcode) < 5:
            postcode = postcode.zfill(5)
    
    elif country == 'FR':  # France - 5 chiffres
        if len(postcode) > 5:
            postcode = postcode[:5]
        elif len(postcode) < 5:
            postcode = postcode.zfill(5)
    
    return postcode

class FraudModel:
    def __init__(self, some_param=None):
        os.makedirs(MODEL_DIR, exist_ok=True)
        # Features pour XGBoost
        self.expected_features = [
            'intrbk_sttlm_amt_log', 
            'is_international', 
            'distance_km',
            'debtor_blacklisted',
            'creditor_blacklisted',
            'extreme_amount',
            'amount_high',
            'amount_low',
        ]
        self.model = self._load_model()
        self.scaler = self._load_scaler()
        self.some_param = some_param

    def _load_model(self):
        if not os.path.exists(MODEL_PATH):
            logger.warning("Aucun modèle XGBoost trouvé - création d'un nouveau modèle par défaut")
            return XGBClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                scale_pos_weight=10
            )
        try:
            return joblib.load(MODEL_PATH)
        except Exception as e:
            logger.error(f"Erreur chargement modèle XGBoost: {e}")
            return None

    def _load_scaler(self):
        if not os.path.exists(SCALER_PATH):
            logger.warning("Aucun scaler trouvé - un nouveau sera créé si nécessaire")
            return None
        try:
            return joblib.load(SCALER_PATH)
        except Exception as e:
            logger.error(f"Erreur chargement scaler: {e}")
            return None

    def validate_features(self, df):
        missing = [f for f in self.expected_features if f not in df.columns]
        if missing:
            logger.warning(f"Features manquantes: {missing} - valeurs par défaut utilisées")
            for feature in missing:
                if feature in ['debtor_blacklisted', 'creditor_blacklisted', 'extreme_amount', 'amount_high', 'amount_low']:
                    df[feature] = 0
                elif feature == 'distance_km':
                    df[feature] = 0.0
                elif feature == 'is_international':
                    df[feature] = 0
        return True, []

    def standardize_amount_column(self, df):
        if 'intrbk_sttlm_amt' not in df.columns:
            if 'instd_amt' in df.columns:
                df.rename(columns={'instd_amt': 'intrbk_sttlm_amt'}, inplace=True)
            else:
                raise ValueError("Colonne de montant manquante (instd_amt ou intrbk_sttlm_amt)")
        
        df['intrbk_sttlm_amt'] = df['intrbk_sttlm_amt'].fillna(0)
        df['intrbk_sttlm_amt_log'] = np.log1p(df['intrbk_sttlm_amt'].clip(lower=0) + 1e-6)
        
        if 'distance_km' not in df.columns:
            logger.warning("Colonne distance_km manquante - création avec valeur par défaut 0")
            df['distance_km'] = 0.0
            
        return df
     
    def prepare_features_for_prediction(self, df):
        """Prépare les features pour XGBoost"""
        df = self.standardize_amount_column(df)
        
        model_features = getattr(self.model, 'feature_names_in_', None)
        expected_features = model_features if model_features is not None else self.expected_features
        
        for feature in expected_features:
            if feature not in df.columns:
                if feature == 'distance_km':
                    df[feature] = 0.0
                elif feature == 'is_international':
                    df[feature] = (df.get('debtor_country', 'MA') != df.get('creditor_country', 'MA')).astype(int)
                elif feature in ['debtor_blacklisted', 'creditor_blacklisted', 'extreme_amount', 
                                 'amount_high', 'amount_low']:
                    df[feature] = 0
                else:
                    logger.warning(f"Feature {feature} manquante - valeur par défaut 0")
                    df[feature] = 0
        
        df.loc[:, 'sector'] = df.apply(lambda row: detect_sector(row['debtor_name'], row['creditor_name']), axis=1)
        df.loc[:, 'amount_low'] = df.apply(
            lambda row: 1 if row['intrbk_sttlm_amt'] < SECTOR_NORMS.get(row['sector'], {'min': 1000})['min'] else 0,
            axis=1
        )
        
        return df

    def apply_business_rules(self, df):
        rules = get_custom_rules()

        BLACKLIST_COUNTRIES = set(rules.get('BLACKLIST_COUNTRIES', []))
        BLACKLIST_CITIES = set(rules.get('BLACKLIST_CITIES', []))
        INTERNATIONAL_DISTANCE_THRESHOLD = rules.get('INTERNATIONAL_DISTANCE_THRESHOLD', 1000000)
        HIGH_AMOUNT_PERCENTILE = rules.get('HIGH_AMOUNT_PERCENTILE', 99)

        # Initialisation
        df.loc[:, 'rule_based_score'] = 0.0
        df.loc[:, 'rule_based_anomaly'] = False

        # Log pour débogage
        logger.info(f"Pays blacklistés configurés: {BLACKLIST_COUNTRIES}")
        logger.info(f"Villes blacklistées configurées: {BLACKLIST_CITIES}")

        # --- CORRECTION: Pays blacklistés - Vérification séparée ---
        debtor_country_blacklisted = df['debtor_country'].isin(BLACKLIST_COUNTRIES)
        creditor_country_blacklisted = df['creditor_country'].isin(BLACKLIST_COUNTRIES)

        df.loc[debtor_country_blacklisted, 'rule_based_score'] += RISK_WEIGHTS['blacklisted_country']
        df.loc[creditor_country_blacklisted, 'rule_based_score'] += RISK_WEIGHTS['blacklisted_country']

        # --- Villes blacklistées ---
        debtor_city_blacklisted = df['debtor_city'].isin(BLACKLIST_CITIES)
        creditor_city_blacklisted = df['creditor_city'].isin(BLACKLIST_CITIES)

        df.loc[debtor_city_blacklisted, 'rule_based_score'] += RISK_WEIGHTS['blacklisted_country'] * 0.5
        df.loc[creditor_city_blacklisted, 'rule_based_score'] += RISK_WEIGHTS['blacklisted_country'] * 0.5

        # Mettre à jour les flags combinés
        df.loc[:, 'debtor_blacklisted'] = (debtor_country_blacklisted | debtor_city_blacklisted).astype(int)
        df.loc[:, 'creditor_blacklisted'] = (creditor_country_blacklisted | creditor_city_blacklisted).astype(int)

        # Log des transactions blacklistées
        blacklisted_count = (debtor_country_blacklisted | creditor_country_blacklisted).sum()
        if blacklisted_count > 0:
            logger.info(f"Transactions avec pays blacklistés détectées: {blacklisted_count}")

        # --- International ---
        if 'is_international' not in df.columns:
            df.loc[:, 'is_international'] = (df['debtor_country'] != df['creditor_country']).astype(int)

        # --- Montants extrêmes ---
        df.loc[:, 'extreme_amount'] = (
            (df['intrbk_sttlm_amt'] < 5000) |
            (df['intrbk_sttlm_amt'] > 5000000)
        ).astype(int)
        df.loc[df['extreme_amount'] == 1, 'rule_based_score'] += 1

        # --- Distance ---
        df.loc[:, 'distance_high'] = 0
        if 'distance_km' in df.columns:
            df.loc[:, 'distance_high'] = (df['distance_km'] > INTERNATIONAL_DISTANCE_THRESHOLD).astype(int)
        df.loc[(df['is_international'] == 1) & (df['distance_high'] == 1), 'rule_based_score'] += 1

        # --- Montant élevé (percentile) ---
        high_amount_threshold = df['intrbk_sttlm_amt'].quantile(0.97) if len(df) > 10 else 100000
        df.loc[:, 'amount_high'] = (df['intrbk_sttlm_amt'] > high_amount_threshold).astype(int)
        df.loc[(df['is_international'] == 1) & (df['amount_high'] == 1), 'rule_based_score'] += 0.5

        # --- CORRECTION CRITIQUE: Incohérence codes postaux ---
        if 'debtor_postcode' in df.columns and 'debtor_city' in df.columns and 'debtor_country' in df.columns:
            df.loc[:, 'expected_postcode_debtor'] = df.apply(
                lambda row: geocode_and_get_postcode(row['debtor_city'], row['debtor_country']),
                axis=1
            )
            
            # Normalisation avant comparaison
            df.loc[:, 'normalized_debtor_postcode'] = df.apply(
                lambda row: normalize_postcode(row['debtor_postcode'], row['debtor_country']),
                axis=1
            )
            df.loc[:, 'normalized_expected_debtor'] = df.apply(
                lambda row: normalize_postcode(row['expected_postcode_debtor'], row['debtor_country']),
                axis=1
            )
            
            # Comparaison avec tolérance
            df.loc[:, 'postal_incoherence_debtor'] = ~(
                (df['normalized_debtor_postcode'] == df['normalized_expected_debtor']) |
                (df['normalized_debtor_postcode'].str[:2] == df['normalized_expected_debtor'].str[:2])
            )
            df.loc[df['postal_incoherence_debtor'].fillna(False), 'rule_based_score'] += 0.5

        if 'creditor_postcode' in df.columns and 'creditor_city' in df.columns and 'creditor_country' in df.columns:
            df.loc[:, 'expected_postcode_creditor'] = df.apply(
                lambda row: geocode_and_get_postcode(row['creditor_city'], row['creditor_country']),
                axis=1
            )
            
            # Normalisation avant comparaison
            df.loc[:, 'normalized_creditor_postcode'] = df.apply(
                lambda row: normalize_postcode(row['creditor_postcode'], row['creditor_country']),
                axis=1
            )
            df.loc[:, 'normalized_expected_creditor'] = df.apply(
                lambda row: normalize_postcode(row['expected_postcode_creditor'], row['creditor_country']),
                axis=1
            )
            
            # Comparaison avec tolérance
            df.loc[:, 'postal_incoherence_creditor'] = ~(
                (df['normalized_creditor_postcode'] == df['normalized_expected_creditor']) |
                (df['normalized_creditor_postcode'].str[:2] == df['normalized_expected_creditor'].str[:2])
            )
            df.loc[df['postal_incoherence_creditor'].fillna(False), 'rule_based_score'] += 0.5

        # --- Montants absolument extrêmes ---
        df.loc[:, 'extreme_amount_absolute'] = (
            (df['intrbk_sttlm_amt'] > 10000000) |
            (df['intrbk_sttlm_amt'] < 100)
        ).astype(int)
        df.loc[df['extreme_amount_absolute'] == 1, 'rule_based_score'] += 0.5

        # --- Incohérence banque-pays ---
        df.loc[:, 'bank_country_mismatch'] = False
        for country_code, banks in NATIONAL_BANKS.items():
            for bank_name, origin_country in banks.items():
                debtor_mask = (
                    df['debtor_name'].str.contains(bank_name, case=False) &
                    (df['debtor_country'] != origin_country)
                )
                creditor_mask = (
                    df['creditor_name'].str.contains(bank_name, case=False) &
                    (df['creditor_country'] != origin_country)
                )
                df.loc[debtor_mask, 'bank_country_mismatch'] = True
                df.loc[creditor_mask, 'bank_country_mismatch'] = True
        df.loc[df['bank_country_mismatch'], 'rule_based_score'] += 1

        # --- Détection finale ---
        df.loc[:, 'rule_based_anomaly'] = df['rule_based_score'] >= 1.5

        return df

    def apply_ai_detection(self, df):
        """Applique la détection IA sur le DataFrame"""
        df.loc[:, 'ai_score'] = 0.0
        df.loc[:, 'ai_anomaly'] = 0
        df.loc[:, 'ai_probability'] = 0.0

        valid, missing = self.validate_features(df)
        if not valid:
            logger.error(f"Features manquantes pour AI: {missing}")
            return df

        model_features = getattr(self.model, 'feature_names_in_', None)
        expected_features = model_features if model_features is not None else self.expected_features
        
        # S'assurer que les features sont bien présentes
        for feature in expected_features:
            if feature not in df.columns:
                df[feature] = 0 

        features = df[expected_features].copy()
        
        if self.scaler is not None:
            features_scaled = self.scaler.transform(features)
            features = pd.DataFrame(features_scaled, columns=features.columns, index=features.index)

        if self.model is not None:
            try:
                df.loc[:, 'ai_probability'] = self.model.predict_proba(features)[:, 1]
                df.loc[:, 'ai_anomaly'] = (df['ai_probability'] > 0.5).astype(int)
                df.loc[:, 'ai_score'] = df['ai_probability']
            except Exception as e:
                logger.error(f"Erreur prédiction XGBoost: {e}")
                df.loc[:, 'ai_anomaly'] = 0
                df.loc[:, 'ai_probability'] = 0.0
        else:
            logger.warning("Modèle XGBoost non chargé - scores AI non calculés")
        
        return df

    def detect_anomalies(self, df):
        """Détecte les anomalies dans le DataFrame"""
        df = df.copy()
        
        df = self.prepare_features_for_prediction(df)
        df = self.apply_business_rules(df)
        df = self.apply_ai_detection(df)
        
        df['is_domestic_low'] = (
            (df['debtor_country'] == 'MA') & 
            (df['creditor_country'] == 'MA') & 
            (df['intrbk_sttlm_amt'] < 50000)
        )
        df.loc[df['is_domestic_low'], 'rule_based_score'] = df.loc[df['is_domestic_low'], 'rule_based_score'] * 0.3
        df.loc[df['is_domestic_low'], 'ai_probability'] = df.loc[df['is_domestic_low'], 'ai_probability'] * 0.3
        
        df['sector_normal'] = df.apply(
            lambda row: is_amount_normal(
                row['intrbk_sttlm_amt'], 
                row['debtor_name'], 
                row['creditor_name']
            ), axis=1
        )
        
        df.loc[df['sector_normal'], 'ai_anomaly'] = 0
        df.loc[df['sector_normal'], 'rule_based_anomaly'] = 0
        df.loc[df['sector_normal'], 'ai_probability'] = 0.0

        df.loc[:, 'rule_score_norm'] = df['rule_based_score'] / 3.5
        df.loc[:, 'ai_score_norm'] = df['ai_probability']
        df.loc[:, 'combined_score'] = 0.6 * df['rule_score_norm'] + 0.4 * df['ai_score_norm']
        
        df.loc[:, 'is_anomaly'] = (
            (df['combined_score'] > 0.5) |
            (df['rule_based_anomaly']) | 
            (df['ai_anomaly'] == 1)
        ).astype(int)
        
        blacklisted_mask = (df['debtor_blacklisted'] == 1) | (df['creditor_blacklisted'] == 1)
        df.loc[blacklisted_mask, 'is_anomaly'] = 1
        
        df.loc[df['is_domestic_low'], 'is_anomaly'] = 0
        df.loc[df['is_domestic_low'], 'rule_based_anomaly'] = 0
        df.loc[df['is_domestic_low'], 'ai_anomaly'] = 0

        df = self.explain_anomalies(df)
        return df.reset_index(drop=True)
    
    def explain_anomalies(self, df):
        if 'is_anomaly' not in df.columns:
            return df
        
        rules = get_custom_rules()
        AI_SCORE_THRESHOLD = rules.get('AI_SCORE_THRESHOLD', 0.5)

        def get_reasons(row):
            reasons = []

            # --- CORRECTION: Vérification directe des pays et villes blacklistés ---
            rules = get_custom_rules()
            BLACKLIST_COUNTRIES = set(rules.get('BLACKLIST_COUNTRIES', []))
            BLACKLIST_CITIES = set(rules.get('BLACKLIST_CITIES', []))
            
            # Vérification des pays blacklistés
            if row['debtor_country'] in BLACKLIST_COUNTRIES:
                reasons.append(f"Débiteur blacklisté ({row['debtor_country']})")
            if row['creditor_country'] in BLACKLIST_COUNTRIES:
                reasons.append(f"Créancier blacklisté ({row['creditor_country']})")
            
            # Vérification des villes blacklistées
            if row['debtor_city'] in BLACKLIST_CITIES:
                reasons.append(f"Ville débiteur blacklistée ({row['debtor_city']})")
            if row['creditor_city'] in BLACKLIST_CITIES:
                reasons.append(f"Ville créancier blacklistée ({row['creditor_city']})")

            if row.get('is_international', False) and row.get('distance_high', False):
                reasons.append("Transaction internationale longue distance")
            if row.get('is_international', False) and row.get('high_amount', False):
                reasons.append("Montant élevé international")
            if row.get('extreme_amount', False):
                if row['intrbk_sttlm_amt'] > 5000000:
                    reasons.append("Montant extrêmement élevé (>5M MAD)")
                elif row['intrbk_sttlm_amt'] < 5000:
                    reasons.append("Montant extrêmement bas (<5K MAD)")
            elif row.get('high_amount', False):
                reasons.append("Montant élevé (500K-10M MAD)")
            if row.get('postal_incoherence_debtor', False):
                reasons.append("Incohérence postale débiteur")
            if row.get('postal_incoherence_creditor', False):
                reasons.append("Incohérence postale créancier")
            if row.get('bank_country_mismatch', False):
                reasons.append("Incohérence banque/pays")
            if row.get('ai_anomaly', 0) == 1:
                reasons.append("Détection IA")

            return "Transaction normale" if not reasons else ", ".join(reasons)

        df.loc[:, 'anomaly_reasons'] = df.apply(get_reasons, axis=1)
        return df

    def train_model(self, X_train, y_train):
        """Méthode pour entraîner le modèle XGBoost"""
        logger.info("Entraînement du modèle XGBoost...")
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        
        try:
            self.model.fit(X_train_scaled, y_train)
            joblib.dump(self.model, MODEL_PATH)
            joblib.dump(self.scaler, SCALER_PATH)
            logger.info("Modèle XGBoost et Scaler entraînés et sauvegardés")
        except Exception as e:
            logger.error(f"Erreur lors de l'entraînement: {e}")