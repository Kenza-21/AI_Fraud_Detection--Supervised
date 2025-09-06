# main.py
import streamlit as st
import pandas as pd

import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from validation import validate_xml_with_xsd
from etl import extract_transactions, transform_data
from ml_model import FraudModel
from report_generator import ReportGenerator
from db_operations import db_manager
import os
from email_sender import send_email_with_report
from customization import show_customization_tab
from auth import check_authentication, show_login_register, logout
from profile import show_auth_card, get_avatar_initials,get_avatar_color,show_user_profile_menu, show_profile_tab, show_edit_profile

from admin_dashboard import show_admin_dashboard



# Vérification de l'authentification
# Remplacer toute la section de vérification d'authentification par:
if not check_authentication():
    # Afficher la carte d'authentification
    col_nav_logo, col_nav_space = st.columns([10, 10])
    with col_nav_logo:
        st.image("app/style/logo_E.png", width=250)
    
    st.markdown("---")
    show_auth_card()
    st.stop()
    
    st.markdown("---")
    st.markdown("""
    <div class="main-header">
        <h1>Système de Détection de Fraude Bancaire</h1>
        <p>Veuillez vous connecter ou créer un compte pour accéder à l'application</p>
    </div>
    """, unsafe_allow_html=True)
    
    show_login_register()
    st.stop()



# Configuration de la page
st.set_page_config(
    page_title="Système de Détection de Fraude",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

col_nav_logo, col_nav_space = st.columns([10, 10])

with col_nav_logo:
    st.image("app/style/logo_E.png", width=250)


st.markdown("---")


try:
    with open("app/style/styles.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    st.error("Le fichier de style 'app/style/styles.css' est introuvable. Veuillez vous assurer qu'il se trouve bien dans un dossier 'app/style' à la racine de votre projet.")

# Import de la police Inter depuis Google Fonts
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
""", unsafe_allow_html=True)



with st.sidebar:
    
    st.markdown("---")


# Initialisation de la session state
if "df_combined" not in st.session_state:
    st.session_state.df_combined = None
if "all_xml_contents" not in st.session_state:
    st.session_state.all_xml_contents = []
if "all_dfs" not in st.session_state:
    st.session_state.all_dfs = []
    
# Ajouter l'initialisation de selected_page
if "selected_page" not in st.session_state:
    st.session_state.selected_page = "Upload XML"
if "editing_profile" not in st.session_state:
    st.session_state.editing_profile = False    
    
    
def display_transaction_summary(df):
    """Affiche un résumé des transactions avec design moderne"""
    total_transactions = len(df)
    total_amount = df['intrbk_sttlm_amt'].sum()
    avg_amount = df['intrbk_sttlm_amt'].mean()
    anomalies = df[df['is_anomaly'] == 1]
    anomaly_percentage = (len(anomalies) / total_transactions * 100) if total_transactions > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <h3>Transactions</h3>
            <h1>{total_transactions:,}</h1>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <h3>Montant Total</h3>
            <h1>{total_amount:,.0f} <small>MAD</small></h1>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <h3>Montant Moyen</h3>
            <h1>{avg_amount:,.0f} <small>MAD</small></h1>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <h3>Anomalies</h3>
            <h1>{len(anomalies)} <small>({anomaly_percentage:.1f}%)</small></h1>
        </div>
        """, unsafe_allow_html=True)
    
def display_risk_indicators(df):
    """Affiche les indicateurs de risque avec graphiques améliorés"""
    st.markdown('<h2 class="section-title">Indicateurs de Risque</h2>', unsafe_allow_html=True)
    
    # Préparation des données - utilisez 'intrbk_sttlm_amt' au lieu de 'instd_amt'
    risk_data = df[['transaction_id', 'intrbk_sttlm_amt', 'is_anomaly', 'combined_score']].copy()
    
    risk_data['risk_level'] = risk_data['combined_score'].apply(
        lambda x: 'Faible' if x < 0.3 else 'Moyen' if x < 0.6 else 'Élevé'
    )
    
    # Graphique 1: Répartition des Niveaux de Risque
    fig1 = px.pie(
        risk_data, 
        names='risk_level', 
        title='Répartition des Niveaux de Risque',
        color='risk_level',
        color_discrete_map={'Faible': '#38a169', 'Moyen': '#d69e2e', 'Élevé': '#e53e3e'}
    )
    fig1.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(74,85,104,0.8)',
        font_color='#f7fafc',
        title_font_size=16,
        title_font_color='#f7fafc'
    )
    
    # Nouveau graphique 2: Nuage de points des transactions par montant et score de risque
    fig2 = px.scatter(
        risk_data, 
        x='combined_score', 
        y='intrbk_sttlm_amt',
        color='risk_level',
        size='intrbk_sttlm_amt',
        hover_data=['transaction_id'],
        title='Montant vs. Score de Risque',
        color_discrete_map={'Faible': '#38a169', 'Moyen': '#d69e2e', 'Élevé': '#e53e3e'},
    )
    fig2.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(74,85,104,0.8)',
        font_color='#f7fafc',
        title_font_size=16,
        title_font_color='#f7fafc',
        xaxis_title="Score de Risque",
        yaxis_title="Montant (MAD)"
    )
    
    # Affichage des graphiques
    col1, col2 = st.columns(2)
    col1.plotly_chart(fig1, use_container_width=True)
    col2.plotly_chart(fig2, use_container_width=True)
    
