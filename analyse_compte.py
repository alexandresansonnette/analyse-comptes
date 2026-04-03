import os
import pandas as pd
import pdfplumber
import re
import streamlit as st

# Configuration de la page Streamlit
st.set_page_config(page_title="Analyse de Relevés Bancaires", layout="wide")
st.title("Analyse de Relevés Bancaires")

# Chemin absolu vers le dossier contenant les fichiers PDF
pdf_base_path = 'C:/Users/alsan/ProjetAnalyseComptes/PDFs'

# Liste des banques et caisses locales
banques_caisses = {
    "BNP Paribas": ["National"],
    "Crédit Agricole": [
        "Alsace Vosges", "Aquitaine", "Atlantique Vendée", "Brie Picardie", "Charente-Maritime Deux-Sèvres",
        "Charente-Périgord", "Champagne-Bourgogne", "Centre Est", "Centre France", "Centre Ouest",
        "Centre-est", "Corse", "Des Savoie", "Finistère", "Ille-et-Vilaine", "Loire Haute-Loire",
        "Morbihan", "Nord de France", "Nord Est", "Normandie", "Normandie-Seine", "Paris et Ile-de-France",
        "Provence Côte d'Azur", "Sud Rhône Alpes", "Tarn et Garonne", "Touraine et Poitou", "Val de France",
        "Pyrénées Gascogne"
    ],
    "Société Générale": ["National"],
    "LCL (Le Crédit Lyonnais)": ["National"],
    "La Banque Postale": ["National"],
    "HSBC France": ["National"],
    "CIC (Crédit Industriel et Commercial)": [
        "CIC Ouest", "CIC Sud-Ouest", "CIC Est", "CIC Nord-Ouest", "CIC Lyonnais", "CIC Paris"
    ],
    "Crédit Mutuel": [
        "Alliance Fédérale", "Anjou", "Antilles", "Arkéa", "Breton", "Centre Est Europe",
        "Ile-de-France", "Loire-Atlantique et Centre-Ouest", "Méditerranéen", "Nord Europe",
        "Océan", "Sud-Est"
    ],
    "Caisse d'Epargne": [
        "Alsace", "Aquitaine Poitou-Charentes", "Auvergne Limousin", "Bourgogne Franche-Comté",
        "Bretagne Pays de Loire", "Centre Val de Loire", "Côte d'Azur", "Grand Est Europe",
        "Hauts de France", "Ile-de-France", "Languedoc-Roussillon", "Lorraine Champagne-Ardenne",
        "Midi-Pyrénées", "Normandie", "Picardie", "Provence Alpes Corse", "Rhône Alpes"
    ],
    "Banque Populaire": [
        "Atlantique", "Bourgogne Franche-Comté", "Grand Ouest", "Hauts de France", "Méditerranée",
        "Nord", "Occitane", "Rives de Paris", "Sud", "Val de France", "Vendée et Bretagne Atlantique"
    ],
    "Arkéa (Crédit Mutuel Arkéa)": ["National"],
    "Fortuneo": ["National"],
    "Boursorama Banque": ["National"],
    "Hello Bank!": ["National"],
    "Monabanq": ["National"],
    "ING Direct": ["National"],
    "N26": ["National"],
    "Revolut": ["National"],
    "Orange Bank": ["National"],
    "BforBank": ["National"],
    "AXA Banque": ["National"],
    "C-Zam (Crédit Agricole)": ["National"],
    "Ma French Bank": ["National"],
    "Monzo": ["National"],
    "Pocket (par Orange Bank)": ["National"]
}

# Gestion des comptes bancaires
st.subheader("Gestion des Comptes Bancaires")

# Liste des comptes existants
comptes_bancaires_file = os.path.join(pdf_base_path, 'comptes_bancaires.txt')
if os.path.exists(comptes_bancaires_file):
    with open(comptes_bancaires_file, 'r') as f:
        comptes = [line.strip() for line in f.readlines()]
else:
    comptes = []

# Ajouter un nouveau compte bancaire
st.write("Ajouter un nouveau compte bancaire :")

# Option pour ajouter une nouvelle banque ou caisse
nouvelle_banque = st.text_input("Nom de la banque (si non listée)")
nouvelle_caisse = st.text_input("Nom de la caisse locale (si non listée)")

