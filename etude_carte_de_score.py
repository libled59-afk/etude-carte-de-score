import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
import os
import json
from streamlit_paste_button import paste_image_button
import io

# 1. Configuration de l'IA
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
model = genai.GenerativeModel('gemini-2.5-flash')

# 2. Configuration de la page
st.set_page_config(page_title="Analyse Golf Pro", layout="wide")

# 3. Zone de téléchargement
st.info("💡 **Astuce** : Prenez une capture d'écran avec `Windows + Maj + S` puis cliquez sur le bouton rouge ci-dessous (ou faites un clic droit > Coller l'image).")

# Initialisation de la variable image
img = None

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Option 1 : Coller la capture d'écran**")
    paste_result = paste_image_button(
        label="📋 Coller l'image",
        background_color="#FF4B4B",
        hover_background_color="#FF6B6B"
    )
    if paste_result.image_data is not None:
        img = paste_result.image_data

with col2:
    st.markdown("**Option 2 : Importer un fichier classique**")
    image_file = st.file_uploader(
        "Fichiers images", 
        type=["jpg", "jpeg", "png"],
        label_visibility="collapsed"
    )
    if image_file:
        img = Image.open(image_file)

if img is not None:
    st.image(img, caption="Carte chargée", width=400)

    if st.button("🚀 Lancer l'analyse"):
        with st.spinner("Analyse technique en cours..."):
            # Prompt structuré pour obtenir du JSON et un commentaire
            prompt = """
            Analyse cette carte de score de golf. 
            1. Extrais les données pour chaque trou au format JSON avec les clés : 
               'Date', 'Club', 'Trou', 'Par', 'Score', 'Putts', 'Fairway touché', 'GIR'.
            2. Après le JSON, ajoute le mot 'SEPARATION' puis un commentaire technique 
               factuel et neutre sur la précision, les GIR et les putts.
            """
            
            response = model.generate_content([prompt, img])
            
            try:
                # Séparation des données et du commentaire
                full_text = response.text
                data_part = full_text.split("SEPARATION")[0].strip()
                comment_part = full_text.split("SEPARATION")[1].strip()

                # Nettoyage du JSON (enlève les balises ```json si présentes)
                data_part = data_part.replace("```json", "").replace("```", "").strip()
                scores_list = json.loads(data_part)
                
                # Stockage dans la session Streamlit pour modification
                st.session_state['df_scores'] = pd.DataFrame(scores_list)
                st.session_state['commentary'] = comment_part
                
            except Exception as e:
                st.error("Erreur de lecture. Assurez-vous que la photo est bien lisible.")

    # 4. Affichage des résultats en onglets
    if 'df_scores' in st.session_state:
        df = st.session_state['df_scores']
        
        # --- NOUVEAU : Tableau de bord des métriques clés ---
        st.markdown("---")
        st.subheader("🏆 Résumé de la partie")
        
        try:
            # Copie et conversion pour les calculs (éviter les erreurs si les valeurs sont des strings)
            df_calc = df.copy()
            for col in ['Score', 'Par', 'Putts']:
                if col in df_calc.columns:
                    df_calc[col] = pd.to_numeric(df_calc[col], errors='coerce')
            
            df_aller = df_calc[df_calc['Trou'] <= 9]
            df_retour = df_calc[df_calc['Trou'] > 9]
            
            score_aller = df_aller['Score'].sum()
            score_retour = df_retour['Score'].sum()
            total_score = df_calc['Score'].sum()
            total_par = df_calc['Par'].sum()
            
            diff = total_score - total_par
            diff_str = f"+{int(diff)}" if diff > 0 else str(int(diff))
            
            # Ligne 1 : Scores
            col_s1, col_s2, col_s3, col_s4 = st.columns(4)
            with col_s1:
                st.metric("Score Aller (1-9)", int(score_aller))
            with col_s2:
                st.metric("Score Retour (10-18)", int(score_retour))
            with col_s3:
                st.metric("Score Total", int(total_score), diff_str)
            with col_s4:
                st.metric("Par total", int(total_par))
                
            st.markdown("---")
            
            # Ligne 2 : Autres Stats
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                total_putts = df_calc['Putts'].sum()
                st.metric("Total Putts", int(total_putts))
                
            with col_m2:
                if 'GIR' in df.columns:
                    gir_hits = df['GIR'].astype(str).str.strip().str.lower().isin(['oui', 'yes', 'vrai', 'true', '1'])
                    gir_hits_count = gir_hits.sum()
                    gir_total = len(df[df['GIR'].astype(str).str.strip().str.lower() != 'n/a'])
                    st.metric("GIR réussis", f"{gir_hits_count} / {gir_total}")
                    
            with col_m3:
                if 'GIR' in df_calc.columns and 'Score' in df_calc.columns and 'Par' in df_calc.columns:
                    is_missed_gir = df_calc['GIR'].astype(str).str.strip().str.lower().isin(['non', 'no', 'faux', 'false', '0', 'n'])
                    missed_gir_df = df_calc[is_missed_gir]
                    missed_gir_count = len(missed_gir_df)
                    
                    if missed_gir_count > 0:
                        saved_par_count = sum(missed_gir_df['Score'] <= missed_gir_df['Par'])
                        scrambling_pct = int((saved_par_count / missed_gir_count) * 100)
                        st.metric("Scrambling", f"{scrambling_pct}%", f"{saved_par_count}/{missed_gir_count} sauvés", delta_color="off")
                    else:
                        st.metric("Scrambling", "N/A", help="Pas de GIR manqué pour calculer le scrambling")
                    
        except Exception as e:
            st.warning("Calcul des métriques indisponible (vérifiez les données).")
        
        st.markdown("<br>", unsafe_allow_html=True)

        # Initialisation de l'état de sauvegarde si nécessaire
        if 'partie_sauvegardee' not in st.session_state:
            st.session_state.partie_sauvegardee = False
        
        # --- CONSEILS DU PRO ---
        st.subheader("🧠 Conseils du Pro")
        st.info(st.session_state.get('commentary', "Aucun commentaire généré."))
        
        st.markdown("<br>", unsafe_allow_html=True)

        # --- DONNÉES ET ÉDITION ---
        st.subheader("📊 Vérification des scores trou par trou")
        # Tableau interactif (pleine largeur, sans index)
        edited_df = st.data_editor(
            df, 
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True
        )
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Gestion dynamique du bouton de sauvegarde
        if st.session_state.partie_sauvegardee:
            # Bouton grisé et texte validé
            st.button("✅ Partie sauvegardée", disabled=True, use_container_width=True)
            st.success("Les données ont été enregistrées dans analyse_golf.csv !")
        else:
            if st.button("💾 Sauvegarder la partie", type="primary", use_container_width=True):
                file_path = "analyse_golf.csv"
                file_exists = os.path.isfile(file_path)
                
                edited_df.to_csv(file_path, mode='a', index=False, header=not file_exists)
                st.session_state.partie_sauvegardee = True
                st.rerun()