def display_geographical_analysis(df):
    """Affiche l'analyse géographique avec carte améliorée"""
    st.markdown('<h2 class="section-title">Analyse Géographique</h2>', unsafe_allow_html=True)
    
    if 'debtor_lat' not in df.columns or 'creditor_lat' not in df.columns:
        st.warning("Données géographiques non disponibles")
        return
    
    # Préparation des données pour la carte en s'assurant que les colonnes existent
    geo_data_df = df.copy()
    geo_data_df = geo_data_df.dropna(subset=['debtor_lat', 'debtor_lon', 'creditor_lat', 'creditor_lon'])
    
    if geo_data_df.empty:
        st.info("Aucune donnée géographique valide disponible")
        return
    
    # Création d'un DataFrame pour les points
    points_df = pd.DataFrame({
        'lat': pd.concat([geo_data_df['debtor_lat'], geo_data_df['creditor_lat']]),
        'lon': pd.concat([geo_data_df['debtor_lon'], geo_data_df['creditor_lon']]),
        'is_anomaly': pd.concat([geo_data_df['is_anomaly'], geo_data_df['is_anomaly']]),
        'type': ['Débiteur'] * len(geo_data_df) + ['Créancier'] * len(geo_data_df)
    })
    
    # Création de la carte avec thème sombre
    fig = go.Figure()
    
    # Ajout des lignes entre débiteurs et créanciers pour toutes les transactions
    for index, row in geo_data_df.iterrows():
        line_color = '#e53e3e' if row['is_anomaly'] else '#3182ce'
        
        fig.add_trace(go.Scattergeo(
            lon=[row['debtor_lon'], row['creditor_lon']],
            lat=[row['debtor_lat'], row['creditor_lat']],
            mode='lines',
            line=dict(width=2, color=line_color),
            hoverinfo='none',
            showlegend=False
        ))
    
    fig.add_trace(go.Scattergeo(
        lon = points_df[points_df['type'] == 'Débiteur']['lon'],
        lat = points_df[points_df['type'] == 'Débiteur']['lat'],
        text = 'Débiteur',
        marker = dict(
            size = 10,
            color = points_df[points_df['type'] == 'Débiteur']['is_anomaly'].apply(lambda x: '#e53e3e' if x else '#3182ce'),
            line = dict(width=2, color='white')
        ),
        name = 'Débiteurs'
    ))
    
    fig.add_trace(go.Scattergeo(
        lon = points_df[points_df['type'] == 'Créancier']['lon'],
        lat = points_df[points_df['type'] == 'Créancier']['lat'],
        text = 'Créancier',
        marker = dict(
            size = 10,
            color = points_df[points_df['type'] == 'Créancier']['is_anomaly'].apply(lambda x: '#e53e3e' if x else '#38a169'),
            symbol = 'diamond',
            line = dict(width=2, color='white')
        ),
        name = 'Créanciers'
    ))
    
    # Configuration de la carte
    fig.update_geos(
        projection_type="natural earth",
        showcountries=True,
        countrycolor="#4a5568",
        bgcolor="rgba(45,55,72,0.8)",
        showocean=True,
        oceancolor="rgba(26,32,44,0.8)",
        showlakes=True,
        lakecolor="rgba(26,32,44,0.8)"
    )
    
    fig.update_layout(
        title='Flux des Transactions',
        height=600,
        margin={"r":0,"t":40,"l":0,"b":0},
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(74,85,104,0.8)',
        font_color='#f7fafc',
        title_font_size=16,
        title_font_color='#f7fafc'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
def display_temporal_analysis():
    """
    Affiche un nuage de points des anomalies temporelles.
    Chaque point représente une transaction anormale.
    """
    st.markdown('<h2 class="section-title">Analyse des Tendances Temporelles des Anomalies</h2>', unsafe_allow_html=True)

    # Récupération des données d'anomalies individuelles
    anomalies_df = db_manager.fetch_individual_anomalies()

    if anomalies_df.empty:
        st.info("Aucune anomalie enregistrée dans la base de données pour l'analyse temporelle.")
        return

    # Convertir la colonne de date en format de date pour une meilleure visualisation
    anomalies_df['anomaly_date'] = pd.to_datetime(anomalies_df['anomaly_date'])

    # Création du nuage de points
    fig = px.scatter(
        anomalies_df,
        x='anomaly_date',
        y='anomaly_score',
        color_discrete_sequence=['#e53e3e'],
        hover_data={
            'transaction_id': True,
            'anomaly_date': '|%Y-%m-%d %H:%M:%S',
            'intrbk_sttlm_amt': ':.2f',
            'anomaly_score': ':.2f',
        },
        title="Anomalies par date et score",
        labels={
            'anomaly_date': 'Date de l\'anomalie',
            'anomaly_score': 'Score d\'anomalie'
        }
    )

    # Mise à jour du layout pour un thème sombre
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(74,85,104,0.8)',
        font_color='#f7fafc',
        title_font_size=16,
        title_font_color='#f7fafc',
        xaxis_title="Date de l'anomalie",
        yaxis_title="Score d'anomalie",
        xaxis=dict(
            tickformat="%Y-%m-%d",
            showgrid=True,
            gridcolor='#606f86'
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='#606f86'
        )
    )

    st.plotly_chart(fig, use_container_width=True)
    