# Ou sélectionner une banque et une caisse existantes
col1, col2, col3 = st.columns(3)
with col1:
    banque = st.selectbox("Banque", [""] + list(banques_caisses.keys()), key="banque")
with col2:
    caisse = st.selectbox("Caisse locale", [""] + (banques_caisses[banque] if banque in banques_caisses else []), key="caisse")
with col3:
    precision = st.text_input("Précision (ex: Compte principal, Compte joint)", key="precision")

if st.button("Ajouter Compte"):
    if nouvelle_banque and nouvelle_caisse:
        compte = f"{nouvelle_banque} - {nouvelle_caisse}"
        if precision:
            compte += f" ({precision})"
    elif banque and caisse:
        compte = f"{banque} - {caisse}"
        if precision:
            compte += f" ({precision})"
    else:
        st.warning("Veuillez entrer une banque et une caisse valides.")
        st.stop()

    if compte not in comptes:
        comptes.append(compte)
        with open(comptes_bancaires_file, 'w') as f:
            f.write("\n".join(comptes))
        st.success(f"Compte {compte} ajouté avec succès !")
    else:
        st.warning(f"Le compte {compte} existe déjà.")

# Sélection des comptes à analyser
st.subheader("Sélection des Comptes à Analyser")
comptes_a_analyser = st.multiselect("Choisissez les comptes à analyser", comptes, default=comptes)

# Sélection des années à analyser
st.subheader("Sélection des Années à Analyser")
annees_disponibles = ["2025", "2026"]
annees_a_analyser = st.multiselect("Choisissez les années à analyser", annees_disponibles, default=["2026"])

# Sélection des mois à analyser
st.subheader("Sélection des Mois à Analyser")
mois_disponibles = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
mois_a_analyser = st.multiselect("Choisissez les mois à analyser", mois_disponibles, default=["janvier"])

# Vérification et chargement des fichiers pour chaque compte, année et mois
fichiers_charges = []

