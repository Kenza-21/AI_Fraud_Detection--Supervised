# profile.py
import streamlit as st
from auth import logout, authenticate_user, register_user,verify_password
import hashlib
from db_operations import db_manager  # Assurez-vous que db_manager est correctement importé

# Modifiez la fonction init_profile_tables dans profile.py
def init_profile_tables():
    """Initialise les tables de profil utilisateur si nécessaire"""
    try:
        # Utiliser la nouvelle méthode update_databases du db_manager
        success = db_manager.update_databases()
        if not success:
            st.error("Erreur lors de la mise à jour de la structure de la base de données")
        return success
    except Exception as e:
        st.error(f"Erreur lors de l'initialisation des tables de profil: {e}")
        return False

def get_avatar_initials(full_name):
    """Génère des initiales à partir du nom complet"""
    if not full_name:
        return "US"
    
    names = full_name.split()
    if len(names) >= 2:
        return f"{names[0][0]}{names[-1][0]}".upper()
    elif len(names) == 1:
        return names[0][:2].upper()
    else:
        return "US"

def get_avatar_color(username):
    """Génère une couleur d'avatar cohérente basée sur le nom d'utilisateur"""
    color_hash = hashlib.md5(username.encode()).hexdigest()
    hue = int(color_hash[:8], 16) % 360
    return f"hsl({hue}, 70%, 50%)"

