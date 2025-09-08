import streamlit as st
import pandas as pd
from db_operations import db_manager
from auth import authenticate_user, hash_password
import plotly.express as px
from datetime import timedelta ,datetime
import secrets  # Ajout pour générer des tokens sécurisés

class AdminDashboard:
    def __init__(self):
        self.conn = db_manager._get_connection()
    
    def get_all_users(self):
        """Récupère tous les utilisateurs de la base de données"""
        try:
            query = """
            SELECT id, username, email, full_name, role, phone_number, 
                   department, created_at, is_active
            FROM users
            ORDER BY created_at DESC
            """
            df = pd.read_sql_query(query, self.conn)
            return df
        except Exception as e:
            st.error(f"Erreur lors de la récupération des utilisateurs: {e}")
            return pd.DataFrame()
    
    def get_connected_users(self):
        """Récupère les informations sur les utilisateurs actuellement connectés"""
        try:
            # Cette requête suppose que vous avez une table de sessions ou un moyen de tracker les connexions
            query = """
            SELECT u.id, u.username, u.full_name, u.role, 
                   MAX(us.created_at) as last_activity
            FROM users u
            LEFT JOIN user_sessions us ON u.id = us.user_id
            WHERE u.is_active = TRUE
            GROUP BY u.id, u.username, u.full_name, u.role
            ORDER BY last_activity DESC NULLS LAST
            """
            df = pd.read_sql_query(query, self.conn)
            return df
        except Exception as e:
            st.error(f"Erreur lors de la récupération des utilisateurs connectés: {e}")
            return pd.DataFrame()
    
    def delete_user(self, user_id):
        """Supprime un utilisateur de la base de données"""
        try:
            # Vérifier d'abord si l'utilisateur existe
            with self.conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
                if cursor.fetchone() is None:
                    return False, "Utilisateur non trouvé"
                
                # Supprimer l'utilisateur
                cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            self.conn.commit()
            return True, "Utilisateur supprimé avec succès"
        except Exception as e:
            return False, f"Erreur lors de la suppression: {e}"
    
    def update_user_role(self, user_id, new_role):
        """Met à jour le rôle d'un utilisateur"""
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE users SET role = %s WHERE id = %s",
                    (new_role, user_id)
                )
            self.conn.commit()
            return True, "Rôle mis à jour avec succès"
        except Exception as e:
            return False, f"Erreur lors de la mise à jour du rôle: {e}"
    
    def create_user(self, username, email, password, full_name, role, phone_number=None, department=None):
        """Crée un nouvel utilisateur (fonctionnalité admin)"""
        from auth import validate_email
        
        if not validate_email(email):
            return False, "Format d'email invalide"
        
        if len(password) < 6:
            return False, "Le mot de passe doit contenir au moins 6 caractères"
        
        password_hash = hash_password(password)
        
        try:
            with self.conn.cursor() as cursor:
                # Insérer l'utilisateur
                cursor.execute(
                    """INSERT INTO users 
                    (username, email, password_hash, full_name, role, phone_number, department) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                    (username, email, password_hash, full_name, role, phone_number, department)
                )
                
                # Récupérer l'ID du nouvel utilisateur
                user_id = cursor.fetchone()[0]
                
                # Générer un token de session sécurisé
                session_token = secrets.token_urlsafe(32)
                
                # Créer une session pour le nouvel utilisateur avec un token valide
                cursor.execute(
                    """INSERT INTO user_sessions (user_id, session_token, created_at, expires_at) 
                    VALUES (%s, %s, %s, %s)""",
                    (user_id, session_token, datetime.now(), datetime.now() + timedelta(days=30))
                )
                
            self.conn.commit()
            return True, "Utilisateur créé avec succès"
        except Exception as e:
            return False, f"Erreur lors de la création: {e}"

def show_admin_dashboard():
    """Affiche le tableau de bord administrateur"""
    
    
    
    admin_db = AdminDashboard()
    
    st.title("Tableau de Bord Administrateur")
    
    # Créer des onglets pour différentes fonctionnalités admin
    tab1, tab2, tab3= st.tabs([
        " Utilisateurs Connectés", 
        " Gestion des Utilisateurs", 
        " Créer un Utilisateur",
       
    ])
    
    with tab1:
        st.header("Listes des Utilisateurs ")
        connected_users = admin_db.get_connected_users()
        
        if not connected_users.empty:
            st.dataframe(
                connected_users,
                use_container_width=True,
                column_config={
                    "id": "ID",
                    "username": "Nom d'utilisateur",
                    "full_name": "Nom complet",
                    "role": "Rôle",
                    "last_activity": "Dernière activité"
                }
            )
        else:
            st.info("Aucun utilisateur connecté ou impossible de récupérer les données.")
    
    with tab2:
        st.header("Gestion des Utilisateurs")
        all_users = admin_db.get_all_users()
        
        if not all_users.empty:
            # Section de suppression d'utilisateur simplifiée
            st.subheader("Supprimer un utilisateur")
            
            # Créer une liste d'options pour la sélection
            user_options = [f"{row['id']} - {row['username']} ({row['email']})" 
                           for _, row in all_users.iterrows()]
            
            # Ajouter une option vide par défaut
            user_options.insert(0, "Sélectionner un utilisateur...")
            
            selected_user = st.selectbox(
                "Choisir l'utilisateur à supprimer",
                options=user_options,
                key="user_to_delete"
            )
            
            # Afficher les détails de l'utilisateur sélectionné
            if selected_user and selected_user != "Sélectionner un utilisateur...":
                user_id = int(selected_user.split(" - ")[0])
                user_data = all_users[all_users['id'] == user_id].iloc[0]
                
                st.write("**Détails de l'utilisateur sélectionné:**")
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Nom d'utilisateur:** {user_data['username']}")
                    st.write(f"**Email:** {user_data['email']}")
                    st.write(f"**Nom complet:** {user_data['full_name']}")
                with col2:
                    st.write(f"**Rôle:** {user_data['role']}")
                    st.write(f"**Département:** {user_data['department']}")
                    st.write(f"**Date de création:** {user_data['created_at'].strftime('%Y-%m-%d')}")
                
                # Bouton de suppression avec confirmation
            if st.button("Supprimer cet utilisateur", type="secondary"):
               success, message = admin_db.delete_user(user_id)
               if success:
                   st.success(message)
                   st.rerun()
               else:
                   st.error(message)
                   st.rerun()
        

    with tab3:
        st.header("Créer un Nouvel Utilisateur")
        
        with st.form("create_user_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                new_username = st.text_input("Nom d'utilisateur *")
                new_email = st.text_input("Email *")
                new_password = st.text_input("Mot de passe *", type="password")
                confirm_password = st.text_input("Confirmer le mot de passe *", type="password")
            
            with col2:
                new_full_name = st.text_input("Nom complet *")
                new_role = st.selectbox("Rôle *", options=["user", "admin"])
                new_phone = st.text_input("Téléphone")
                new_department = st.text_input("Département")
            
            submitted = st.form_submit_button("Créer l'utilisateur")
            
            if submitted:
                if not all([new_username, new_email, new_password, new_full_name, new_role]):
                    st.error("Veuillez remplir tous les champs obligatoires (*)")
                elif new_password != confirm_password:
                    st.error("Les mots de passe ne correspondent pas")
                else:
                    success, message = admin_db.create_user(
                        new_username, new_email, new_password, new_full_name, 
                        new_role, new_phone, new_department
                    )
                    if success:
                        st.success(message)
                        # Rafraîchir les données affichées
                        st.rerun()
                    else:
                        st.error(message)
    
    