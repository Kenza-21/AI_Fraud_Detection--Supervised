import streamlit as st
import json
import os
import pandas as pd


CONFIG_DIR = "config"
CONFIG_FILE = os.path.join(CONFIG_DIR, "rules_config.json")

def load_rules():
    """Load rules from the JSON file."""
    if not os.path.exists(CONFIG_FILE):
        return {
            "BLACKLIST_COUNTRIES": ['NG', 'TR', 'RU', 'UA', 'PK', 'IN', 'CN', 'VN', 'BR', 'CO'],
            "BLACKLIST_CITIES": ['Lagos', 'Istanbul', 'Moscow', 'Kyiv', 'Karachi', 'Mumbai', 'Beijing', 'Ho Chi Minh City', 'Rio de Janeiro', 'Bogota'],
            "INTERNATIONAL_DISTANCE_THRESHOLD": 1000000,
            "HIGH_AMOUNT_PERCENTILE": 99,
            "RULE_BASED_SCORE_THRESHOLD": 1.5,
            "AI_SCORE_THRESHOLD": 0.4
        }
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except UnicodeDecodeError:
        # Try Latin-1 if UTF-8 fails
        try:
            with open(CONFIG_FILE, 'r', encoding='latin-1') as f:
                return json.load(f)
        except json.JSONDecodeError:
            st.error("Erreur de format dans le fichier de configuration des règles. Réinitialisation des paramètres.")
            return get_default_rules()
    except json.JSONDecodeError:
        st.error("Erreur de format dans le fichier de configuration des règles. Réinitialisation des paramètres.")
        return get_default_rules()

def get_default_rules():
    """Return default rules to avoid code duplication."""
    return {
        "BLACKLIST_COUNTRIES": ['NG', 'TR', 'RU', 'UA', 'PK', 'IN', 'CN', 'VN', 'BR', 'CO'],
        "BLACKLIST_CITIES": ['Lagos', 'Istanbul', 'Moscow', 'Kyiv', 'Karachi', 'Mumbai', 'Beijing', 'Ho Chi Minh City', 'Rio de Janeiro', 'Bogota'],
        "INTERNATIONAL_DISTANCE_THRESHOLD": 1000000,
        "HIGH_AMOUNT_PERCENTILE": 99,
        "RULE_BASED_SCORE_THRESHOLD": 1.5,
        "AI_SCORE_THRESHOLD": 0.4
    }

def save_rules(rules):
    """Save rules to the JSON file."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
       json.dump(rules, f, indent=4, ensure_ascii=True)


def show_customization_tab():
    
    st.markdown('<h2 class="section-title">Personnalisation des Règles de Détection</h2>', unsafe_allow_html=True)
    st.info("Modifiez les paramètres ci-dessous pour ajuster les règles métier et les seuils de détection.")

    current_rules = load_rules()

    with st.form("rules_form"):
        st.subheader("Règles de Blacklist")
        new_countries_str = st.text_input(
            "Pays sur liste noire (codes à deux lettres, séparés par une virgule)",
            value=", ".join(current_rules.get("BLACKLIST_COUNTRIES", []))
        )
        new_cities_str = st.text_input(
            "Villes sur liste noire (séparées par une virgule)",
            value=", ".join(current_rules.get("BLACKLIST_CITIES", []))
        )

        st.subheader("Seuils et Paramètres")
        new_distance = st.number_input(
            "Distance internationale minimale (km)",
            min_value=0,
            value=current_rules.get("INTERNATIONAL_DISTANCE_THRESHOLD", 1000000)
        )
        new_high_amount_percentile = st.slider(
            "Seuil de montant élevé (en percentile)",
            min_value=90,
            max_value=99,
            value=current_rules.get("HIGH_AMOUNT_PERCENTILE", 99)
        )
        new_rule_threshold = st.slider(
            "Seuil de score des règles métier",
            min_value=0.0,
            max_value=5.0,
            step=0.1,
            value=current_rules.get("RULE_BASED_SCORE_THRESHOLD", 1.5)
        )
        new_ai_threshold = st.slider(
            "Seuil de score normalisé de l'IA",
            min_value=0.0,
            max_value=1.0,
            step=0.01,
            value=current_rules.get("AI_SCORE_THRESHOLD", 0.4)
        )

        submitted = st.form_submit_button("Sauvegarder les modifications")
        if submitted:
            new_rules = {
                "BLACKLIST_COUNTRIES": [c.strip().upper() for c in new_countries_str.split(',')],
                "BLACKLIST_CITIES": [c.strip().title() for c in new_cities_str.split(',')],
                "INTERNATIONAL_DISTANCE_THRESHOLD": new_distance,
                "HIGH_AMOUNT_PERCENTILE": new_high_amount_percentile,
                "RULE_BASED_SCORE_THRESHOLD": new_rule_threshold,
                "AI_SCORE_THRESHOLD": new_ai_threshold,
            }
            save_rules(new_rules)
            st.success("Les nouvelles règles ont été sauvegardées. L'analyse des prochains fichiers utilisera ces paramètres.")
            # Clear cache to ensure new rules are used
            st.cache_data.clear()

def get_custom_rules():
    """Fetches custom rules from the config file or returns defaults."""
    rules = load_rules()
    return rules

# Augmentez les seuils pour réduire les faux positifs
# customization.py - Modifications à apporter

def apply_custom_rules(df, rules_config):
    """Applique les règles personnalisées sur le DataFrame avec XGBoost"""
    
    # Initialiser la colonne d'anomalie basée sur les règles
    df['rule_based_anomaly'] = 0
    
    # Récupérer les configurations
    blacklist_countries = rules_config.get('BLACKLIST_COUNTRIES', [])
    rule_threshold = rules_config.get('RULE_BASED_SCORE_THRESHOLD', 1.5)
    ai_threshold = rules_config.get('AI_SCORE_THRESHOLD', 0.4)
    
    # 🔼 Appliquer les règles avec les nouveaux seuils
    # 1. Pays blacklistés
    df.loc[df['creditor_country'].isin(blacklist_countries), 'rule_based_anomaly'] = 1
    df.loc[df['debtor_country'].isin(blacklist_countries), 'rule_based_anomaly'] = 1
    
    # 2. Montants très élevés (1M MAD au lieu de 500K)
    df.loc[df['intrbk_sttlm_amt'] > 1000000, 'rule_based_anomaly'] = 1
    
    # 3. Transactions internationales avec montant élevé (250K au lieu de 100K)
    if 'is_international' in df.columns:
        df.loc[(df['is_international'] == 1) & (df['intrbk_sttlm_amt'] > 250000), 'rule_based_anomaly'] = 1
    
    # 4. Utiliser les scores combinés de XGBoost + règles métier
    # Vérifier si les colonnes de score existent
    if 'combined_score' in df.columns:
        df['final_anomaly'] = (
            (df['combined_score'] > ai_threshold) | 
            (df['rule_based_anomaly'] == 1)
        ).astype(int)
    else:
        # Fallback si les scores XGBoost ne sont pas disponibles
        df['final_anomaly'] = df['rule_based_anomaly']
    
    return df