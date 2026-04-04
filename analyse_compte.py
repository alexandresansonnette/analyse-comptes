import os
import json
import re
import pandas as pd
import pdfplumber
import plotly.express as px
import streamlit as st

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG PAGE
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Analyse de Relevés Bancaires", layout="wide")

# Chemin par défaut : remonte d'un niveau depuis App/ pour pointer vers
# ProjetAnalyseComptes/PDFs — hors du dossier versionné par Git.
_DEFAULT_PDF_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "PDFs",
)

PDF_BASE_PATH = st.sidebar.text_input(
    "📂 Dossier PDF",
    value=os.environ.get("PDF_BASE_PATH", _DEFAULT_PDF_PATH),
    help="Chemin vers le dossier PDFs (par défaut : un niveau au-dessus de App/)",
)

# ══════════════════════════════════════════════════════════════════════════════
# DONNÉES DE RÉFÉRENCE
# ══════════════════════════════════════════════════════════════════════════════
BANQUES_INITIALES = {
    "BNP Paribas": ["National"],
    "Crédit Agricole": [
        "Alsace Vosges", "Aquitaine", "Atlantique Vendée", "Brie Picardie",
        "Charente-Maritime Deux-Sèvres", "Charente-Périgord", "Champagne-Bourgogne",
        "Centre Est", "Centre France", "Centre Ouest", "Corse", "Des Savoie",
        "Finistère", "Ille-et-Vilaine", "Loire Haute-Loire", "Morbihan",
        "Nord de France", "Nord Est", "Normandie", "Normandie-Seine",
        "Paris et Ile-de-France", "Provence Côte d'Azur", "Sud Rhône Alpes",
        "Tarn et Garonne", "Touraine et Poitou", "Val de France", "Pyrénées Gascogne",
    ],
    "Société Générale": ["National"],
    "LCL": ["National"],
    "La Banque Postale": ["National"],
    "CIC": ["CIC Ouest", "CIC Sud-Ouest", "CIC Est", "CIC Nord-Ouest", "CIC Lyonnais", "CIC Paris"],
    "Crédit Mutuel": [
        "Alliance Fédérale", "Anjou", "Antilles", "Arkéa", "Breton",
        "Centre Est Europe", "Ile-de-France", "Loire-Atlantique et Centre-Ouest",
        "Méditerranéen", "Nord Europe", "Océan", "Sud-Est",
    ],
    "Caisse d'Epargne": [
        "Alsace", "Aquitaine Poitou-Charentes", "Auvergne Limousin",
        "Bourgogne Franche-Comté", "Bretagne Pays de Loire", "Centre Val de Loire",
        "Côte d'Azur", "Grand Est Europe", "Hauts de France", "Ile-de-France",
        "Languedoc-Roussillon", "Lorraine Champagne-Ardenne", "Midi-Pyrénées",
        "Normandie", "Picardie", "Provence Alpes Corse", "Rhône Alpes",
    ],
    "Banque Populaire": [
        "Atlantique", "Bourgogne Franche-Comté", "Grand Ouest", "Hauts de France",
        "Méditerranée", "Nord", "Occitane", "Rives de Paris", "Sud",
        "Val de France", "Vendée et Bretagne Atlantique",
    ],
    "Boursorama Banque": ["National"],
    "Hello Bank!": ["National"],
    "ING Direct": ["National"],
    "N26": ["National"],
    "Revolut": ["National"],
    "Fortuneo": ["National"],
    "BforBank": ["National"],
    "Monabanq": ["National"],
    "Orange Bank": ["National"],
    "Ma French Bank": ["National"],
}

# Catégories par défaut — vides, les mots-clés sont ajoutés au fur et à mesure
CATEGORIES_DEFAUT = {
    "Abonnements":      [],
    "École / CLAE":     [],
    "Loisirs":          [],
    "Nourriture":       [],
    "Prêt / Assurance": [],
    "Revenu":           [],
    "Virement interne": [],
    "Voiture":          [],
}

MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]

# Palette couleur partagée entre les deux graphiques (daltonisme-friendly)
PALETTE = px.colors.qualitative.Safe


# ══════════════════════════════════════════════════════════════════════════════
# PERSISTANCE
# ══════════════════════════════════════════════════════════════════════════════
def _chemin_comptes() -> str:
    return os.path.join(PDF_BASE_PATH, "comptes_bancaires.json")

def _chemin_comptes_legacy() -> str:
    return os.path.join(PDF_BASE_PATH, "comptes_bancaires.txt")

def _chemin_categories() -> str:
    return os.path.join(PDF_BASE_PATH, "categories.json")

def charger_comptes() -> list:
    """Charge les comptes depuis JSON.
    Rétrocompatibilité : si seul le .txt existe, on le migre automatiquement.
    Chaque compte est un dict :
      { "intitule": "Mon compte principal",
        "banque": "Crédit Agricole",
        "caisse": "Midi-Pyrénées" }
    """
    p_json   = _chemin_comptes()
    p_legacy = _chemin_comptes_legacy()

    if os.path.exists(p_json):
        with open(p_json, "r", encoding="utf-8") as f:
            return json.load(f)

    # Migration depuis l'ancien format .txt
    if os.path.exists(p_legacy):
        comptes = []
        with open(p_legacy, "r", encoding="utf-8") as f:
            for ligne in f:
                ligne = ligne.strip()
                if not ligne:
                    continue
                # Format legacy : "Banque - Caisse (Précision)"
                intitule = ligne  # on garde la string entière comme intitulé
                parties  = ligne.split(" - ", 1)
                banque   = parties[0].strip() if len(parties) > 1 else ligne
                reste    = parties[1] if len(parties) > 1 else ""
                # Extraire précision entre parenthèses si présente
                m = re.match(r"^(.*?)\s*\((.+)\)$", reste)
                if m:
                    caisse   = m.group(1).strip()
                    intitule = m.group(2).strip()
                else:
                    caisse   = reste.strip() or "National"
                comptes.append({"intitule": intitule, "banque": banque, "caisse": caisse})
        sauvegarder_comptes_data(comptes)
        return comptes

    return []

def sauvegarder_comptes_data(comptes: list):
    """Sauvegarde la liste de dicts comptes en JSON."""
    os.makedirs(PDF_BASE_PATH, exist_ok=True)
    with open(_chemin_comptes(), "w", encoding="utf-8") as f:
        json.dump(comptes, f, ensure_ascii=False, indent=2)

def sauvegarder_comptes():
    sauvegarder_comptes_data(st.session_state["comptes"])

def label_compte(c: dict) -> str:
    """Retourne l'étiquette affichée pour un compte."""
    return f"{c['intitule']}  —  {c['banque']} / {c['caisse']}"

def charger_categories() -> dict:
    """Charge depuis JSON ; complète avec les défauts ; retourne trié A→Z."""
    p = _chemin_categories()
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            cats = json.load(f)
        for k, v in CATEGORIES_DEFAUT.items():
            if k not in cats:
                cats[k] = v
    else:
        cats = dict(CATEGORIES_DEFAUT)
    return dict(sorted(cats.items(), key=lambda x: x[0].lower()))

def sauvegarder_categories():
    """Trie A→Z puis écrit le JSON."""
    os.makedirs(PDF_BASE_PATH, exist_ok=True)
    cats_triees = dict(sorted(
        st.session_state["categories"].items(),
        key=lambda x: x[0].lower(),
    ))
    st.session_state["categories"] = cats_triees
    with open(_chemin_categories(), "w", encoding="utf-8") as f:
        json.dump(cats_triees, f, ensure_ascii=False, indent=2)


def _chemin_cheques() -> str:
    return os.path.join(PDF_BASE_PATH, "cheques.json")