def display_transaction_details(df):
    """
    Affiche les détails des transactions avec filtres et un expander pour le XML.
    Affiche maintenant TOUTES les transactions (normales et anormales)
    """
    st.markdown('<h2 class="section-title">Détail des Transactions</h2>', unsafe_allow_html=True)

    # Générer un identifiant unique pour cette session d'affichage
    session_id = str(hash(str(datetime.now())))
    
    # Conteneur de filtres moderne
    with st.container(border=True):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            show_all = st.checkbox(
                "Afficher toutes les transactions",
                value=True,
                key=f"show_all_transactions_{session_id}"
            )
        with col2:
            show_anomalies = st.checkbox(
                "Afficher uniquement les transactions à risque",
                value=False,
                key=f"show_only_anomalies_{session_id}"
            )
        with col3:
            min_amount = st.number_input(
                "Montant minimum (MAD)",
                min_value=0,
                max_value=int(df['intrbk_sttlm_amt'].max()) if not df.empty else 1000000,
                value=0,
                key=f"min_amount_filter_{session_id}"
            )
        with col4:
            risk_level = st.selectbox(
                "Niveau de risque",
                ["Tous", "Faible (0-30%)", "Moyen (30-60%)", "Élevé (60-100%)"],
                key=f"risk_level_filter_{session_id}"
            )

    # Application des filtres
    filtered_df = df.copy()

    if show_anomalies:
        filtered_df = filtered_df[filtered_df['is_anomaly'] == 1]
    elif not show_all:
        # Par défaut, montrer seulement les anomalies si on ne veut pas tout voir
        filtered_df = filtered_df[filtered_df['is_anomaly'] == 1]

    filtered_df = filtered_df[filtered_df['intrbk_sttlm_amt'] >= min_amount]

    if risk_level != "Tous":
        risk_map = {"Faible (0-30%)": (0, 0.3), "Moyen (30-60%)": (0.3, 0.6), "Élevé (60-100%)": (0.6, 1)}
        min_score, max_score = risk_map[risk_level]
        filtered_df = filtered_df[
            (filtered_df['combined_score'] >= min_score) &
            (filtered_df['combined_score'] < max_score)
        ]

    # Affichage des transactions
    if filtered_df.empty:
        st.info("Aucune transaction ne correspond aux critères sélectionnés.")
        return

    # Afficher le nombre de transactions filtrées
    st.info(f"**{len(filtered_df)}** transaction(s) correspondant aux filtres "
            f"({len(filtered_df[filtered_df['is_anomaly'] == 1])} anomalie(s))")

    for idx, row in filtered_df.iterrows():
        # Définition du statut et de la classe CSS basée sur le score combiné
        if row['is_anomaly'] == 1:
            if row['combined_score'] >= 0.6:
                
                card_class = "risk-card high-risk"
                status = "Transaction à haut risque"
                icon = "🚨"
            elif row['combined_score'] >= 0.3:
                card_class = "risk-card medium-risk"
                status = "Transaction à risque moyen"
                icon = "⚠️"
            else:
                card_class = "risk-card low-risk"
                status = "Transaction suspecte"
                status = "Risque faible"
                icon = "🔶"
        else:
            
            if row['combined_score'] == 0.0:
                card_class = "risk-card normal-zero"
                status = "Transaction normale"
                icon = "✅"
            else:
                card_class = "risk-card normal"
                status = "Transaction normale"
            icon = "✅"

        # Formatage des informations
        debtor_info = f"{row['debtor_name']} ({row['debtor_country']})"
        creditor_info = f"{row['creditor_name']} ({row['creditor_country']})"
        amount = f"{row['intrbk_sttlm_amt']:,.2f} MAD"
        date = pd.to_datetime(row['transaction_date']).strftime("%d/%m/%Y %H:%M") if 'transaction_date' in row else "N/A"

        # Affichage du message d'explication
        reasons_text = row.get('anomaly_reasons', 'Aucune raison spécifique.')

        st.markdown(f"""
        <div class="{card_class}">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <h3 style="margin: 0; font-size: 1.125rem; font-weight: 600;">Transaction #{row['transaction_id']}</h3>
                <span style="font-weight: 600; font-size: 0.875rem;">{icon} {status}</span>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
                <div>
                    <p style="margin: 0.25rem 0;"><strong>Débiteur:</strong> {debtor_info}</p>
                    <p style="margin: 0.25rem 0;"><strong>Créancier:</strong> {creditor_info}</p>
                </div>
                <div>
                    <p style="margin: 0.25rem 0;"><strong>Montant:</strong> {amount}</p>
                    <p style="margin: 0.25rem 0;"><strong>Date:</strong> {date}</p>
                </div>
                <div>
                    <p style="margin: 0.25rem 0;"><strong>Score de risque:</strong> {row['combined_score']*100:.1f}%</p>
                    <p style="margin: 0.25rem 0;"><strong>Distance:</strong> {row.get('distance_km', 'N/A')} km</p>
                </div>
            </div>
            <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid rgba(255,255,255,0.1);">
                <p style="margin: 0;"><strong>Analyse:</strong> {reasons_text}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_buttons = st.columns(2)
        with col_buttons[0]:
            if st.button(f"Sauvegarder", key=f"save_{row['transaction_id']}_{idx}_{session_id}", use_container_width=True):
                with st.spinner("Sauvegarde en cours..."):
                    single_row_df = pd.DataFrame([row.to_dict()])
                    
                    # Correction ici: passer le contenu XML, pas le nom du fichier
                    file_index = row.get('file_index', 0)
                    if st.session_state.all_xml_contents and file_index < len(st.session_state.all_xml_contents):
                        xml_content_to_save = st.session_state.all_xml_contents[file_index]
                        success = db_manager.save_transactions(single_row_df, xml_content_to_save)
                    else:
                        st.error("Contenu XML introuvable pour ce fichier.")
                        success = False

                    if success:
                        st.success("Transaction sauvegardée avec succès")
                    else:
                        st.error("Erreur lors de la sauvegarde")

        with col_buttons[1]:
            # Utilisation d'un expander pour un affichage propre du XML
            with st.expander("Voir XML", expanded=False):
                file_index = row.get('file_index', 0)
                if st.session_state.all_xml_contents and file_index < len(st.session_state.all_xml_contents):
                    st.code(st.session_state.all_xml_contents[file_index], language='xml')
                else:
                    st.error("Contenu XML introuvable pour ce fichier.")

        st.markdown("---")


def display_anomalies_only(df):
    """
    Affiche uniquement les transactions anormales de manière claire
    """
    st.markdown('<h2 class="section-title">Transactions Anormales</h2>', unsafe_allow_html=True)
    
    # Filtrer seulement les anomalies
    anomalies_df = df[df['is_anomaly'] == 1].copy()
    
    if anomalies_df.empty:
        st.success("Aucune transaction anormale détectée !")
        return
    
    st.info(f"**{len(anomalies_df)}** transaction(s) anormale(s) détectée(s)")
    
    # Trier par score de risque décroissant
    anomalies_df = anomalies_df.sort_values('combined_score', ascending=False)
    
    # Statistiques des anomalies
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Transactions à haut risque", 
                 len(anomalies_df[anomalies_df['combined_score'] >= 0.6]))
                 
    with col2:
        st.metric("Transactions suspectes", 
                 len(anomalies_df[anomalies_df['combined_score'] < 0.6]))
               
    with col3:
        total_amount = anomalies_df['intrbk_sttlm_amt'].sum()
        st.metric("Montant total à risque", f"{total_amount:,.0f} MAD")
               
    
    st.markdown("---")
    
    # Afficher chaque anomalie
    for idx, row in anomalies_df.iterrows():
        if row['combined_score'] >= 0.6:
            card_class = "risk-card high-risk"
            status = "🚨 HAUT RISQUE"
        else:
            card_class = "risk-card suspicious"
            status = "⚠️ SUSPECTE"
        
        debtor_info = f"{row['debtor_name']} ({row['debtor_country']})"
        creditor_info = f"{row['creditor_name']} ({row['creditor_country']})"
        amount = f"{row['intrbk_sttlm_amt']:,.2f} MAD"
        date = pd.to_datetime(row['transaction_date']).strftime("%d/%m/%Y %H:%M") if 'transaction_date' in row else "N/A"
        
        st.markdown(f"""
        <div class="{card_class}">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <h3 style="margin: 0; font-size: 1.125rem; font-weight: 600;">Transaction #{row['transaction_id']}</h3>
                <span style="font-weight: 700; font-size: 0.875rem; color: #fff;">{status}</span>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
                <div>
                    <p style="margin: 0.25rem 0;"><strong>Débiteur:</strong> {debtor_info}</p>
                    <p style="margin: 0.25rem 0;"><strong>Créancier:</strong> {creditor_info}</p>
                </div>
                <div>
                    <p style="margin: 0.25rem 0;"><strong>Montant:</strong> {amount}</p>
                    <p style="margin: 0.25rem 0;"><strong>Date:</strong> {date}</p>
                </div>
                <div>
                    <p style="margin: 0.25rem 0;"><strong>Score de risque:</strong> {row['combined_score']*100:.1f}%</p>
                    <p style="margin: 0.25rem 0;"><strong>Raisons:</strong> {row.get('anomaly_reasons', 'Non spécifié')}</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Actions pour cette anomalie
        col_act1, col_act2 = st.columns(2)
        with col_act1:
            if st.button(" Voir détails", key=f"details_{row['transaction_id']}_{idx}", use_container_width=True):
                st.write(f"**Détails de la transaction {row['transaction_id']}:**")
                st.json({k: v for k, v in row.items() if pd.notna(v)})
        with col_act2:
            if st.button(" Sauvegarder", key=f"save_anom_{row['transaction_id']}_{idx}", use_container_width=True):
                with st.spinner("Sauvegarde..."):
                    single_row_df = pd.DataFrame([row.to_dict()])
                    
                    # Correction ici: passer le contenu XML
                    file_index = row.get('file_index', 0)
                    if st.session_state.all_xml_contents and file_index < len(st.session_state.all_xml_contents):
                        xml_content_to_save = st.session_state.all_xml_contents[file_index]
                        success = db_manager.save_transactions(single_row_df, xml_content_to_save)
                    else:
                        st.error("Contenu XML source introuvable pour cette transaction.")
                        success = False

                    if success:
                        st.success(" Transaction sauvegardée")
                    else:
                        st.error(" Erreur de sauvegarde")
        
        st.markdown("---")

def process_uploaded_file(uploaded_file, file_index=None):
    """Traite le fichier XML uploadé avec gestion robuste des index"""
    try:
        xml_content = uploaded_file.read().decode("utf-8")
        
        # Validation XML
        is_valid, message = validate_xml_with_xsd(xml_content)
        if not is_valid:
            st.error(f"Erreur de validation (Fichier {file_index+1 if file_index is not None else 1}): {message}")
            return None, None
        
        st.success(f"Fichier XML {file_index+1 if file_index is not None else 1} validé avec succès")
        
        with st.spinner(f"Extraction et analyse en cours (Fichier {file_index+1 if file_index is not None else 1})..."):
            transactions = extract_transactions(xml_content)
            df = transform_data(transactions)
            
            # Réinitialisation systématique de l'index
            df.reset_index(drop=True, inplace=True)
            
            # Vérification des données critiques
            if df.empty or 'intrbk_sttlm_amt' not in df.columns:
                st.error(f"Données transformées invalides (Fichier {file_index+1 if file_index is not None else 1})")
                return None, None
            
            fraud_model = FraudModel()
            
            try:
                df = fraud_model.detect_anomalies(df)
                df = fraud_model.explain_anomalies(df)
                
                # Ajout d'un identifiant de fichier
                df['file_index'] = file_index if file_index is not None else 0
                df['file_name'] = uploaded_file.name
                
                return df, xml_content
                
            except Exception as e:
                st.error(f"Erreur de traitement ML (Fichier {file_index+1 if file_index is not None else 1}): {str(e)}")
                return None, None
            
    except Exception as e:
        st.error(f"Erreur système (Fichier {file_index+1 if file_index is not None else 1}): {str(e)}")
        return None, None

# ==============================================================================
# 🏗️ STRUCTURE PRINCIPALE DE L'APPLICATION AVEC MENU LATÉRAL
# ==============================================================================
# --- En-tête de l'application (sous le logo) ---
st.markdown("""
<div class="main-header">
    <h1>Système de Détection de Fraude Bancaire</h1>
    <p>Analyse intelligente des fichiers PACS.008 • Détection d'anomalies en temps réel</p>
</div>
""", unsafe_allow_html=True)


    


with st.sidebar:
   
    if 'user' in st.session_state:
        user = st.session_state.user
        avatar_initials = get_avatar_initials(user.get('full_name', ''))
        avatar_color = get_avatar_color(user.get('username', ''))
        
        # Utilisez des colonnes pour aligner l'avatar et le bouton de paramètres
        col_avatar, col_settings_btn = st.columns([0.8, 0.2])
        
        with col_avatar:
            st.markdown(f"""
            <div style="text-align: center; margin-bottom: 2rem;">
                <div style="width: 100px; height: 100px; border-radius: 50%; 
                            background: {avatar_color}; display: flex; align-items: center; 
                            justify-content: center; color: white; font-weight: 600; font-size: 1.5rem;
                            margin: 0 auto; border: 3px solid #4a5568; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                            transition: transform 0.3s ease, box-shadow 0.3s ease;">
                    {avatar_initials}
                </div>
                <h3 style="color: #f7fafc; margin-top: 0.5rem; margin-bottom: 0.25rem;">{user.get('full_name', 'Utilisateur')}</h3>
                <p style="color: #a0aec0; margin: 0; font-size: 0.9rem;">{user.get('role', 'Utilisateur')}</p>
            </div>
            """, unsafe_allow_html=True)

        with col_settings_btn:
            if user.get('role') == 'admin':
    # Utilisation d'un bouton avec style minimal pour n'afficher que l'emoji
              if st.button("⚙️", key="settings_emoji_button", help="Aller à la personnalisation", use_container_width=False):
                  st.session_state.selected_page = "Personnalisation"
                  st.rerun()

    st.markdown("---")
    
    # point de navigation
    pages = ["Upload XML", "Tableau de Bord", "Transactions", "Anomalies","Rapports", "Profil"]
    if user.get('role') == 'admin':
        pages.append("Admin Dashboard")
        pages.append("Personnalisation") 
    st.markdown("---")
    st.markdown("<h3 style='color:#f7fafc; margin-bottom: 1rem;'>Navigation</h3>", unsafe_allow_html=True)

    # Initialiser la page sélectionnée
    if "selected_page" not in st.session_state:
        st.session_state.selected_page = pages[0]
    # Plus loin dans le code, ajouter la gestion de cette nouvelle page:
    
    
    st.markdown("""
    <style>
    .stButton > button:focus {
        background-color: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%) !important;  /* Couleur de fond */
        color: #f7fafc !important;
        font-weight: 500 !important;
        border: 0px solid #334155 !important;
        box-shadow: 0 0 10px #fb923c;
    }
    </style>
    """, unsafe_allow_html=True)

    # Création des boutons de navigation
    for p in pages:
        if st.button(p, key=f"sidebar_{p}", use_container_width=True):
            st.session_state.selected_page = p
            

    


if st.session_state.selected_page == "Anomalies":
      if st.session_state.df_combined is not None:
        display_anomalies_only(st.session_state.df_combined)

        
if st.session_state.selected_page == "Admin Dashboard":
       show_admin_dashboard()  
    
# ==============================================================================
#  Afficher le contenu de la page sélectionnée
# ==============================================================================
if st.session_state.selected_page == "Upload XML":
    st.markdown('<h2 class="section-title">Uploader des Fichiers XML</h2>', unsafe_allow_html=True)
    st.markdown("""
    <div style="text-align: center; padding: 2rem 1rem; color: var(--text-secondary); border: 2px dashed rgba(255,255,255,0.2); border-radius: var(--border-radius); margin-bottom: 2rem;">
        <h3>Prêt à analyser vos transactions</h3>
        <p>Uploadez un ou plusieurs fichiers XML pour commencer l'analyse de détection de fraude</p>
    </div>
    """, unsafe_allow_html=True)
    uploaded_files = st.file_uploader("", type=["xml"], accept_multiple_files=True, label_visibility="visible")

    if uploaded_files:
        all_dfs = []
        all_xml_contents = []
        
        for i, uploaded_file in enumerate(uploaded_files):
            df, xml_content = process_uploaded_file(uploaded_file, file_index=i)
            if df is not None:
                all_dfs.append(df)
                all_xml_contents.append(xml_content)
        
        if all_dfs:
            combined_df = pd.concat(all_dfs, ignore_index=True)
            st.session_state.df_combined = combined_df
            st.session_state.all_xml_contents = all_xml_contents
            st.session_state.all_dfs = all_dfs
            st.success(f"{len(all_dfs)} fichier(s) XML traité(s) avec succès")
            st.info("Naviguez vers les autres onglets pour visualiser les résultats.")

elif st.session_state.selected_page == "Tableau de Bord":
    if st.session_state.df_combined is not None:
        display_transaction_summary(st.session_state.df_combined)
        st.markdown("---")
        display_risk_indicators(st.session_state.df_combined)
        st.markdown("---")
        display_geographical_analysis(st.session_state.df_combined)
        st.markdown("---")
        display_temporal_analysis()
        st.markdown("---")
    else:
        st.warning("Veuillez d'abord uploader un fichier XML dans la page 'Upload XML'.")

elif st.session_state.selected_page == "Transactions":
    if st.session_state.df_combined is not None:
        display_transaction_details(st.session_state.df_combined)
    else:
        st.warning("Veuillez d'abord uploader un fichier XML dans la page 'Upload XML'.")

elif st.session_state.selected_page == "Rapports":
    if st.session_state.df_combined is not None:
        st.markdown('<h2 class="section-title">Générer et télécharger les rapports</h2>', unsafe_allow_html=True)
        
        st.info("Ces rapports contiennent une analyse complète de toutes les transactions importées.")

        # --- Section pour le rapport PDF ---
        st.markdown("<h4>Rapport d'analyse (PDF)</h4>", unsafe_allow_html=True)
        st.write("Ce rapport est idéal pour une vue d'ensemble et une présentation.")
        if st.button("Générer le rapport PDF", key="generate_pdf_button", use_container_width=True):
            with st.spinner("Génération du rapport PDF..."):
                pdf_path = ReportGenerator.generate_pdf(st.session_state.df_combined, title="Rapport d'analyse de transactions")
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        label="⬇️ Télécharger le rapport PDF",
                        data=f,
                        file_name="rapport_analyse_transactions.pdf",
                        mime="application/pdf",
                        key="download_pdf_final",
                        use_container_width=True
                    )
        st.markdown("---") # Séparateur visuel

        # --- Section pour le fichier Parquet ---
        st.markdown("<h4>Données pour Power BI (Parquet)</h4>", unsafe_allow_html=True)
        st.write("Le fichier Parquet est optimisé pour les outils de BI comme Power BI.")
        if st.button("Générer les données Parquet", key="generate_parquet_button", use_container_width=True):
            with st.spinner("Génération du fichier Parquet..."):
                try:
                    import pyarrow
                except ImportError:
                    st.error("La bibliothèque 'pyarrow' n'est pas installée.")
                    st.stop()
                    
                import io
                parquet_buffer = io.BytesIO()
                st.session_state.df_combined.to_parquet(parquet_buffer, index=False)
                parquet_buffer.seek(0)
                
                st.download_button(
                    label="⬇️ Télécharger le fichier Parquet",
                    data=parquet_buffer,
                    file_name="transactions_data.parquet",
                    mime="application/octet-stream",
                    key="download_parquet_final",
                    use_container_width=True
                )
        st.markdown("---") # Séparateur visuel

        # --- Section pour l'envoi par email ---
        st.markdown('<h2 class="section-title">Envoyer le rapport par email</h2>', unsafe_allow_html=True)
        st.info("Cette fonctionnalité vous permet d'envoyer le rapport par email. Entrez une adresse email ci-dessous et cliquez sur 'Envoyer'.")
        
        email = st.text_input("Adresse email du destinataire:", key="email_input")
        
        if st.button("Envoyer par mail", key="send_email_button", use_container_width=True):
            if email:
                with st.spinner("Envoi de l'email en cours..."):
                    pdf_path = ReportGenerator.generate_pdf(st.session_state.df_combined)
                    if send_email_with_report(
                        to_email=email,
                        report_path=pdf_path,
                        subject="Rapport d'analyse de fraude bancaire",
                        body="Bonjour,\n\nVeuillez trouver ci-joint le rapport d'analyse de fraude bancaire généré par l'application Streamlit."
                    ):
                        st.success(f"Le rapport a été envoyé avec succès à **{email}** !")
                    else:
                        st.error(f" Échec de l'envoi du rapport à {email}. Veuillez vérifier la configuration de l'envoi d'emails.")
            else:
                st.warning("Veuillez entrer une adresse email valide.")

    else:
        st.warning("Veuillez d'abord uploader un fichier XML dans la page 'Upload XML'.")
     