def update_user_profile(user_id, full_name, email, phone_number, department):
    """Met à jour le profil utilisateur dans la base de données"""
    try:
        with db_manager._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE users 
                    SET full_name = %s, email = %s, phone_number = %s, department = %s
                    WHERE id = %s
                """, (full_name, email, phone_number, department, user_id))
                conn.commit()
                return True, "Profil mis à jour avec succès"
    except Exception as e:
        return False, f"Erreur lors de la mise à jour du profil: {e}"
# profile.py - Correction de change_password

def change_password(user_id, current_password, new_password):
    """Change le mot de passe de l'utilisateur"""
    try:
        # Vérifier d'abord le mot de passe actuel
        with db_manager._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT password_hash FROM users WHERE id = %s
                """, (user_id,))
                result = cursor.fetchone()
                
                if not result:
                    return False, "Utilisateur non trouvé"
                
                stored_hash = result[0]
                # Vérifier le mot de passe actuel avec bcrypt
                from auth import verify_password
                if not verify_password(current_password, stored_hash):
                    return False, "Mot de passe actuel incorrect"
                
                # Hacher le nouveau mot de passe avec bcrypt
                from auth import hash_password
                new_hash = hash_password(new_password)
                
                # Mettre à jour le mot de passe
                cursor.execute("""
                    UPDATE users SET password_hash = %s WHERE id = %s
                """, (new_hash, user_id))
                conn.commit()
                return True, "Mot de passe changé avec succès"
                
    except Exception as e:
        return False, f"Erreur lors du changement de mot de passe: {e}"
def show_auth_card():
    """Affiche la carte d'authentification moderne"""
    st.markdown("""
    <style>
   
    .auth-header {
        text-align: center;
        margin-bottom: 2rem;
    }
    .auth-header h2 {
        color: white;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    .auth-tabs {
        display: flex;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        margin-bottom: 1.5rem;
        overflow: hidden;
    }
    .auth-tab {
        flex: 1;
        padding: 0.75rem;
        text-align: center;
        cursor: pointer;
        transition: all 0.3s ease;
        font-weight: 500;
    }
    .auth-tab.active {
        background: rgba(255, 255, 255, 0.2);
    }
   
    .auth-input {
        margin-bottom: 1rem;
    }
    .auth-button {
        background: #FF6B35;
        color: white;
        border: none;
        padding: 0.75rem;
        border-radius: 8px;
        width: 100%;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    .auth-button:hover {
        background: #E55A2B;
        transform: translateY(-2px);
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Conteneur principal de la carte d'authentification
    st.markdown('<div class="auth-card">', unsafe_allow_html=True)
    
    # En-tête
    st.markdown("""
    <div class="auth-header">
        <h2> Authentification</h2>
        <p>Accédez à votre espace sécurisé</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Gestion des onglets
    tab = st.selectbox("Choisir une action", ["Connexion", "Inscription"])
    
    # Formulaire
    st.markdown('<div class="auth-form">', unsafe_allow_html=True)
    
    if tab == "Connexion":
        username = st.text_input("Nom d'utilisateur", key="login_username")
        password = st.text_input("Mot de passe", type="password", key="login_password")
        
        if st.button("Se connecter", key="login_btn", use_container_width=True):
            if username and password:
                success, result = authenticate_user(username, password)
                if success:
                    st.session_state.user = result
                    st.session_state.logged_in = True
                    st.success(f"Bienvenue {result['full_name']}!")
                    st.rerun()
                else:
                    st.error(result)
            else:
                st.warning("Veuillez remplir tous les champs")
    
    else:  # Inscription
        full_name = st.text_input("Nom complet", key="register_name")
        email = st.text_input("Email", key="register_email")
        username = st.text_input("Nom d'utilisateur", key="register_username")
        password = st.text_input("Mot de passe", type="password", key="register_password")
        confirm_password = st.text_input("Confirmer le mot de passe", type="password", key="register_confirm")
        
        if st.button("Créer un compte", key="register_btn", use_container_width=True):
            if not all([full_name, email, username, password, confirm_password]):
                st.warning("Veuillez remplir tous les champs")
            elif password != confirm_password:
                st.error("Les mots de passe ne correspondent pas")
            else:
                success, result = register_user(username, email, password, full_name)
                if success:
                    st.success(result)
                    st.info("Vous pouvez maintenant vous connecter")
                else:
                    st.error(result)
    
    st.markdown('</div>', unsafe_allow_html=True)  # Fin du formulaire
    st.markdown('</div>', unsafe_allow_html=True)  # Fin de la carte

def show_user_profile_menu():
    """Affiche le menu profil utilisateur avec avatar"""
    st.markdown("""
    <style>
    .profile-menu {
        position: relative;
        display: inline-block;
    }
    .profile-avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s ease;
        border: 2px solid rgba(255, 255, 255, 0.2);
    }
    .profile-avatar:hover {
        transform: scale(1.05);
        border-color: rgba(255, 255, 255, 0.4);
    }
    .profile-dropdown {
        display: none;
        position: absolute;
        right: 0;
        top: 50px;
        background: white;
        min-width: 200px;
        border-radius: 8px;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
        z-index: 1000;
        overflow: hidden;
    }
    .profile-dropdown.show {
        display: block;
    }
    .profile-header {
        padding: 1rem;
        background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%);
        color: white;
    }
    .profile-item {
        padding: 0.75rem 1rem;
        cursor: pointer;
        transition: all 0.3s ease;
        border-bottom: 1px solid #f3f4f6;
    }
    .profile-item:hover {
        background: #f9fafb;
    }
    .profile-item:last-child {
        border-bottom: none;
        color: #ef4444;
    }
    .profile-item:last-child:hover {
        background: #fef2f2;
    }
    </style>
    """, unsafe_allow_html=True)
    
    user = st.session_state.user
    avatar_initials = get_avatar_initials(user['full_name'])
    avatar_color = get_avatar_color(user['username'])
    
    # Conteneur du menu profil
    st.markdown(f"""
    <div class="profile-menu">
        <div class="profile-avatar" style="background: {avatar_color};" onclick="toggleProfileMenu()">
            {avatar_initials}
        </div>
        <div class="profile-dropdown" id="profileDropdown">
            <div class="profile-header">
                <strong>{user['full_name']}</strong>
                <div style="font-size: 0.8rem; opacity: 0.8;">{user['role']}</div>
            </div>
            <div class="profile-item" onclick="showProfile()">Voir profil</div>
            <div class="profile-item" onclick="editProfile()"> Modifier informations</div>
            <div class="profile-item" onclick="logout()"> Déconnexion</div>
        </div>
    </div>
    
    <script>
    function toggleProfileMenu() {{
        var dropdown = document.getElementById('profileDropdown');
        dropdown.classList.toggle('show');
    }}
    
    function showProfile() {{
        // Ouvrir l'onglet profil
        window.parent.document.querySelector('[data-testid="stTabButton"]:nth-child(5)').click();
        toggleProfileMenu();
    }}
    
    function editProfile() {{
        // Ouvrir l'onglet profil avec édition
        window.parent.document.querySelector('[data-testid="stTabButton"]:nth-child(5)').click();
        // Activer le mode édition (à implémenter dans l'onglet profil)
        window.parent.document.dispatchEvent(new CustomEvent('editProfileMode'));
        toggleProfileMenu();
    }}
    
    function logout() {{
        // Déclencher la déconnexion
        window.parent.document.dispatchEvent(new CustomEvent('triggerLogout'));
    }}
    
    // Fermer le menu si on clique ailleurs
    window.addEventListener('click', function(e) {{
        var dropdown = document.getElementById('profileDropdown');
        var avatar = document.querySelector('.profile-avatar');
        if (dropdown.classList.contains('show') && !avatar.contains(e.target)) {{
            dropdown.classList.remove('show');
        }}
    }});
    </script>
    """, unsafe_allow_html=True)

def show_profile_tab():
    """Affiche l'onglet de profil utilisateur"""
    st.markdown("""
    <style>
    .profile-container {
        max-width: 600px;
        margin: 0 auto;
        padding: 2rem;
    }
    .profile-header {
        text-align: center;
        margin-bottom: 2rem;
    }
    .profile-avatar-large {
        width: 80px;
        height: 80px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: 600;
        font-size: 1.5rem;
        margin: 0 auto 1rem;
    }
    .profile-info {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
    }
    .info-item {
        display: flex;
        justify-content: space-between;
        padding: 0.75rem 0;
        border-bottom: 1px solid #f3f4f6;
    }
    .info-item:last-child {
        border-bottom: none;
    }
    .info-label {
        font-weight: 600;
        color: #6b7280;
    }
    </style>
    """, unsafe_allow_html=True)
    
    user = st.session_state.user
    avatar_initials = get_avatar_initials(user.get('full_name', ''))
    avatar_color = get_avatar_color(user.get('username', ''))
    
    st.markdown('<div class="profile-container">', unsafe_allow_html=True)
    
    # En-tête du profil
    st.markdown(f"""
    <div class="profile-header">
        <div class="profile-avatar-large" style="background: {avatar_color};">
            {avatar_initials}
        </div>
        <h2>{user.get('full_name', 'Utilisateur')}</h2>
        <p style="color: #6b7280;">{user.get('role', 'user')}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Informations du profil
    st.markdown('<div class="profile-info">', unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="info-item">
        <span class="info-label">Nom d'utilisateur:</span>
        <span>{user.get('username', 'Non renseigné')}</span>
    </div>
    <div class="info-item">
        <span class="info-label">Nom complet:</span>
        <span>{user.get('full_name', 'Non renseigné')}</span>
    </div>
    <div class="info-item">
        <span class="info-label">Email:</span>
        <span>{user.get('email', 'Non renseigné')}</span>
    </div>
    <div class="info-item">
        <span class="info-label">Téléphone:</span>
        <span>{user.get('phone_number', 'Non renseigné')}</span>
    </div>
    <div class="info-item">
        <span class="info-label">Département:</span>
        <span>{user.get('department', 'Non renseigné')}</span>
    </div>
    <div class="info-item">
        <span class="info-label">Rôle:</span>
        <span>{user.get('role', 'Non renseigné')}</span>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)  # Fin des infos profil
    
    # Bouton d'édition
    if st.button(" Modifier le profil", use_container_width=True):
        st.session_state.editing_profile = True
    
    # Bouton de déconnexion
   
    
    st.markdown('</div>', unsafe_allow_html=True)  # Fin du conteneur
# profile.py - Modification de la fonction show_edit_profile()
def show_edit_profile():
    """Affiche le formulaire d'édition du profil"""
    user = st.session_state.user
    
    # Ajout d'un bouton "Revenir au profil" en haut du formulaire
    if st.button("◀ Revenir au profil", key="back_to_profile_btn"):
        st.session_state.editing_profile = False
        st.rerun()
    
    with st.form("edit_profile_form"):
        full_name = st.text_input("Nom complet", value=user.get('full_name', ''), key="edit_full_name")
        email = st.text_input("Email", value=user.get('email', ''), key="edit_email")
        phone_number = st.text_input("Téléphone", value=user.get('phone_number', ''), key="edit_phone")
        department = st.text_input("Département", value=user.get('department', ''), key="edit_department")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button(" Enregistrer", use_container_width=True):
                # Mise à jour du profil
                success, message = update_user_profile(
                    user['id'], full_name, email, phone_number, department
                )
                if success:
                    st.success(message)
                    # Mettre à jour les informations dans la session
                    st.session_state.user.update({
                        'full_name': full_name,
                        'email': email,
                        'phone_number': phone_number,
                        'department': department
                    })
                    st.session_state.editing_profile = False
                    st.rerun()
                else:
                    st.error(message)
        with col2:
            if st.form_submit_button(" Annuler", use_container_width=True):
                st.session_state.editing_profile = False
                st.rerun()
    
    # Section changement de mot de passe
    st.markdown("---")
    st.subheader("Changer le mot de passe")
    
    with st.form("change_password_form"):
        current_password = st.text_input("Mot de passe actuel", type="password", key="current_password")
        new_password = st.text_input("Nouveau mot de passe", type="password", key="new_password")
        confirm_password = st.text_input("Confirmer le nouveau mot de passe", type="password", key="confirm_password")
        
        if st.form_submit_button("🔒  Changer le mot de passe", use_container_width=True):
            if not current_password or not new_password or not confirm_password:
                st.error("Veuillez remplir tous les champs")
            elif new_password != confirm_password:
                st.error("Les mots de passe ne correspondent pas")
            else:
                success, message = change_password(user['id'], current_password, new_password)
                if success:
                    st.success(message)
                    # RETOUR AUTOMATIQUE AU PROFIL APRÈS CHANGEMENT DE MOT DE PASSE
                    st.session_state.editing_profile = False
                    st.rerun()
                else:
                    st.error(message)


def logout():
    """Déconnecte l'utilisateur et réinitialise complètement la session"""
    # Efface toute la session state SAUF les clés nécessaires pour la redirection
    keys_to_keep = ['_streamlit', 'FormSubmitter:logout_button', 'file_uploader']
    
    for key in list(st.session_state.keys()):
        if key not in keys_to_keep:
            del st.session_state[key]
    
    # Réinitialise l'état d'authentification
    st.session_state.authenticated = False
    
    # Force le rerun pour afficher la page de login
    st.rerun()