for compte in comptes_a_analyser:
    for annee in annees_a_analyser:
        for mois in mois_a_analyser:
            # Remplacer les espaces et caractères spéciaux pour le nom du fichier
            nom_fichier = compte.replace(" ", "_").replace("-", "").replace("(", "").replace(")", "")
            fichier_nom = f"{nom_fichier}_{mois}_{annee}.pdf"
            annee_mois_path = os.path.join(pdf_base_path, annee, mois)
            fichier_path = os.path.join(annee_mois_path, fichier_nom)

            # Créer le dossier de l'année et du mois s'il n'existe pas
            os.makedirs(annee_mois_path, exist_ok=True)

            if os.path.exists(fichier_path):
                st.write(f"Le fichier {fichier_nom} a été trouvé et sera utilisé.")
                fichiers_charges.append(fichier_path)
            else:
                st.write(f"Le fichier {fichier_nom} est manquant.")
                uploaded_file = st.file_uploader(f"Choisissez le fichier PDF pour {compte} - {mois} {annee}", type="pdf", key=f"uploader_{compte}_{mois}_{annee}")

                if uploaded_file is not None:
                    with open(fichier_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    st.success(f"Fichier {fichier_nom} chargé avec succès.")
                    fichiers_charges.append(fichier_path)

# Vérifier si tous les fichiers ont été chargés
if len(fichiers_charges) != len(comptes_a_analyser) * len(annees_a_analyser) * len(mois_a_analyser):
    st.error("Tous les fichiers nécessaires n'ont pas été chargés. Veuillez recharger les fichiers manquants.")
    st.stop()

# Fonction pour extraire les données des PDFs
def extraire_donnees_pdf(file_path):
    try:
        with pdfplumber.open(file_path) as pdf:
            data = []
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if len(row) >= 3:
                            date = row[0].strip() if row[0] else None
                            libelle = row[2].strip() if len(row) > 2 and row[2] else None

                            # Trouver les colonnes de débit et crédit
                            debit = None
                            credit = None
                            for i, cell in enumerate(row):
                                if cell and re.search(r'\d+\s?[.,]\d{2}\s?€?$', str(cell)):
                                    if debit is None:
                                        debit = cell.strip().replace(',', '.').replace(' ', '')
                                    elif credit is None:
                                        credit = cell.strip().replace(',', '.').replace(' ', '')

                            if debit is None:
                                debit = '0'
                            if credit is None:
                                credit = '0'

                            if date and libelle:
                                data.append({'Date': date, 'Libellé': libelle, 'Débit': float(debit), 'Crédit': float(credit)})
            return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Erreur lors de l'extraction des données du PDF : {e}")
        return pd.DataFrame()

# Extraire les données de tous les fichiers PDF chargés
dfs = []
for fichier_path in fichiers_charges:
    df = extraire_donnees_pdf(fichier_path)
    if not df.empty:
        dfs.append(df)

if not dfs:
    st.error("Aucune donnée extraite des fichiers PDF.")
    st.stop()

# Combiner les données de tous les fichiers
combined_df = pd.concat(dfs, ignore_index=True)

# Afficher les données
st.subheader("Données extraites")
st.dataframe(combined_df)

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

# Ajouter une nouvelle catégorie
st.subheader("Ajouter une Nouvelle Catégorie")
nouvelle_categorie = st.text_input("Nom de la nouvelle catégorie")
if st.button("Ajouter Catégorie"):
    if nouvelle_categorie and nouvelle_categorie not in categories:
        categories[nouvelle_categorie] = []
        st.success(f"Catégorie '{nouvelle_categorie}' ajoutée avec succès !")
    else:
        st.warning("Veuillez entrer un nom de catégorie valide ou la catégorie existe déjà.")

def categoriser_transactions(df, categories):
    df['Catégorie'] = 'À catégoriser'
    for categorie, mots_clés in categories.items():
        for mot in mots_clés:
            df.loc[df['Libellé'].str.contains(mot, case=False, na=False), 'Catégorie'] = categorie
    return df

combined_df = categoriser_transactions(combined_df, categories)

# Afficher les données catégorisées
st.subheader("Données catégorisées")
st.dataframe(combined_df)

# Visualisation des dépenses par catégorie
st.subheader("Visualisation des Dépenses par Catégorie")
rapport = combined_df.groupby('Catégorie').agg({'Débit': 'sum', 'Crédit': 'sum'}).fillna(0)
rapport['Solde'] = rapport['Crédit'] - rapport['Débit']
st.bar_chart(rapport['Débit'])

# Section pour les lignes non catégorisées
st.subheader("Lignes Non Catégorisées")
non_categorise_df = combined_df[combined_df['Catégorie'] == 'À catégoriser']
if not non_categorise_df.empty:
    st.dataframe(non_categorise_df)

    # Ajouter une interface pour catégoriser manuellement les lignes non catégorisées
    st.write("Catégoriser manuellement les lignes non catégorisées :")
    for index, row in non_categorise_df.iterrows():
        libelle = row['Libellé']
        new_category = st.selectbox(f"Catégoriser: {libelle}", [""] + list(categories.keys()), key=f"cat_{index}")
        if new_category:
            combined_df.at[index, 'Catégorie'] = new_category
            st.success(f"Libellé '{libelle}' catégorisé comme '{new_category}'.")

    # Modifier la catégorie d'un libellé
    st.subheader("Modifier la Catégorie d'un Libellé")
    libelle_a_modifier = st.selectbox("Sélectionnez un libellé", combined_df['Libellé'].unique(), key="libelle_modifier")
    nouvelle_categorie_libelle = st.selectbox("Nouvelle catégorie", list(categories.keys()), key="nouvelle_categorie_libelle")

    if st.button("Modifier Catégorie du Libellé"):
        combined_df.loc[combined_df['Libellé'] == libelle_a_modifier, 'Catégorie'] = nouvelle_categorie_libelle
        st.success(f"Libellé '{libelle_a_modifier}' mis à jour avec la catégorie '{nouvelle_categorie_libelle}'.")

    # Réafficher les données catégorisées après mise à jour
    st.subheader("Données catégorisées mises à jour")
    st.dataframe(combined_df)

    # Mettre à jour le rapport
    rapport = combined_df.groupby('Catégorie').agg({'Débit': 'sum', 'Crédit': 'sum'}).fillna(0)
    rapport['Solde'] = rapport['Crédit'] - rapport['Débit']
    st.subheader("Visualisation des Dépenses par Catégorie mise à jour")
    st.bar_chart(rapport['Débit'])
else:
    st.write("Toutes les lignes sont catégorisées.")

# Sauvegarder les données combinées et catégorisées
csv = combined_df.to_csv(index=False, sep=';').encode('utf-8')
st.download_button(
    label="Télécharger les données en CSV",
    data=csv,
    file_name='combined_transactions.csv',
    mime='text/csv',
)