elif st.session_state.selected_page == "Profil":
    if 'editing_profile' in st.session_state and st.session_state.editing_profile:
        show_edit_profile()
    else:
        show_profile_tab()
        
elif st.session_state.selected_page == "Personnalisation":
    if user.get('role') == 'admin':
      show_customization_tab()




st.markdown("""
    <style>
    div.stButton > button[kind="primary"][key="logout_button"] {
        background-color: red !important;
        color: white !important;
        border-radius: 8px;
        border: none;
        font-weight: bold;
    }
    div.stButton > button[kind="primary"][key="logout_button"]:hover {
        background-color: darkred !important;
        color: white !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.markdown("---")  
with st.sidebar:
        st.markdown("---")  
        if st.button(" Déconnexion", key="logout_button", use_container_width=True):
              logout()
              st.rerun()  
              st.markdown("---")      
# --- Contenu de la barre latérale ---
with st.sidebar:
   
    st.markdown("---")
    st.markdown(
        """
        <div style="text-align: center; color: #888; font-size: 12px; margin-top: 20px;font-weight:100">
            <p>Application de détection de fraude bancaire </p>
            <p> © 2025</p>
        </div>
        """,
        unsafe_allow_html=True
    )
# --- Footer ---
st.markdown("""
<div class="footer-container">
    <h4>Système de Détection de Fraude Bancaire</h4>
    <p>© 2025 Tous droits réservés.</p>
    <p>Conforme aux normes PACS.008 </p>
 
</div>

""", unsafe_allow_html=True)