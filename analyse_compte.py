from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
import pandas as pd
import pdfplumber
import streamlit as st
import os

# Configuration de la page Streamlit
st.set_page_config(page_title="Analyse de Relevés Bancaires", layout="wide")
st.title("Analyse de Relevés Bancaires")

# Chemin vers les identifiants Google Drive
credentials_path = r'C:\Users\alsan\json\credentials.json'  # Remplacez par le chemin exact de votre fichier JSON

# Vérifiez si le fichier de credentials existe
if not os.path.exists(credentials_path):
    st.error(f"Le fichier de credentials est introuvable à l'emplacement : {credentials_path}")
else:
    try:
        # Authentification
        creds = service_account.Credentials.from_service_account_file(credentials_path)
        service = build('drive', 'v3', credentials=creds)

        # ID du dossier parent dans Google Drive
        parent_folder_id = '12WZpjneNv0Q_FQZfA3KVUtTWkUHzU8k6'  # Remplacez par l'ID de votre dossier

        # Fonction pour lister les fichiers dans un dossier Google Drive
        def list_files_in_folder(folder_id):
            results = service.files().list(
                q=f"'{folder_id}' in parents",
                fields="files(id, name)"
            ).execute()
            return results.get('files', [])

        # Lister les fichiers dans le dossier
        files = list_files_in_folder(parent_folder_id)

        if not files:
            st.write('Aucun fichier trouvé.')
        else:
            st.write('Fichiers disponibles :')
            for file in files:
                st.write(f"{file['name']} (ID: {file['id']})")

            # Demander à l'utilisateur de sélectionner un fichier
            file_names = [file['name'] for file in files]
            selected_file_name = st.selectbox("Sélectionnez un fichier PDF à analyser", file_names)

            # Trouver l'ID du fichier sélectionné
            selected_file_id = next(file['id'] for file in files if file['name'] == selected_file_name)

            # Fonction pour télécharger un fichier depuis Google Drive
            def download_file(file_id):
                request = service.files().get_media(fileId=file_id)
                file = io.BytesIO()
                downloader = io.BytesIO()
                downloader = request.execute_media_io_base_downloader(downloader)
                downloader.seek(0)
                return downloader

            # Télécharger le fichier sélectionné
            file_content = download_file(selected_file_id)

            # Fonction pour extraire les données des PDFs
            def extraire_donnees_pdf(file_content):
                with pdfplumber.open(file_content) as pdf:
                    data = []
                    for page in pdf.pages:
                        tables = page.extract_tables()
                        for table in tables:
                            for row in table:
                                if len(row) >= 5:
                                    date = row[0].strip() if row[0] else None
                                    libelle = row[2].strip() if len(row) > 2 and row[2] else None
                                    debit = row[3].strip().replace(',', '.') if len(row) > 3 and row[3] else '0'
                                    credit = row[4].strip().replace(',', '.') if len(row) > 4 and row[4] else '0'
                                    if date and libelle:
                                        data.append({'Date': date, 'Libellé': libelle, 'Débit': float(debit), 'Crédit': float(credit)})
                    return pd.DataFrame(data)

            # Extraire les données du fichier PDF
            df = extraire_donnees_pdf(file_content)

            # Afficher les données
            st.subheader("Données extraites")
            st.dataframe(df)

            # Catégoriser les transactions
            categories = {
                'Revenu': ['VIR DE', 'VIR MSA', 'SALAIRE'],
                'Nourriture': ['SUPER U', 'CARREFOUR', 'LE MARCHE DES FR'],
                'Abonnement': ['PRLV SEPA SFR'],
                'Prêt/ass': ['PRLV SEPA GROUPAMA', 'PRLV SEPA BNP PARIBAS'],
                'Sénégal': ['SENDWAVE', 'WESTERN UNION'],
                'CLAE école': ['MSA MIDI PYRENEES'],
                'Loisirs/vac./kdo': ['FDJ', 'AMAZON', 'ALIEXPRESS'],
                'Voiture': ['V2G', 'SA TOHA LAVAGE'],
                'Virement interne': ['VIR INST', 'VIR VERS'],
            }

            def categoriser_transactions(df, categories):
                df['Catégorie'] = 'À catégoriser'
                for categorie, mots_clés in categories.items():
                    for mot in mots_clés:
                        df.loc[df['Libellé'].str.contains(mot, case=False, na=False), 'Catégorie'] = categorie
                return df

            df = categoriser_transactions(df, categories)

            # Afficher les données catégorisées
            st.subheader("Données catégorisées")
            st.dataframe(df)

            # Visualisation des dépenses par catégorie
            st.subheader("Visualisation des Dépenses par Catégorie")
            rapport = df.groupby('Catégorie').agg({'Débit': 'sum', 'Crédit': 'sum'}).fillna(0)
            rapport['Solde'] = rapport['Crédit'] - rapport['Débit']
            st.bar_chart(rapport['Débit'])

            # Sauvegarder les données combinées et catégorisées
            csv = df.to_csv(index=False, sep=';').encode('utf-8')
            st.download_button(
                label="Télécharger les données en CSV",
                data=csv,
                file_name='combined_transactions.csv',
                mime='text/csv',
            )

    except Exception as e:
        st.error(f"Une erreur s'est produite : {e}")
