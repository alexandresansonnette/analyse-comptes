import streamlit as st
import pandas as pd
import pdfplumber
import os

# Configuration de la page
st.set_page_config(page_title="Analyse de Relevés Bancaires", layout="wide")

# Titre de l'application
st.title("Analyse de Relevés Bancaires")

# Fonction pour extraire les données des PDFs
def extraire_donnees_pdf(uploaded_file):
    with pdfplumber.open(uploaded_file) as pdf:
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

# Fonction pour catégoriser les transactions
def categoriser_transactions(df, categories):
    df['Catégorie'] = 'À catégoriser'
    for categorie, mots_clés in categories.items():
        for mot in mots_clés:
            df.loc[df['Libellé'].str.contains(mot, case=False, na=False), 'Catégorie'] = categorie
    return df

# Demander à l'utilisateur de télécharger les fichiers PDF
uploaded_files = st.file_uploader(
    "Téléchargez vos relevés PDF",
    type=["pdf"],
    accept_multiple_files=True
)

# Catégories de transactions
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

if st.button("Analyser les relevés"):
    if uploaded_files:
        dfs = []
        for uploaded_file in uploaded_files:
            st.write(f"Analyse du fichier : {uploaded_file.name}")
            df = extraire_donnees_pdf(uploaded_file)
            dfs.append(df)

        if dfs:
            df_combined = pd.concat(dfs, ignore_index=True)
            df_combined = categoriser_transactions(df_combined, categories)

            # Afficher les données
            st.subheader("Données Extraits")
            st.dataframe(df_combined)

            # Visualisation des dépenses par catégorie
            st.subheader("Visualisation des Dépenses par Catégorie")
            rapport = df_combined.groupby('Catégorie').agg({'Débit': 'sum', 'Crédit': 'sum'}).fillna(0)
            rapport['Solde'] = rapport['Crédit'] - rapport['Débit']
            st.bar_chart(rapport['Débit'])

            # Sauvegarder les données combinées et catégorisées
            csv = df_combined.to_csv(index=False, sep=';').encode('utf-8')
            st.download_button(
                label="Télécharger les données en CSV",
                data=csv,
                file_name='combined_transactions.csv',
                mime='text/csv',
            )
    else:
        st.warning("Aucun fichier PDF n'a été sélectionné.")