def charger_cheques() -> dict:
    """Charge le registre des chèques déjà catégorisés.

    Clé = "DATE|LIBELLE_COMPLET" pour éviter toute confusion si deux chèques
    ont le même numéro (rare mais possible sur des comptes différents ou des
    périodes différentes).

    Format :
    {
      "30.01|Chèque 1596519": {"categorie": "Nourriture", "montant": 28.0},
      "30.01|Chèque 1596520": {"categorie": "Voiture",    "montant": 42.0}
    }
    """
    p = _chemin_cheques()
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def _cle_cheque(date: str, libelle: str) -> str:
    """Clé unique d'identification d'un chèque : date + libellé complet."""
    return f"{date.strip()}|{libelle.strip()}"

def sauvegarder_cheques():
    os.makedirs(PDF_BASE_PATH, exist_ok=True)
    with open(_chemin_cheques(), "w", encoding="utf-8") as f:
        json.dump(st.session_state["cheques_connus"], f, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
def init_state():
    if "comptes"          not in st.session_state:
        comptes_charges = charger_comptes()
        st.session_state["comptes"] = sorted(
            comptes_charges, key=lambda c: c["intitule"].lower() if isinstance(c, dict) else c.lower()
        )
    if "banques"          not in st.session_state:
        # Trier banques A→Z, et caisses A→Z dans chaque banque
        st.session_state["banques"] = {
            k: sorted(v, key=str.lower)
            for k, v in sorted(BANQUES_INITIALES.items(), key=lambda x: x[0].lower())
        }
    if "categories"       not in st.session_state:
        st.session_state["categories"]       = charger_categories()
    if "fichiers_charges" not in st.session_state:
        st.session_state["fichiers_charges"] = []
    if "combined_df"      not in st.session_state:
        st.session_state["combined_df"]      = None
    if "cheques_connus"   not in st.session_state:
        st.session_state["cheques_connus"]   = charger_cheques()

init_state()


# ══════════════════════════════════════════════════════════════════════════════
# FILTRES D'EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════

# Mots qui peuvent apparaître dans la ligne d'en-tête d'un tableau de transactions
_ENTETES = {
    "libellé", "libelle", "opération", "operation", "désignation",
    "désignation de l'opération", "detail", "détail", "description",
    "nature", "intitulé", "intitule",
}

# Mots qui signalent une colonne "date" dans l'en-tête d'un tableau
_ENTETES_DATE = {
    "date", "date opération", "date operation", "date valeur",
    "date de valeur", "jour",
}

# Mots qui signalent une colonne "montant/débit/crédit" dans l'en-tête
_ENTETES_MONTANT = {
    "débit", "debit", "crédit", "credit", "montant", "somme",
    "débit €", "crédit €", "débit eur", "crédit eur",
    "débit euros", "crédit euros",        # Monabanq
    "mouvements débiteurs", "mouvements créditeurs",
}

_RE_PRLV_CARTE = re.compile(
    r"(factur\w*\s+carte|prlv\s+carte|remise\s+carte|total\s+carte"
    r"|r[eè]glement\s+carte|pr[eé]l[eè]vement\s+carte"
    r"|vos\s+paiements\s+carte|arr[eê]t[eé]\s+carte"
    r"|d[eé]penses\s+carte)",   # CA : "Prlv Dépenses Carte X1181 Au 23/01/26"
    re.IGNORECASE,
)
_RE_DATE    = re.compile(r"\d{2}")
_RE_MONTANT = re.compile(r"[\d\s]+[.,]\d{2}\s*€?\s*$")  # espace milliers ok

# Libellés parasites récurrents dans les PDFs bancaires (frais, découverts,
# récapitulatifs, totaux…) — ces lignes ne sont pas des transactions.
_RE_LIGNE_PARASITE = re.compile(
    r"""(
        \btotal\b                              # TOTAL DES FRAIS, TOTAL MENSUEL…
      | \bfrais\b                              # frais débités
      | \bautorisation\b                       # AUTORISATION DE DECOUVERT
      | \bd[eé]couvert\b                       # découvert
      | \bfacilit[eé]\b                        # facilité de caisse
      | \btaeg\b                               # TAEG (taux annuel effectif global)
      | \bp[eé]riode\b                         # Période : 4 Trim 25 TAEG…
      | \bn[°º]\s*de\s*compte\b               # N° de compte
      | \bproduits\s+et\s+services\b           # produits et services bancaires
      | \br[eé]capitulatif\b                   # récapitulatif
      | \bsolde\s+(au|du|de|initial|final)\b   # solde au …
      | \breport[eé]?\b                        # report
      | \bancien\s+solde\b
      | \bnouveau\s+solde\b
      | \bmontant\s+pr[eé]lev[eé]\b           # Montant prélevé au 30.01…
      | ^ref\s+vir\b                           # Ref vir : (ligne de référence virement)
      | ^[A-Z]{2}\d{2}[A-Z0-9]{10,}           # Référence bancaire pure type SEPA/IBAN
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# Une vraie date de transaction : JJ/MM, JJ.MM, JJ-MM et variantes avec année
# Un numéro de compte seul (ex : 53000052338) ne doit pas passer pour une date.
_RE_VRAIE_DATE = re.compile(
    r"""(
        \d{1,2}[/\.\-]\d{1,2}([/\.\-]\d{2,4})?   # 15/03, 15.03, 15-03, 15/03/2026, 15.01.26
      | \d{1,2}\s+                                     # 15 janvier …
        (jan|f[eé]v|mar|avr|mai|juin|juil
        |ao[uû]|sep|oct|nov|d[eé]c)
    )""",
    re.IGNORECASE | re.VERBOSE,
)


def _tableau_est_un_releve(table: list) -> bool:
    """Vérifie que le tableau contient bien les colonnes attendues d'un relevé
    bancaire : au moins une colonne date, une colonne libellé/opération, et au
    moins une colonne montant (débit ou crédit).

    Stratégie :
    - On cherche dans la première ligne non vide (l'en-tête) des cellules
      correspondant aux trois types de colonnes.
    - Si l'en-tête est absent ou illisible, on bascule sur une heuristique :
      au moins 30 % des lignes doivent contenir un montant valide ET une date.
    """
    if not table or len(table) < 2:
        return False

    # Un tableau de transactions a au minimum 4 colonnes (date, libellé, débit, crédit)
    # Les tableaux parasites (découverts, frais) n'en ont que 3
    nb_cols = max(len(r) for r in table if r)
    if nb_cols < 4:
        return False

    # ── Recherche de l'en-tête ───────────────────────────────────────────────
    header = None
    for row in table[:3]:          # l'en-tête est en général dans les 3 premières lignes
        cells = [str(c or "").lower().strip() for c in row]
        if any(c in _ENTETES_DATE for c in cells):
            header = cells
            break

    if header is not None:
        a_date    = any(c in _ENTETES_DATE    for c in header)
        a_libelle = any(c in _ENTETES         for c in header)
        a_montant = any(c in _ENTETES_MONTANT for c in header)
        # On exige date + montant ; libellé est souvent nommé autrement
        return a_date and a_montant

    # ── Heuristique si pas d'en-tête lisible ─────────────────────────────────
    # Un relevé de transactions : la grande majorité des lignes ont
    # une date (2 chiffres au moins en col 0) ET au moins un montant sur la ligne.
    lignes_data = [r for r in table if r and len(r) >= 3]
    if not lignes_data:
        return False

    score = 0
    for row in lignes_data:
        col0 = str(row[0] or "").strip()
        a_date_ligne    = bool(_RE_DATE.search(col0)) and len(col0) <= 20
        a_montant_ligne = any(bool(_RE_MONTANT.search(str(c or ""))) for c in row)
        if a_date_ligne and a_montant_ligne:
            score += 1

    return (score / len(lignes_data)) >= 0.30   # au moins 30 % de lignes "transaction"


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACTION PDF
# ══════════════════════════════════════════════════════════════════════════════
def _detecter_colonnes(header_row: list) -> tuple:
    """À partir de la ligne d'en-tête, retourne (idx_date, idx_libelle, idx_debit, idx_credit).
    Retourne None si les colonnes essentielles sont introuvables.
    """
    idx_date = idx_lib = idx_deb = idx_cred = None
    _DATE_KEYS    = {"date", "date opé.", "date ope.", "date opé", "date ope",
                     "date opération", "date operation", "jour"}
    _LIBELLE_KEYS = {"libellé", "libelle", "libellé des opérations",
                     "libelle des operations", "opération", "operation",
                     "désignation", "description", "nature"}
    _DEBIT_KEYS   = {"débit", "debit", "débit €", "débit eur", "débit euros",
                     "mouvements débiteurs"}
    _CREDIT_KEYS  = {"crédit", "credit", "crédit €", "crédit eur", "crédit euros",
                     "mouvements créditeurs"}

    for i, cell in enumerate(header_row):
        c = str(cell or "").lower().strip().replace("\n", " ")
        if c in _DATE_KEYS and idx_date is None:
            idx_date = i
        elif c in _LIBELLE_KEYS and idx_lib is None:
            idx_lib = i
        elif c in _DEBIT_KEYS and idx_deb is None:
            idx_deb = i
        elif c in _CREDIT_KEYS and idx_cred is None:
            idx_cred = i

    # Fallback : si pas de colonne crédit distincte mais débit trouvé,
    # on cherche la colonne suivante
    if idx_deb is not None and idx_cred is None and idx_deb + 1 < len(header_row):
        idx_cred = idx_deb + 1

    if idx_date is None or idx_lib is None or idx_deb is None:
        return None
    return (idx_date, idx_lib, idx_deb, idx_cred)


def _parse_montant(cell) -> float:
    """Convertit une cellule texte en float (gère virgule, espace milliers, €)."""
    s = str(cell or "").strip()
    # Supprimer tout sauf chiffres, virgule, point
    s = re.sub(r"[^\d,.]", "", s)
    if not s:
        return 0.0
    # Si virgule et point : la virgule est séparateur décimal (format FR)
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _fusionner_lignes(table: list, idx_date: int, idx_lib: int,
                     idx_deb: int, idx_cred: int, header_idx: int) -> list:
    """Fusionne les lignes de continuation dans un tableau bancaire.

    Une ligne de continuation est une ligne dont la colonne date est vide
    ET les colonnes débit/crédit sont vides : elle contient uniquement du
    texte complémentaire dans la colonne libellé, qui appartient à
    l'opération précédente.

    Exemples CA Pyrénées Gascogne :
      L3  05.01  Prlv CA Consumer Finance       566,39
      L4         290202529437202257 FR35290...           ← continuation → fusionné
      L10 07.01  Prlv ** Intérets débiteurs     2,16
      L11        Période : 4 Trim 25 TAEG=...           ← continuation → fusionné
    """
    fusionnees = []
    for ri, row in enumerate(table):
        if ri <= header_idx:
            continue
        if not row or len(row) <= max(c for c in (idx_date, idx_lib, idx_deb, idx_cred) if c is not None):
            continue

        date_cell  = str(row[idx_date] or "").strip()
        lib_cell   = str(row[idx_lib]  or "").strip().replace("\n", " ")
        deb_cell   = str(row[idx_deb]  or "").strip()
        cred_cell  = str(row[idx_cred] or "").strip() if idx_cred is not None else ""

        est_continuation = (
            not date_cell
            and lib_cell
            and not deb_cell
            and not cred_cell
        )

        if est_continuation and fusionnees:
            # Ajouter le texte complémentaire au libellé de la ligne précédente
            # mais seulement s'il apporte une info utile (pas une référence bancaire pure)
            if not _RE_LIGNE_PARASITE.search(lib_cell):
                fusionnees[-1]["libelle_suite"] = (
                    fusionnees[-1].get("libelle_suite", "") + " " + lib_cell
                ).strip()
        else:
            fusionnees.append({
                "date":         date_cell,
                "libelle":      lib_cell,
                "debit_cell":   deb_cell,
                "credit_cell":  cred_cell,
                "libelle_suite": "",
            })

    return fusionnees


def extraire_donnees_pdf(file_path: str) -> pd.DataFrame:
    """Extrait uniquement les tableaux qui ressemblent à un relevé de transactions.

    Améliorations :
    - Détecte les colonnes date/libellé/débit/crédit via l'en-tête.
    - Fusionne les lignes de continuation (libellé sur plusieurs lignes du tableau).
    - Le libellé final = ligne principale + suite, pour une meilleure catégorisation.
    """
    rows = []
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                for table in (page.extract_tables() or []):

                    if not _tableau_est_un_releve(table):
                        continue

                    # Détecter les colonnes via l'en-tête
                    cols = None
                    header_idx = 0
                    for hi, row in enumerate(table[:3]):
                        cols = _detecter_colonnes(row)
                        if cols:
                            header_idx = hi
                            break
                    if not cols:
                        cols = (0, 2, 3, 4)

                    idx_date, idx_lib, idx_deb, idx_cred = cols

                    # Fusionner les lignes de continuation
                    lignes = _fusionner_lignes(table, idx_date, idx_lib,
                                               idx_deb, idx_cred, header_idx)

                    for ligne in lignes:
                        date    = ligne["date"]
                        # Libellé complet = ligne principale + éventuelles suites
                        suite   = ligne["libelle_suite"]
                        libelle = (ligne["libelle"] + (" " + suite if suite else "")).strip()

                        if not date or not libelle:
                            continue
                        if not _RE_VRAIE_DATE.search(date):
                            continue
                        if libelle.lower().strip() in _ENTETES:
                            continue
                        if _RE_PRLV_CARTE.search(libelle):
                            continue
                        if _RE_LIGNE_PARASITE.search(libelle):
                            continue

                        debit  = _parse_montant(ligne["debit_cell"])
                        credit = _parse_montant(ligne["credit_cell"])
                        rows.append({"Date": date, "Libellé": libelle,
                                     "Débit": debit, "Crédit": credit})
    except Exception as e:
        st.error(f"Erreur extraction {os.path.basename(file_path)} : {e}")
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
# CATÉGORISATION
# ══════════════════════════════════════════════════════════════════════════════

# Tokens sans valeur distinctive — supprimés du mot-clé mémorisé.
# Inclut : types d'opération, articles, abréviations bancaires, mots de liaison.
_TOKENS_GENERIQUES = re.compile(
    r"""^(
        # Types d'opération
        virement | vir | inst | sepa | prlv | pr[eé]l[eè]vement
      | paiement | psc | tpe | cb | chq | ch[eè]que | ech | cotis
      | r[eè]glement | r[eé]gl | fact | facture
        # Articles et prépositions
      | carte | vers | de | du | le | la | les | au | aux | et | ou | par | sur
        # Civilités
      | m | mr | mme | m\. | mr\. | mme\.
        # Abréviations banque
      | ag | gestion | [eé]ch[eé]ance | [eé]ch[eé]ances
    )$""",
    re.IGNORECASE | re.VERBOSE,
)

# Tokens qui signalent une partie NON STABLE du libellé (à ignorer ou stopper)
_RE_TOKEN_BRUIT = re.compile(
    r"""(
        \d{2}[/.]\d{2,4}          # date  01/2026, 01.01
      | \d{4,}                 # numéro >= 4 chiffres (code PSC 1201, contrats...)
      | ^-$                        # tiret isolé séparateur
      | IBAN | BIC | REF
      | CONTRAT | ECHEANCE | COTISATION | PERIODIQUE
      | CORE                   # suffixe SEPA technique
      | ^FR\d{2}                   # IBAN FR…
      | \*\*                       # masque CA type "Cotis ** Offre"
      | ^[A-Z]{2,4}-\d+$           # code référence type GEC-01, KF20…
      | ^[A-Z]\d{2,}               # code alphanumérique type X1181, K20…
    )""",
    re.IGNORECASE | re.VERBOSE,
)


def _extraire_tronc(libelle: str, max_mots_utiles: int = 3) -> str:
    """Extrait le mot-clé DISTINCTIF d'un libellé bancaire.

    Principe :
    - On parcourt les tokens du libellé.
    - Les tokens "bruit" (numéros, dates, codes techniques) sont ignorés.
    - Les tokens génériques (Virement, PSC, vers, de...) sont ignorés.
    - On collecte jusqu'à max_mots_utiles tokens vraiment informatifs.

    Exemples :
      "Virement Vir Inst vers Dieme Samba"           → "Dieme Samba"
      "PAIEMENT PSC 1201 MASSEUBE DR MARSEILLAN"     → "MASSEUBE DR MARSEILLAN"
      "Prlv Predica Crédit Agricole Echéance 01/2026" → "Predica Crédit Agricole"
      "PRLV SEPA SFR"                                → "SFR"
      "Prlv Groupama Gan Vie"                        → "Groupama Gan Vie"
      "Sendwave 1060 Bruxelles"                      → "Sendwave Bruxelles"
      "Cotis ** Offre Premium"                       → "Offre Premium"
      "Ech Prêt 00000109451 Echéance 05/01/26"       → "Prêt"
    """
    tokens      = libelle.split()
    mots_utiles = []

    for tok in tokens:
        # Token bruit → on l'ignore et on continue (pas d'arrêt définitif)
        if _RE_TOKEN_BRUIT.search(tok) or tok == "-":
            continue
        # Token générique → on l'ignore sans compter
        if _TOKENS_GENERIQUES.match(tok):
            continue
        # Token utile
        mots_utiles.append(tok)
        if len(mots_utiles) >= max_mots_utiles:
            break

    return " ".join(mots_utiles) if mots_utiles else libelle.strip()


# Détecte un libellé de chèque — le numéro seul ne permet pas de catégoriser.
_RE_CHEQUE = re.compile(r"^\s*ch[eè]que\s+\d+\s*$", re.IGNORECASE)

def _est_cheque(libelle: str) -> bool:
    return bool(_RE_CHEQUE.match(libelle))

def categoriser(df: pd.DataFrame) -> pd.DataFrame:
    """Applique les règles de catégorisation par mots-clés.

    Les chèques (libellé = 'Chèque XXXXXXX') sont systématiquement exclus
    de la catégorisation automatique — leur objet est inconnu sur le relevé.
    Ils restent en 'À catégoriser (chèque)' pour forcer une saisie manuelle.
    """
    df = df.copy()
    df["Catégorie"] = "À catégoriser"

    # Marquer les chèques avant toute règle
    masque_cheque = df["Libellé"].apply(_est_cheque)
    df.loc[masque_cheque, "Catégorie"] = "À catégoriser (chèque)"

    # Appliquer le registre des chèques déjà connus (clé = date|libellé)
    cheques_connus = st.session_state.get("cheques_connus", {})
    for idx, row in df[masque_cheque].iterrows():
        cle = _cle_cheque(row["Date"], row["Libellé"])
        if cle in cheques_connus:
            df.at[idx, "Catégorie"] = cheques_connus[cle]["categorie"]

    # Appliquer les règles mots-clés sur les lignes NON chèque uniquement
    for cat, mots in st.session_state["categories"].items():
        for mot in mots:
            mask = (
                df["Libellé"].str.contains(re.escape(mot), case=False, na=False)
                & ~masque_cheque
            )
            df.loc[mask, "Catégorie"] = cat

    return df

def appliquer_categorisation():
    if st.session_state["combined_df"] is not None:
        df = st.session_state["combined_df"].drop(columns=["Catégorie"], errors="ignore")
        st.session_state["combined_df"] = categoriser(df)


# ══════════════════════════════════════════════════════════════════════════════
# GRAPHIQUES
# ══════════════════════════════════════════════════════════════════════════════
def _palette_cat(categories: list) -> dict:
    """Une couleur fixe par catégorie (ordre A→Z) partagée entre les deux camemberts."""
    cats_triees = sorted(set(categories), key=str.lower)
    return {c: PALETTE[i % len(PALETTE)] for i, c in enumerate(cats_triees)}

def graphique_pie(data: pd.Series, titre: str, palette: dict):
    """Camembert Plotly avec pourcentages et montants au survol."""
    data = data[data > 0]
    if data.empty:
        st.info("Aucune donnée.")
        return
    fig = px.pie(
        values=data.values,
        names=data.index,
        title=titre,
        color=data.index,
        color_discrete_map=palette,
        hole=0.35,
    )
    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>%{value:,.2f} €<br>%{percent}<extra></extra>",
    )
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="v", x=1.02, y=0.5),
        margin=dict(t=50, b=20, l=20, r=140),
    )
    st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# MODALS
# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
# FORMULAIRES (compatibles toutes versions Streamlit — pas de st.dialog)
# ══════════════════════════════════════════════════════════════════════════════

def form_ajouter_compte(container):
    """Formulaire d'ajout de compte affiché dans un container (expander)."""
    banques = st.session_state["banques"]
    with container:
        # ── Intitulé personnalisé — champ principal ───────────────────────
        st.markdown("#### 🏷️ Intitulé du compte")
        intitule = st.text_input(
            "Intitulé personnalisé *",
            placeholder="Ex : Compte courant principal, Compte joint, Livret A…",
            help="Cet intitulé sera utilisé partout dans l'application pour identifier ce compte.",
            key="_f_intitule",
        )
        st.divider()

        # ── Banque & caisse ───────────────────────────────────────────────
        st.markdown("#### 🏦 Établissement bancaire")
        st.write("**Option 1 — Choisir dans la liste**")
        col1, col2 = st.columns(2)
        with col1:
            banques_triees = sorted(banques.keys(), key=str.lower)
            banque_sel = st.selectbox("Banque", [""] + banques_triees, key="_f_banque")
        with col2:
            caisses    = sorted(banques.get(banque_sel, []), key=str.lower) if banque_sel else []
            caisse_sel = st.selectbox("Caisse locale", [""] + caisses, key="_f_caisse")

        st.write("**Option 2 — Saisie libre** (si votre banque n'est pas dans la liste)")
        col3, col4 = st.columns(2)
        with col3:
            banque_libre = st.text_input("Banque (libre)", key="_f_banque_libre")
        with col4:
            caisse_libre = st.text_input("Caisse (libre)", key="_f_caisse_libre")

        if st.button("✅ Valider l'ajout", key="_f_valider_compte"):
            intitule_f = intitule.strip()
            banque_f   = banque_libre.strip() or banque_sel
            caisse_f   = caisse_libre.strip() or caisse_sel

            if not intitule_f:
                st.warning("L'intitulé personnalisé est obligatoire.")
                return
            if not banque_f or not caisse_f:
                st.warning("Veuillez renseigner banque et caisse.")
                return

            # Vérifier que l'intitulé n'existe pas déjà
            intitules_existants = [c["intitule"] for c in st.session_state["comptes"]]
            if intitule_f in intitules_existants:
                st.warning(f"Un compte avec l'intitulé « {intitule_f} » existe déjà.")
                return

            nouveau = {"intitule": intitule_f, "banque": banque_f, "caisse": caisse_f}
            st.session_state["comptes"].append(nouveau)
            # Trier les comptes A→Z par intitulé
            st.session_state["comptes"] = sorted(
                st.session_state["comptes"], key=lambda c: c["intitule"].lower()
            )
            if banque_libre.strip() and banque_libre.strip() not in banques:
                st.session_state["banques"][banque_libre.strip()] = [caisse_libre.strip() or "National"]
            # Trier le dict banques A→Z après chaque ajout
            st.session_state["banques"] = dict(sorted(
                st.session_state["banques"].items(), key=lambda x: x[0].lower()
            ))
            sauvegarder_comptes()
            st.success(f"Compte « {intitule_f} » ({banque_f} / {caisse_f}) ajouté !")
            st.rerun()


def form_categories(container):
    """Formulaire de gestion des catégories affiché dans un container (expander)."""
    cats = st.session_state["categories"]
    with container:
        action = st.radio(
            "Action",
            ["➕ Ajouter", "✏️ Modifier", "🗑️ Supprimer"],
            horizontal=True, key="_fc_action",
        )

        if action == "➕ Ajouter":
            new_name = st.text_input("Nom de la nouvelle catégorie", key="_fc_new_name")
            new_mots = st.text_input(
                "Mots-clés (séparés par des virgules)",
                help="Ex : SUPER U, LECLERC, LIDL",
                key="_fc_new_mots",
            )
            if st.button("✅ Ajouter", key="_fc_add"):
                nom = new_name.strip()
                if not nom:
                    st.warning("Nom requis.")
                elif nom in cats:
                    st.warning("Cette catégorie existe déjà.")
                else:
                    mots = [m.strip().upper() for m in new_mots.split(",") if m.strip()]
                    cats[nom] = mots
                    sauvegarder_categories()
                    appliquer_categorisation()
                    st.success(f"Catégorie « {nom} » ajoutée.")
                    st.rerun()

        elif action == "✏️ Modifier":
            cat_sel  = st.selectbox("Catégorie à modifier",
                                    sorted(cats.keys(), key=str.lower), key="_fc_edit_sel")
            mots_act = ", ".join(cats.get(cat_sel, []))
            new_mots = st.text_input("Mots-clés", value=mots_act, key="_fc_edit_mots")
            new_name = st.text_input("Renommer (laisser vide = garder le nom)", key="_fc_rename")
            if st.button("✅ Enregistrer", key="_fc_save"):
                mots_list = [m.strip().upper() for m in new_mots.split(",") if m.strip()]
                nom_final = new_name.strip() or cat_sel
                if nom_final != cat_sel:
                    del cats[cat_sel]
                cats[nom_final] = mots_list
                sauvegarder_categories()
                appliquer_categorisation()
                st.success("Catégorie mise à jour.")
                st.rerun()

        elif action == "🗑️ Supprimer":
            cat_sel = st.selectbox("Catégorie à supprimer",
                                   sorted(cats.keys(), key=str.lower), key="_fc_del_sel")
            st.warning(f"Les transactions « {cat_sel} » passeront en « À catégoriser ».")
            if st.button("🗑️ Confirmer la suppression", key="_fc_del", type="primary"):
                del cats[cat_sel]
                sauvegarder_categories()
                appliquer_categorisation()
                st.success(f"Catégorie « {cat_sel} » supprimée.")
                st.rerun()

        st.divider()
        st.markdown("#### ♻️ Réinitialiser toutes les catégories")
        st.caption("Remet les catégories de base vides. Tous les mots-clés enregistrés seront effacés.")
        if st.checkbox("Je confirme vouloir réinitialiser", key="_fc_confirm_reset"):
            if st.button("♻️ Réinitialiser", key="_fc_reset", type="primary"):
                st.session_state["categories"] = dict(CATEGORIES_DEFAUT)
                sauvegarder_categories()
                appliquer_categorisation()
                st.success("Catégories réinitialisées.")
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# LAYOUT
# ══════════════════════════════════════════════════════════════════════════════
st.title("🏦 Analyse de Relevés Bancaires")

tab_comptes, tab_fichiers, tab_categories, tab_analyse, tab_regles = st.tabs([
    "📋 Comptes", "📁 Fichiers", "🏷️ Catégorisation", "📊 Analyse", "⚙️ Règles",
])

# ─────────────────────────────────────────────
# ONGLET 1 — Comptes
# ─────────────────────────────────────────────
with tab_comptes:
    st.subheader("Comptes bancaires enregistrés")
    comptes = st.session_state["comptes"]

    if comptes:
        df_comptes = pd.DataFrame([{
            "#":        i + 1,
            "Intitulé": c["intitule"],
            "Banque":   c["banque"],
            "Caisse":   c["caisse"],
        } for i, c in enumerate(comptes)])
        st.dataframe(df_comptes, use_container_width=True, hide_index=True)

        with st.expander("🗑️ Supprimer un compte"):
            options_del  = [label_compte(c) for c in comptes]
            label_del    = st.selectbox("Compte à supprimer", options_del, key="del_compte_sel")
            idx_del      = options_del.index(label_del)
            st.caption(f"Intitulé : **{comptes[idx_del]['intitule']}** — {comptes[idx_del]['banque']} / {comptes[idx_del]['caisse']}")
            if st.button("Supprimer", key="btn_del_compte", type="primary"):
                st.session_state["comptes"].pop(idx_del)
                sauvegarder_comptes()
                st.rerun()
    else:
        st.info("Aucun compte enregistré. Ajoutez-en un ci-dessous.")

    # Bouton toggle : efface les champs à chaque ouverture
    _KEYS_FORM_COMPTE = [
        "_f_intitule", "_f_banque", "_f_caisse",
        "_f_banque_libre", "_f_caisse_libre",
    ]
    if st.button("➕ Ajouter un compte bancaire", key="btn_toggle_add_compte"):
        # Effacer les valeurs précédentes pour repartir de zéro
        for k in _KEYS_FORM_COMPTE:
            if k in st.session_state:
                del st.session_state[k]
        st.session_state["_show_add_compte"] = not st.session_state.get("_show_add_compte", False)

    if st.session_state.get("_show_add_compte", False):
        with st.container(border=True):
            form_ajouter_compte(st.container())

# ─────────────────────────────────────────────
# ONGLET 2 — Fichiers
# ─────────────────────────────────────────────
with tab_fichiers:
    st.subheader("Chargement des relevés PDF")
    comptes = st.session_state["comptes"]

    if not comptes:
        st.warning("Ajoutez d'abord des comptes dans l'onglet « Comptes ».")
        st.stop()

    # Labels affichés = intitulé propre
    labels_comptes = [label_compte(c) for c in comptes]

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        labels_sel = st.multiselect("Comptes", labels_comptes, default=labels_comptes, key="f_comptes")
    with col_b:
        annees_sel = st.multiselect("Années", ["2024", "2025", "2026"], default=["2026"], key="f_annees")
    with col_c:
        mois_sel   = st.multiselect("Mois", MOIS, default=["janvier"], key="f_mois")

    if not (labels_sel and annees_sel and mois_sel):
        st.info("Sélectionnez au moins un compte, une année et un mois.")
        st.stop()

    # Retrouver les dicts comptes correspondant aux labels sélectionnés
    comptes_sel   = [c for c in comptes if label_compte(c) in labels_sel]
    total_attendu = len(comptes_sel) * len(annees_sel) * len(mois_sel)
    fichiers_ok   = []

    for compte in comptes_sel:
        for annee in annees_sel:
            for mois in mois_sel:
                # Nom de fichier basé sur l'intitulé (stable et lisible)
                safe    = re.sub(r"[^\w]", "_", compte["intitule"])
                safe    = re.sub(r"_+", "_", safe).strip("_")
                nom     = f"{safe}_{mois}_{annee}.pdf"
                dossier = os.path.join(PDF_BASE_PATH, annee, mois)
                chemin  = os.path.join(dossier, nom)
                os.makedirs(dossier, exist_ok=True)

                label   = label_compte(compte)
                if os.path.exists(chemin):
                    st.success(f"✅ {nom} trouvé.")
                    fichiers_ok.append(chemin)
                else:
                    st.warning(f"❌ {nom} manquant.")
                    up = st.file_uploader(
                        f"PDF — {label} / {mois} {annee}",
                        type="pdf",
                        key=f"up_{compte['intitule']}_{mois}_{annee}",
                    )
                    if up:
                        with open(chemin, "wb") as fh:
                            fh.write(up.getbuffer())
                        st.success(f"{nom} enregistré.")
                        fichiers_ok.append(chemin)

    st.session_state["fichiers_charges"] = fichiers_ok
    manquants = total_attendu - len(fichiers_ok)

    if manquants > 0:
        st.error(f"{manquants} fichier(s) manquant(s).")
    else:
        st.success("Tous les fichiers sont disponibles.")
        if st.button("🔄 Extraire et consolider", key="btn_extraire"):
            dfs = []
            with st.spinner("Extraction en cours…"):
                for path in fichiers_ok:
                    df_tmp = extraire_donnees_pdf(path)
                    if not df_tmp.empty:
                        df_tmp["Source"] = os.path.basename(path)
                        dfs.append(df_tmp)
            if dfs:
                consolidated = pd.concat(dfs, ignore_index=True)
                st.session_state["combined_df"] = categoriser(consolidated)
                st.success(f"{len(consolidated)} transactions extraites.")
            else:
                st.error("Aucune donnée extraite. Vérifiez la structure de vos PDFs.")

# ─────────────────────────────────────────────
# ONGLET 3 — Catégorisation
# ─────────────────────────────────────────────
with tab_categories:
    st.subheader("Catégorisation des transactions")

    df = st.session_state.get("combined_df")
    if df is None:
        st.info("Extrayez d'abord les données dans l'onglet « Fichiers ».")
        st.stop()

    with st.expander("📄 Toutes les transactions", expanded=False):
        st.dataframe(df, use_container_width=True, hide_index=True)

    # ── Chèques — section séparée obligatoire ────────────────────────────────
    cheques = df[df["Catégorie"] == "À catégoriser (chèque)"].copy()
    if not cheques.empty:
        st.subheader(f"🏦 Chèques à catégoriser manuellement — {len(cheques)} chèque(s)")
        st.warning(
            "Les chèques ne peuvent pas être catégorisés automatiquement "
            "car leur objet n'apparaît pas sur le relevé. "
            "Veuillez sélectionner une catégorie pour chacun."
        )
        cats_dispo_chq = sorted(st.session_state["categories"].keys(), key=str.lower)
        assign_chq = {}
        for _, row_chq in cheques.iterrows():
            c1, c2, c3, c4 = st.columns([2, 1, 2, 3])
            with c1:
                st.write(f"🟠 **{row_chq['Libellé']}**")
            with c2:
                sens = "💸" if row_chq["Débit"] > 0 else "💰"
                montant = row_chq["Débit"] if row_chq["Débit"] > 0 else row_chq["Crédit"]
                st.caption(f"{sens} {montant:,.2f} €")
            with c3:
                st.caption(f"Date : {row_chq['Date']}")
            with c4:
                choix_chq = st.selectbox(
                    "cat",
                    ["— Choisir —"] + cats_dispo_chq + ["➕ Nouvelle catégorie…"],
                    key=f"chq_{row_chq.name}",
                    label_visibility="collapsed",
                )
                if choix_chq == "➕ Nouvelle catégorie…":
                    nouvelle_chq = st.text_input(
                        "Nom", key=f"new_chq_{row_chq.name}",
                        placeholder="Nouvelle catégorie",
                        label_visibility="collapsed",
                    )
                    if nouvelle_chq.strip():
                        assign_chq[row_chq.name] = ("new", nouvelle_chq.strip())
                elif choix_chq != "— Choisir —":
                    assign_chq[row_chq.name] = ("existing", choix_chq)

        if st.button("✅ Valider les chèques", key="btn_valider_chq"):
            cats          = st.session_state["categories"]
            chq_connus    = st.session_state["cheques_connus"]
            for idx_chq, (kind, valeur) in assign_chq.items():
                if kind == "new" and valeur not in cats:
                    cats[valeur] = []
                cat_finale = valeur
                row_data   = st.session_state["combined_df"].loc[idx_chq]
                # Clé = date + libellé complet pour unicité absolue
                cle = _cle_cheque(row_data["Date"], row_data["Libellé"])
                chq_connus[cle] = {
                    "categorie": cat_finale,
                    "libelle":   row_data["Libellé"],
                    "date":      row_data["Date"],
                    "montant":   float(row_data["Débit"] or row_data["Crédit"]),
                }
                st.session_state["combined_df"].loc[idx_chq, "Catégorie"] = cat_finale
            if assign_chq:
                sauvegarder_categories()
                sauvegarder_cheques()
                st.success(f"{len(assign_chq)} chèque(s) catégorisé(s) et mémorisé(s).")
                st.rerun()
        st.divider()

    # ── Transactions non catégorisées ────────────────────────────────────────
    non_cat = df[df["Catégorie"] == "À catégoriser"].copy()
    nb_total_a_faire = len(non_cat) + len(cheques)
    st.subheader(f"Transactions à catégoriser — {len(non_cat)} libellé(s)")

    if non_cat.empty and cheques.empty:
        st.success("✅ Toutes les transactions sont catégorisées.")
    elif non_cat.empty:
        st.success("✅ Tous les libellés non-chèque sont catégorisés. Traitez les chèques ci-dessus.")
    else:
        cats_dispo = sorted(st.session_state["categories"].keys(), key=str.lower)

        # Résumé par libellé unique : occurrences, total débit, total crédit
        resume = (
            non_cat.groupby("Libellé")
                   .agg(
                       Occurrences=("Libellé", "count"),
                       Total_Débit=("Débit", "sum"),
                       Total_Crédit=("Crédit", "sum"),
                   )
                   .reset_index()
                   .sort_values("Libellé")
        )

        st.info(f"{len(resume)} libellé(s) distinct(s) — choisissez une catégorie pour chacun.")

        # En-têtes
        h1, h2, h3, h4, h5 = st.columns([3, 1, 1, 2, 3])
        h1.markdown("**Libellé**")
        h2.markdown("**Nb**")
        h3.markdown("**Sens**")
        h4.markdown("**Montant total**")
        h5.markdown("**Catégorie**")
        st.divider()

        assignations = {}

        for _, rr in resume.iterrows():
            libelle  = rr["Libellé"]
            occ      = int(rr["Occurrences"])
            t_deb    = rr["Total_Débit"]
            t_cred   = rr["Total_Crédit"]

            # Sens dominant de la ligne
            if t_deb > 0 and t_cred == 0:
                sens    = "💸 Sortie"
                montant = f"−{t_deb:,.2f} €"
                icone   = "🔴"
            elif t_cred > 0 and t_deb == 0:
                sens    = "💰 Entrée"
                montant = f"+{t_cred:,.2f} €"
                icone   = "🟢"
            else:
                sens    = "↔️ Mixte"
                montant = f"D:{t_deb:,.2f} € / C:{t_cred:,.2f} €"
                icone   = "🟡"

            c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 2, 3])
            with c1:
                st.write(f"{icone} **{libelle}**")
            with c2:
                st.caption(f"{occ}×")
            with c3:
                st.caption(sens)
            with c4:
                st.caption(montant)
            with c5:
                choix = st.selectbox(
                    "cat",
                    ["— Choisir —"] + cats_dispo + ["➕ Nouvelle catégorie…"],
                    key=f"sel_{libelle}",
                    label_visibility="collapsed",
                )
                if choix == "➕ Nouvelle catégorie…":
                    nouvelle = st.text_input(
                        "Nom",
                        key=f"new_{libelle}",
                        placeholder="Nom de la nouvelle catégorie",
                        label_visibility="collapsed",
                    )
                    if nouvelle.strip():
                        assignations[libelle] = ("new", nouvelle.strip())
                elif choix != "— Choisir —":
                    assignations[libelle] = ("existing", choix)
                # Afficher le mot-clé qui sera mémorisé
                if choix != "— Choisir —":
                    tronc = _extraire_tronc(libelle)
                    if tronc != libelle:
                        st.caption(f"🔑 Mémorisé : *{tronc}*")

        if st.button("✅ Appliquer les catégorisations", key="btn_apply_cats"):
            cats = st.session_state["categories"]
            for libelle, (kind, valeur) in assignations.items():
                if kind == "new":
                    if valeur not in cats:
                        cats[valeur] = []
                    cat_finale = valeur
                else:
                    cat_finale = valeur

                # ── Mot-clé intelligent ───────────────────────────────────
                # Pour les libellés longs et variables (ex : "PRLV PREDICA ...
                # Echéance 01/2026 - Contrat 86987..."), on extrait un tronc
                # stable : les premiers mots avant un chiffre, une date ou un
                # tiret — ce tronc sera le mot-clé enregistré et cherché le
                # mois suivant même si la fin du libellé change.
                mot_cle = _extraire_tronc(libelle)

                mots_existants = [m.upper() for m in cats.get(cat_finale, [])]
                if mot_cle.upper() not in mots_existants:
                    cats.setdefault(cat_finale, []).append(mot_cle)

                # Appliquer au DataFrame courant
                st.session_state["combined_df"].loc[
                    st.session_state["combined_df"]["Libellé"] == libelle,
                    "Catégorie",
                ] = cat_finale

            sauvegarder_categories()
            st.success("Catégorisations appliquées. Les mots-clés stables ont été mémorisés pour les prochains relevés.")
            st.rerun()

# ─────────────────────────────────────────────
# ONGLET 4 — Analyse
# ─────────────────────────────────────────────
with tab_analyse:
    st.subheader("📊 Analyse des flux financiers")

    df = st.session_state.get("combined_df")
    if df is None:
        st.info("Extrayez d'abord les données dans l'onglet « Fichiers ».")
        st.stop()

    # ── KPI globaux ──────────────────────────────────────────────────────────
    total_sorties = df["Débit"].sum()
    total_entrees = df["Crédit"].sum()
    solde_net     = total_entrees - total_sorties

    m1, m2, m3 = st.columns(3)
    m1.metric("💸 Total sorties",  f"{total_sorties:,.2f} €")
    m2.metric("💰 Total entrées",  f"{total_entrees:,.2f} €")
    m3.metric(
        "📊 Solde net",
        f"{solde_net:,.2f} €",
        delta=f"{solde_net:+,.2f} €",
        delta_color="normal",
    )

    st.divider()

    # ── Tableau récapitulatif par catégorie ──────────────────────────────────
    rapport = (
        df.groupby("Catégorie")
          .agg(Sorties=("Débit", "sum"), Entrées=("Crédit", "sum"))
          .assign(Solde=lambda x: x["Entrées"] - x["Sorties"])
          .sort_index()   # A→Z
    )

    with st.expander("📋 Tableau récapitulatif par catégorie", expanded=True):
        st.dataframe(
            rapport.style
                   .format({"Sorties": "{:,.2f} €", "Entrées": "{:,.2f} €", "Solde": "{:,.2f} €"})
                   .background_gradient(subset=["Solde"], cmap="RdYlGn"),
            use_container_width=True,
        )

    st.divider()

    # ── Graphiques camembert : sorties | entrées ─────────────────────────────
    # Palette commune : même couleur pour une même catégorie dans les deux graphiques
    toutes_cats = rapport.index.tolist()
    palette     = _palette_cat(toutes_cats)

    col_g, col_d = st.columns(2)
    with col_g:
        st.markdown("### 💸 Répartition des sorties par catégorie")
        graphique_pie(rapport["Sorties"], "Sorties par catégorie", palette)
    with col_d:
        st.markdown("### 💰 Répartition des entrées par catégorie")
        graphique_pie(rapport["Entrées"], "Entrées par catégorie", palette)

    st.divider()

    # ── Détail par catégorie ─────────────────────────────────────────────────
    st.markdown("### 🔍 Détail d'une catégorie")
    toutes_cats_liste = sorted(df["Catégorie"].unique().tolist(), key=str.lower)
    cat_detail = st.selectbox("Choisir une catégorie à détailler", toutes_cats_liste,
                              key="detail_cat_sel")

    df_detail = (
        df[df["Catégorie"] == cat_detail]
        [["Date", "Libellé", "Débit", "Crédit", "Source"]]
        .copy()
        .sort_values("Date")
    )

    # Totaux de la sélection
    d1, d2, d3 = st.columns(3)
    d1.metric("Nb transactions", len(df_detail))
    d2.metric("Total sorties",   f"{df_detail['Débit'].sum():,.2f} €")
    d3.metric("Total entrées",   f"{df_detail['Crédit'].sum():,.2f} €")

    st.dataframe(
        df_detail.style.format({"Débit": "{:,.2f} €", "Crédit": "{:,.2f} €"}),
        use_container_width=True,
        hide_index=True,
    )

    # Export CSV du détail uniquement
    csv_detail = df_detail.to_csv(index=False, sep=";").encode("utf-8-sig")
    st.download_button(
        f"⬇️ Télécharger le détail « {cat_detail} »",
        data=csv_detail,
        file_name=f"detail_{cat_detail.replace(' ', '_')}.csv",
        mime="text/csv",
        key="dl_detail",
    )

    st.divider()

    # ── Export CSV complet ───────────────────────────────────────────────────
    csv = df.to_csv(index=False, sep=";").encode("utf-8-sig")
    st.download_button(
        "⬇️ Télécharger toutes les transactions en CSV",
        data=csv,
        file_name="transactions_categoriees.csv",
        mime="text/csv",
    )


# ─────────────────────────────────────────────
# ONGLET 5 — Règles (catégories + mots-clés)
# ─────────────────────────────────────────────
with tab_regles:
    st.subheader("⚙️ Gestion des catégories et mots-clés")
    st.caption(
        "Les mots-clés sont les termes recherchés dans les libellés de vos relevés. "
        "Plus ils sont courts et génériques (ex : *Amazon*, *SFR*, *Groupama*), "
        "plus ils capturent de variantes automatiquement."
    )

    cats = st.session_state["categories"]

    # ── Vue tableau de toutes les catégories et mots-clés ────────────────────
    st.markdown("### 📋 Vue d'ensemble")

    if cats:
        rows_vue = []
        for cat, mots in sorted(cats.items(), key=lambda x: x[0].lower()):
            rows_vue.append({
                "Catégorie":   cat,
                "Nb mots-clés": len(mots),
                "Mots-clés":   ", ".join(mots) if mots else "—  aucun",
            })
        st.dataframe(
            pd.DataFrame(rows_vue),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Catégorie":    st.column_config.TextColumn(width="medium"),
                "Nb mots-clés": st.column_config.NumberColumn(width="small"),
                "Mots-clés":    st.column_config.TextColumn(width="large"),
            }
        )
    else:
        st.info("Aucune catégorie définie.")

    st.divider()

    # ── Actions sur les catégories ────────────────────────────────────────────
    col_act1, col_act2, col_act3 = st.columns(3)

    # ── Créer une catégorie ───────────────────────────────────────────────────
    with col_act1:
        with st.container(border=True):
            st.markdown("#### ➕ Nouvelle catégorie")
            new_cat_name = st.text_input("Nom", key="rg_new_name",
                                         placeholder="Ex : Santé")
            new_cat_mots = st.text_input(
                "Mots-clés (séparés par des virgules)",
                key="rg_new_mots",
                placeholder="Ex : pharmacie, médecin, dentiste",
                help="Laisser vide pour ajouter les mots-clés plus tard.",
            )
            if st.button("✅ Créer", key="rg_btn_create"):
                nom = new_cat_name.strip()
                if not nom:
                    st.warning("Nom requis.")
                elif nom in cats:
                    st.warning("Cette catégorie existe déjà.")
                else:
                    mots = [m.strip().upper() for m in new_cat_mots.split(",") if m.strip()]
                    cats[nom] = mots
                    sauvegarder_categories()
                    appliquer_categorisation()
                    st.success(f"« {nom} » créée.")
                    st.rerun()

    # ── Modifier une catégorie ────────────────────────────────────────────────
    with col_act2:
        with st.container(border=True):
            st.markdown("#### ✏️ Modifier")
            cat_edit = st.selectbox(
                "Catégorie",
                sorted(cats.keys(), key=str.lower),
                key="rg_edit_sel",
            )
            if cat_edit:
                new_edit_name = st.text_input(
                    "Renommer (laisser vide = garder)",
                    key="rg_edit_name",
                    placeholder=cat_edit,
                )
                mots_actuels = ", ".join(cats.get(cat_edit, []))
                new_edit_mots = st.text_area(
                    "Mots-clés (un par ligne ou séparés par virgules)",
                    value="\n".join(cats.get(cat_edit, [])),
                    key="rg_edit_mots",
                    height=120,
                    help="Modifiez, ajoutez ou supprimez des mots-clés. "
                         "Chaque ligne = un mot-clé.",
                )
                if st.button("✅ Enregistrer", key="rg_btn_edit"):
                    # Accepter virgules ou retours à la ligne comme séparateurs
                    raw = new_edit_mots.replace(",", "\n")
                    mots_list = [m.strip().upper() for m in raw.split("\n") if m.strip()]
                    nom_final = new_edit_name.strip() or cat_edit
                    if nom_final != cat_edit:
                        del cats[cat_edit]
                    cats[nom_final] = mots_list
                    sauvegarder_categories()
                    appliquer_categorisation()
                    st.success("Enregistré.")
                    st.rerun()

    # ── Supprimer une catégorie ───────────────────────────────────────────────
    with col_act3:
        with st.container(border=True):
            st.markdown("#### 🗑️ Supprimer")
            cat_del = st.selectbox(
                "Catégorie",
                sorted(cats.keys(), key=str.lower),
                key="rg_del_sel",
            )
            if cat_del:
                nb_mots = len(cats.get(cat_del, []))
                st.warning(
                    f"Supprimera **{cat_del}** "
                    f"et ses **{nb_mots} mot(s)-clé(s)**. "
                    "Les transactions classées ici passeront en « À catégoriser »."
                )
                confirmer = st.checkbox("Je confirme", key="rg_del_confirm")
                if confirmer:
                    if st.button("🗑️ Supprimer", key="rg_btn_del", type="primary"):
                        del cats[cat_del]
                        sauvegarder_categories()
                        appliquer_categorisation()
                        st.success(f"« {cat_del} » supprimée.")
                        st.rerun()

    st.divider()

    # ── Gestion fine des mots-clés d'une catégorie ───────────────────────────
    st.markdown("### 🔑 Mots-clés détaillés")
    st.caption("Ajoutez ou supprimez un mot-clé précis sans toucher aux autres.")

    cat_detail_rg = st.selectbox(
        "Catégorie à détailler",
        sorted(cats.keys(), key=str.lower),
        key="rg_detail_sel",
    )

    if cat_detail_rg:
        mots = cats.get(cat_detail_rg, [])

        if mots:
            st.write(f"**{len(mots)} mot(s)-clé(s) pour « {cat_detail_rg} »**")
            # Afficher chaque mot-clé avec un bouton supprimer
            cols_header = st.columns([4, 1])
            cols_header[0].markdown("**Mot-clé**")
            cols_header[1].markdown("**Action**")

            for i, mot in enumerate(mots):
                c_mot, c_del = st.columns([4, 1])
                with c_mot:
                    st.code(mot, language=None)
                with c_del:
                    if st.button("🗑️", key=f"rg_del_mot_{cat_detail_rg}_{i}",
                                 help=f"Supprimer « {mot} »"):
                        cats[cat_detail_rg].remove(mot)
                        sauvegarder_categories()
                        appliquer_categorisation()
                        st.rerun()
        else:
            st.info(f"Aucun mot-clé pour « {cat_detail_rg} » — toutes les transactions seront à catégoriser manuellement.")

        # Ajouter un mot-clé individuel
        col_add1, col_add2 = st.columns([3, 1])
        with col_add1:
            nouveau_mot = st.text_input(
                "Ajouter un mot-clé",
                key="rg_new_mot",
                placeholder="Ex : LECLERC",
                label_visibility="collapsed",
            )
        with col_add2:
            if st.button("➕ Ajouter", key="rg_btn_add_mot"):
                mot_clean = nouveau_mot.strip().upper()
                if not mot_clean:
                    st.warning("Mot-clé vide.")
                elif mot_clean in [m.upper() for m in cats.get(cat_detail_rg, [])]:
                    st.warning("Ce mot-clé existe déjà.")
                else:
                    cats.setdefault(cat_detail_rg, []).append(mot_clean)
                    sauvegarder_categories()
                    appliquer_categorisation()
                    st.success(f"« {mot_clean} » ajouté à « {cat_detail_rg} ».")
                    st.rerun()

    st.divider()

    # ── Registre des chèques mémorisés ────────────────────────────────────────
    st.markdown("### 🏦 Chèques mémorisés")
    chq_connus = st.session_state.get("cheques_connus", {})

    if chq_connus:
        st.caption(
            "Ces chèques ont déjà été catégorisés. Ils seront classés "
            "automatiquement si le même chèque (même date + même numéro) "
            "apparaît à nouveau — ce qui est rare mais prévu."
        )
        rows_chq = []
        for cle, info in sorted(chq_connus.items()):
            rows_chq.append({
                "Date":      info.get("date", ""),
                "Libellé":   info.get("libelle", ""),
                "Montant":   f"{info.get('montant', 0):,.2f} €",
                "Catégorie": info.get("categorie", ""),
            })
        df_chq = pd.DataFrame(rows_chq)
        st.dataframe(df_chq, use_container_width=True, hide_index=True)

        # Permettre de corriger la catégorie d'un chèque mémorisé
        with st.expander("✏️ Corriger un chèque mémorisé"):
            cles = list(chq_connus.keys())
            labels_cles = [
                f"{chq_connus[c]['date']} — {chq_connus[c]['libelle']} "
                f"({chq_connus[c]['montant']:.2f} €)"
                for c in cles
            ]
            sel_cle_label = st.selectbox("Chèque à corriger", labels_cles,
                                         key="rg_chq_edit_sel")
            sel_cle = cles[labels_cles.index(sel_cle_label)]
            nouvelle_cat_chq = st.selectbox(
                "Nouvelle catégorie",
                sorted(cats.keys(), key=str.lower),
                index=sorted(cats.keys(), key=str.lower).index(
                    chq_connus[sel_cle]["categorie"]
                ) if chq_connus[sel_cle]["categorie"] in cats else 0,
                key="rg_chq_new_cat",
            )
            col_save, col_del = st.columns(2)
            with col_save:
                if st.button("✅ Corriger", key="rg_chq_save"):
                    chq_connus[sel_cle]["categorie"] = nouvelle_cat_chq
                    sauvegarder_cheques()
                    appliquer_categorisation()
                    st.success("Chèque mis à jour.")
                    st.rerun()
            with col_del:
                if st.button("🗑️ Oublier ce chèque", key="rg_chq_del"):
                    del chq_connus[sel_cle]
                    sauvegarder_cheques()
                    st.success("Chèque supprimé du registre.")
                    st.rerun()
    else:
        st.info("Aucun chèque mémorisé pour l'instant.")

    st.divider()

    # ── Réinitialisation ──────────────────────────────────────────────────────
    st.markdown("### ♻️ Réinitialiser toutes les catégories")
    st.caption("Remet les 8 catégories de base vides. Tous les mots-clés seront effacés.")
    if st.checkbox("Je confirme vouloir réinitialiser", key="rg_confirm_reset"):
        if st.button("♻️ Réinitialiser", key="rg_btn_reset", type="primary"):
            st.session_state["categories"] = dict(CATEGORIES_DEFAUT)
            sauvegarder_categories()
            appliquer_categorisation()
            st.success("Catégories réinitialisées.")
            st.rerun()