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

def _chemin_cheques() -> str:
    return os.path.join(PDF_BASE_PATH, "cheques.json")

def _chemin_csv(annee: str, mois: str) -> str:
    return os.path.join(PDF_BASE_PATH, annee, mois, f"transactions_{mois}_{annee}.csv")


def charger_comptes() -> list:
    p_json   = _chemin_comptes()
    p_legacy = _chemin_comptes_legacy()

    if os.path.exists(p_json):
        with open(p_json, "r", encoding="utf-8") as f:
            return json.load(f)

    if os.path.exists(p_legacy):
        comptes = []
        for enc in ("utf-8", "cp1252", "latin-1"):
            try:
                with open(p_legacy, "r", encoding=enc) as f:
                    lignes = f.readlines()
                break
            except (UnicodeDecodeError, LookupError):
                continue
        else:
            lignes = []
        for ligne in lignes:
            ligne = ligne.strip()
            if not ligne:
                continue
            intitule = ligne
            parties  = ligne.split(" - ", 1)
            banque   = parties[0].strip() if len(parties) > 1 else ligne
            reste    = parties[1] if len(parties) > 1 else ""
            m = re.match(r"^(.*?)\s*\((.+)\)$", reste)
            if m:
                caisse   = m.group(1).strip()
                intitule = m.group(2).strip()
            else:
                caisse = reste.strip() or "National"
            comptes.append({"intitule": intitule, "banque": banque, "caisse": caisse})
        sauvegarder_comptes_data(comptes)
        return comptes

    return []

def sauvegarder_comptes_data(comptes: list):
    os.makedirs(PDF_BASE_PATH, exist_ok=True)
    with open(_chemin_comptes(), "w", encoding="utf-8") as f:
        json.dump(comptes, f, ensure_ascii=False, indent=2)

def sauvegarder_comptes():
    sauvegarder_comptes_data(st.session_state["comptes"])

def label_compte(c: dict) -> str:
    return f"{c['intitule']}  —  {c['banque']} / {c['caisse']}"

def charger_categories() -> dict:
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
    os.makedirs(PDF_BASE_PATH, exist_ok=True)
    cats_triees = dict(sorted(
        st.session_state["categories"].items(),
        key=lambda x: x[0].lower(),
    ))
    st.session_state["categories"] = cats_triees
    with open(_chemin_categories(), "w", encoding="utf-8") as f:
        json.dump(cats_triees, f, ensure_ascii=False, indent=2)

def charger_cheques() -> dict:
    p = _chemin_cheques()
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def _cle_cheque(date: str, libelle: str) -> str:
    return f"{date.strip()}|{libelle.strip()}"

def sauvegarder_cheques():
    os.makedirs(PDF_BASE_PATH, exist_ok=True)
    with open(_chemin_cheques(), "w", encoding="utf-8") as f:
        json.dump(st.session_state["cheques_connus"], f, ensure_ascii=False, indent=2)

def sauvegarder_csv(annee: str, mois: str):
    df = st.session_state.get("combined_df")
    if df is None or df.empty:
        return
    chemin = _chemin_csv(annee, mois)
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    df.to_csv(chemin, index=False, sep=";", encoding="utf-8-sig")

def charger_csv(annee: str, mois: str):
    chemin = _chemin_csv(annee, mois)
    if os.path.exists(chemin):
        try:
            df = pd.read_csv(chemin, sep=";", encoding="utf-8-sig")
            df["Date"]      = df["Date"].fillna("").astype(str)
            df["Libellé"]   = df["Libellé"].fillna("").astype(str)
            df["Catégorie"] = df["Catégorie"].fillna("À catégoriser").astype(str)
            df["Débit"]     = pd.to_numeric(df["Débit"],  errors="coerce").fillna(0.0)
            df["Crédit"]    = pd.to_numeric(df["Crédit"], errors="coerce").fillna(0.0)
            # Toujours re-catégoriser au chargement pour détecter
            # chèques et virements opaques même sur anciens CSV
            df = df.drop(columns=["Catégorie"], errors="ignore")
            return df
        except Exception as e:
            st.error(f"Erreur chargement CSV : {e}")
            return None
    return None


# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
def init_state():
    if "comptes" not in st.session_state:
        comptes_charges = charger_comptes()
        st.session_state["comptes"] = sorted(
            comptes_charges,
            key=lambda c: c["intitule"].lower() if isinstance(c, dict) else c.lower()
        )
    if "banques" not in st.session_state:
        st.session_state["banques"] = {
            k: sorted(v, key=str.lower)
            for k, v in sorted(BANQUES_INITIALES.items(), key=lambda x: x[0].lower())
        }
    if "categories" not in st.session_state:
        st.session_state["categories"] = charger_categories()
    if "fichiers_charges" not in st.session_state:
        st.session_state["fichiers_charges"] = []
    if "combined_df" not in st.session_state:
        st.session_state["combined_df"] = None
    if "cheques_connus" not in st.session_state:
        st.session_state["cheques_connus"] = charger_cheques()

init_state()


# ══════════════════════════════════════════════════════════════════════════════
# FILTRES D'EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════
_ENTETES = {
    "libellé", "libelle", "opération", "operation", "désignation",
    "désignation de l'opération", "detail", "détail", "description",
    "nature", "intitulé", "intitule",
}
_ENTETES_DATE = {
    "date", "date opération", "date operation", "date valeur",
    "date de valeur", "jour",
}
_ENTETES_MONTANT = {
    "débit", "debit", "crédit", "credit", "montant", "somme",
    "débit €", "crédit €", "débit eur", "crédit eur",
    "débit euros", "crédit euros",
    "mouvements débiteurs", "mouvements créditeurs",
}
_RE_PRLV_CARTE = re.compile(
    r"(factur\w*\s+carte|prlv\s+carte|remise\s+carte|total\s+carte"
    r"|r[eè]glement\s+carte|pr[eé]l[eè]vement\s+carte"
    r"|vos\s+paiements\s+carte|arr[eê]t[eé]\s+carte"
    r"|d[eé]penses\s+carte)",
    re.IGNORECASE,
)
_RE_DATE    = re.compile(r"\d{2}")
_RE_MONTANT = re.compile(r"[\d\s]+[.,]\d{2}\s*€?\s*$")
_RE_LIGNE_PARASITE = re.compile(
    r"""(
        \btotal\b
      | \bfrais\b
      | \bautorisation\b
      | \bd[eé]couvert\b
      | \bfacilit[eé]\b
      | \btaeg\b
      | \bp[eé]riode\b
      | \bn[°º]\s*de\s*compte\b
      | \bproduits\s+et\s+services\b
      | \br[eé]capitulatif\b
      | \bsolde\s+(au|du|de|initial|final)\b
      | \breport[eé]?\b
      | \bancien\s+solde\b
      | \bnouveau\s+solde\b
      | \bmontant\s+pr[eé]lev[eé]\b
      | ^ref\s+vir\b
      | ^[A-Z]{2}\d{2}[A-Z0-9]{10,}
    )""",
    re.IGNORECASE | re.VERBOSE,
)
_RE_VRAIE_DATE = re.compile(
    r"""(
        \d{1,2}[/\.\-]\d{1,2}([/\.\-]\d{2,4})?
      | \d{1,2}\s+(jan|f[eé]v|mar|avr|mai|juin|juil|ao[uû]|sep|oct|nov|d[eé]c)
    )""",
    re.IGNORECASE | re.VERBOSE,
)


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACTION PDF
# ══════════════════════════════════════════════════════════════════════════════
def _tableau_est_un_releve(table: list) -> bool:
    if not table or len(table) < 2:
        return False
    nb_cols = max(len(r) for r in table if r)
    if nb_cols < 4:
        return False
    header = None
    for row in table[:3]:
        cells = [str(c or "").lower().strip() for c in row]
        if any(c in _ENTETES_DATE for c in cells):
            header = cells
            break
    if header is not None:
        return any(c in _ENTETES_DATE for c in header) and any(c in _ENTETES_MONTANT for c in header)
    lignes_data = [r for r in table if r and len(r) >= 3]
    if not lignes_data:
        return False
    score = sum(
        1 for row in lignes_data
        if bool(_RE_DATE.search(str(row[0] or "").strip())) and len(str(row[0] or "").strip()) <= 20
        and any(bool(_RE_MONTANT.search(str(c or ""))) for c in row)
    )
    return (score / len(lignes_data)) >= 0.30

def _detecter_colonnes(header_row: list):
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
        if c in _DATE_KEYS    and idx_date is None: idx_date = i
        elif c in _LIBELLE_KEYS and idx_lib  is None: idx_lib  = i
        elif c in _DEBIT_KEYS   and idx_deb  is None: idx_deb  = i
        elif c in _CREDIT_KEYS  and idx_cred is None: idx_cred = i
    if idx_deb is not None and idx_cred is None and idx_deb + 1 < len(header_row):
        idx_cred = idx_deb + 1
    if idx_date is None or idx_lib is None or idx_deb is None:
        return None
    return (idx_date, idx_lib, idx_deb, idx_cred)

def _parse_montant(cell) -> float:
    s = re.sub(r"[^\d,.]", "", str(cell or "").strip())
    if not s: return 0.0
    if "," in s and "." in s: s = s.replace(".", "").replace(",", ".")
    elif "," in s: s = s.replace(",", ".")
    try: return float(s)
    except ValueError: return 0.0

def _fusionner_lignes(table, idx_date, idx_lib, idx_deb, idx_cred, header_idx):
    fusionnees = []
    for ri, row in enumerate(table):
        if ri <= header_idx: continue
        if not row or len(row) <= max(c for c in (idx_date, idx_lib, idx_deb, idx_cred) if c is not None):
            continue
        date_cell  = str(row[idx_date] or "").strip()
        lib_cell   = str(row[idx_lib]  or "").strip().replace("\n", " ")
        deb_cell   = str(row[idx_deb]  or "").strip()
        cred_cell  = str(row[idx_cred] or "").strip() if idx_cred is not None else ""
        est_continuation = not date_cell and lib_cell and not deb_cell and not cred_cell
        if est_continuation and fusionnees:
            if not _RE_LIGNE_PARASITE.search(lib_cell):
                fusionnees[-1]["libelle_suite"] = (
                    fusionnees[-1].get("libelle_suite", "") + " " + lib_cell
                ).strip()
        else:
            fusionnees.append({
                "date": date_cell, "libelle": lib_cell,
                "debit_cell": deb_cell, "credit_cell": cred_cell,
                "libelle_suite": "",
            })
    return fusionnees

def extraire_donnees_pdf(file_path: str) -> pd.DataFrame:
    rows = []
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                for table in (page.extract_tables() or []):
                    if not _tableau_est_un_releve(table): continue
                    cols = None; header_idx = 0
                    for hi, row in enumerate(table[:3]):
                        cols = _detecter_colonnes(row)
                        if cols: header_idx = hi; break
                    if not cols: cols = (0, 2, 3, 4)
                    idx_date, idx_lib, idx_deb, idx_cred = cols
                    lignes = _fusionner_lignes(table, idx_date, idx_lib, idx_deb, idx_cred, header_idx)
                    for ligne in lignes:
                        date    = ligne["date"]
                        suite   = ligne["libelle_suite"]
                        libelle = (ligne["libelle"] + (" " + suite if suite else "")).strip()
                        if not date or not libelle: continue
                        if not _RE_VRAIE_DATE.search(date): continue
                        if libelle.lower().strip() in _ENTETES: continue
                        if _RE_PRLV_CARTE.search(libelle): continue
                        if _RE_LIGNE_PARASITE.search(libelle): continue
                        debit  = _parse_montant(ligne["debit_cell"])
                        credit = _parse_montant(ligne["credit_cell"])
                        rows.append({"Date": date, "Libellé": libelle, "Débit": debit, "Crédit": credit})
    except Exception as e:
        st.error(f"Erreur extraction {os.path.basename(file_path)} : {e}")
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
# CATÉGORISATION
# ══════════════════════════════════════════════════════════════════════════════
_TOKENS_GENERIQUES = re.compile(
    r"""^(
        virement | vir | inst | sepa | prlv | pr[eé]l[eè]vement
      | paiement | psc | tpe | cb | chq | ch[eè]que | ech | cotis
      | r[eè]glement | r[eé]gl | fact | facture
      | carte | vers | de | du | le | la | les | au | aux | et | ou | par | sur
      | m | mr | mme | ag | gestion | [eé]ch[eé]ance | [eé]ch[eé]ances
    )$""",
    re.IGNORECASE | re.VERBOSE,
)
_RE_TOKEN_BRUIT = re.compile(
    r"""(
        \d{2}[/.]\d{2,4} | \d{4,} | ^-$
      | \bIBAN\b | \bBIC\b | \bREF\b
      | \bCONTRAT\b | \bECHEANCE\b | \bCOTISATION\b | \bPERIODIQUE\b
      | \bCORE\b | ^FR\d{2} | \*\* | ^[A-Z]{2,4}-\d+$ | ^[A-Z]\d{2,}
    )""",
    re.IGNORECASE | re.VERBOSE,
)

def _extraire_tronc(libelle: str, max_mots_utiles: int = 3) -> str:
    tokens = libelle.split()
    mots_utiles = []
    for tok in tokens:
        if _RE_TOKEN_BRUIT.search(tok) or tok == "-": continue
        if _TOKENS_GENERIQUES.match(tok): continue
        mots_utiles.append(tok)
        if len(mots_utiles) >= max_mots_utiles: break
    return " ".join(mots_utiles) if mots_utiles else ""

_RE_CHEQUE = re.compile(r"^\s*ch[eè]que\s+\d+\s*$", re.IGNORECASE)

def _est_cheque(libelle: str) -> bool:
    return bool(_RE_CHEQUE.match(libelle.strip()))

def _est_virement_opaque(libelle: str) -> bool:
    """Virement dont le tronc distinctif est vide — traité manuellement comme un chèque."""
    lib = libelle.strip()
    if not re.match(r"^(vir(ement)?\s)", lib, re.IGNORECASE):
        return False
    tronc = _extraire_tronc(lib)
    return not tronc or len(tronc) <= 3

def categoriser(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Catégorie"] = "À catégoriser"

    # Détecter chèques et virements opaques AVANT toute règle automatique
    masque_cheque = df["Libellé"].str.strip().apply(_est_cheque)
    masque_vir_op = df["Libellé"].str.strip().apply(_est_virement_opaque)
    masque_manuel = masque_cheque | masque_vir_op

    df.loc[masque_cheque, "Catégorie"] = "À catégoriser (chèque)"
    df.loc[masque_vir_op, "Catégorie"] = "À catégoriser (virement)"

    # Appliquer le registre des opérations déjà connues
    cheques_connus = st.session_state.get("cheques_connus", {})
    for idx, row in df[masque_manuel].iterrows():
        cle = _cle_cheque(row["Date"], row["Libellé"])
        if cle in cheques_connus:
            df.at[idx, "Catégorie"] = cheques_connus[cle]["categorie"]

    # Appliquer les mots-clés sur les lignes NON manuelles uniquement
    for cat, mots in st.session_state["categories"].items():
        for mot in mots:
            mask = (
                df["Libellé"].str.contains(re.escape(mot), case=False, na=False)
                & ~masque_manuel
            )
            df.loc[mask, "Catégorie"] = cat

    return df

def appliquer_categorisation():
    if st.session_state["combined_df"] is not None:
        df = st.session_state["combined_df"].drop(columns=["Catégorie"], errors="ignore")
        st.session_state["combined_df"] = categoriser(df)

def _sauvegarder_csv_si_complet():
    """Sauvegarde le CSV si tout est catégorisé et la période est connue."""
    df = st.session_state.get("combined_df")
    if df is None: return
    cats_incompletes = {"À catégoriser", "À catégoriser (chèque)", "À catégoriser (virement)"}
    if df["Catégorie"].isin(cats_incompletes).any(): return
    f_annees = st.session_state.get("_annees_sel", [])
    f_mois   = st.session_state.get("_mois_sel", [])
    if len(f_annees) == 1 and len(f_mois) == 1:
        sauvegarder_csv(f_annees[0], f_mois[0])
        return True
    return False


# ══════════════════════════════════════════════════════════════════════════════
# GRAPHIQUES
# ══════════════════════════════════════════════════════════════════════════════
def _palette_cat(categories: list) -> dict:
    cats_triees = sorted(set(categories), key=str.lower)
    return {c: PALETTE[i % len(PALETTE)] for i, c in enumerate(cats_triees)}

def graphique_pie(data: pd.Series, titre: str, palette: dict):
    data = data[data > 0]
    if data.empty:
        st.info("Aucune donnée.")
        return
    fig = px.pie(
        values=data.values, names=data.index, title=titre,
        color=data.index, color_discrete_map=palette, hole=0.35,
    )
    fig.update_traces(
        textposition="inside", textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>%{value:,.2f} €<br>%{percent}<extra></extra>",
    )
    fig.update_layout(
        showlegend=True, legend=dict(orientation="v", x=1.02, y=0.5),
        margin=dict(t=50, b=20, l=20, r=140),
    )
    st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# FORMULAIRES
# ══════════════════════════════════════════════════════════════════════════════
def form_ajouter_compte(container):
    banques = st.session_state["banques"]
    with container:
        st.markdown("#### 🏷️ Intitulé du compte")
        intitule = st.text_input(
            "Intitulé personnalisé *",
            placeholder="Ex : Compte courant principal, Compte joint, Livret A…",
            key="_f_intitule",
        )
        st.divider()
        st.markdown("#### 🏦 Établissement bancaire")
        st.write("**Option 1 — Choisir dans la liste**")
        col1, col2 = st.columns(2)
        with col1:
            banque_sel = st.selectbox("Banque", [""] + sorted(banques.keys(), key=str.lower), key="_f_banque")
        with col2:
            caisses = sorted(banques.get(banque_sel, []), key=str.lower) if banque_sel else []
            caisse_sel = st.selectbox("Caisse locale", [""] + caisses, key="_f_caisse")
        st.write("**Option 2 — Saisie libre**")
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
                st.warning("L'intitulé est obligatoire.")
                return
            if not banque_f or not caisse_f:
                st.warning("Veuillez renseigner banque et caisse.")
                return
            if intitule_f in [c["intitule"] for c in st.session_state["comptes"]]:
                st.warning(f"Un compte « {intitule_f} » existe déjà.")
                return
            nouveau = {"intitule": intitule_f, "banque": banque_f, "caisse": caisse_f}
            st.session_state["comptes"].append(nouveau)
            st.session_state["comptes"] = sorted(st.session_state["comptes"], key=lambda c: c["intitule"].lower())
            if banque_libre.strip() and banque_libre.strip() not in banques:
                st.session_state["banques"][banque_libre.strip()] = [caisse_libre.strip() or "National"]
            st.session_state["banques"] = dict(sorted(st.session_state["banques"].items(), key=lambda x: x[0].lower()))
            sauvegarder_comptes()
            st.success(f"Compte « {intitule_f} » ajouté !")
            st.rerun()

def form_categories(container):
    cats = st.session_state["categories"]
    with container:
        action = st.radio("Action", ["➕ Ajouter", "✏️ Modifier", "🗑️ Supprimer"], horizontal=True, key="_fc_action")
        if action == "➕ Ajouter":
            new_name = st.text_input("Nom", key="_fc_new_name")
            new_mots = st.text_input("Mots-clés (virgules)", key="_fc_new_mots")
            if st.button("✅ Ajouter", key="_fc_add"):
                nom = new_name.strip()
                if not nom: st.warning("Nom requis.")
                elif nom in cats: st.warning("Existe déjà.")
                else:
                    cats[nom] = [m.strip().upper() for m in new_mots.split(",") if m.strip()]
                    sauvegarder_categories(); appliquer_categorisation()
                    st.success(f"« {nom} » ajoutée."); st.rerun()
        elif action == "✏️ Modifier":
            cat_sel  = st.selectbox("Catégorie", sorted(cats.keys(), key=str.lower), key="_fc_edit_sel")
            new_mots = st.text_input("Mots-clés", value=", ".join(cats.get(cat_sel, [])), key="_fc_edit_mots")
            new_name = st.text_input("Renommer (vide = garder)", key="_fc_rename")
            if st.button("✅ Enregistrer", key="_fc_save"):
                mots_list = [m.strip().upper() for m in new_mots.split(",") if m.strip()]
                nom_final = new_name.strip() or cat_sel
                if nom_final != cat_sel: del cats[cat_sel]
                cats[nom_final] = mots_list
                sauvegarder_categories(); appliquer_categorisation()
                st.success("Mis à jour."); st.rerun()
        elif action == "🗑️ Supprimer":
            cat_sel = st.selectbox("Catégorie", sorted(cats.keys(), key=str.lower), key="_fc_del_sel")
            st.warning(f"« {cat_sel} » → « À catégoriser ».")
            if st.button("🗑️ Confirmer", key="_fc_del", type="primary"):
                del cats[cat_sel]; sauvegarder_categories(); appliquer_categorisation()
                st.success(f"« {cat_sel} » supprimée."); st.rerun()
        st.divider()
        st.markdown("#### ♻️ Réinitialiser")
        if st.checkbox("Je confirme", key="_fc_confirm_reset"):
            if st.button("♻️ Réinitialiser", key="_fc_reset", type="primary"):
                st.session_state["categories"] = dict(CATEGORIES_DEFAUT)
                sauvegarder_categories(); appliquer_categorisation()
                st.success("Réinitialisé."); st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# LAYOUT
# ══════════════════════════════════════════════════════════════════════════════
st.title("🏦 Analyse de Relevés Bancaires")

_TAB_INDEX = {"comptes": 0, "fichiers": 1, "categorisation": 2, "analyse": 3, "regles": 4}
_goto = st.session_state.pop("_goto_tab", None)

tab_comptes, tab_fichiers, tab_categories, tab_analyse, tab_regles = st.tabs([
    "📋 Comptes", "📁 Fichiers", "🏷️ Catégorisation", "📊 Analyse", "⚙️ Règles",
])

if _goto in _TAB_INDEX:
    idx = _TAB_INDEX[_goto]
    st.components.v1.html(f"""
        <script>
        function switchTab() {{
            const tabs = window.parent.document.querySelectorAll('[data-baseweb="tab"]');
            if (tabs.length > {idx}) {{ tabs[{idx}].click(); }}
            else {{ setTimeout(switchTab, 100); }}
        }}
        setTimeout(switchTab, 200);
        </script>
    """, height=0)


# ─────────────────────────────────────────────
# ONGLET 1 — Comptes
# ─────────────────────────────────────────────
with tab_comptes:
    st.subheader("Comptes bancaires enregistrés")
    comptes = st.session_state["comptes"]
    if comptes:
        st.dataframe(pd.DataFrame([{
            "#": i+1, "Intitulé": c["intitule"], "Banque": c["banque"], "Caisse": c["caisse"],
        } for i, c in enumerate(comptes)]), use_container_width=True, hide_index=True)
        with st.expander("🗑️ Supprimer un compte"):
            options_del = [label_compte(c) for c in comptes]
            label_del   = st.selectbox("Compte", options_del, key="del_compte_sel")
            idx_del     = options_del.index(label_del)
            if st.button("Supprimer", key="btn_del_compte", type="primary"):
                st.session_state["comptes"].pop(idx_del)
                sauvegarder_comptes(); st.rerun()
    else:
        st.info("Aucun compte. Ajoutez-en un ci-dessous.")

    _KEYS_FORM = ["_f_intitule", "_f_banque", "_f_caisse", "_f_banque_libre", "_f_caisse_libre"]
    if st.button("➕ Ajouter un compte bancaire", key="btn_toggle_add_compte"):
        for k in _KEYS_FORM:
            if k in st.session_state: del st.session_state[k]
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
        st.warning("Ajoutez d'abord des comptes.")
        st.stop()

    labels_comptes = [label_compte(c) for c in comptes]
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        labels_sel = st.multiselect("Comptes", labels_comptes, default=labels_comptes, key="f_comptes")
    with col_b:
        annees_sel = st.multiselect("Années", ["2024", "2025", "2026"], default=["2026"], key="f_annees")
    with col_c:
        mois_sel = st.multiselect("Mois", MOIS, default=["janvier"], key="f_mois")

    if not (labels_sel and annees_sel and mois_sel):
        st.info("Sélectionnez au moins un compte, une année et un mois.")
        st.stop()

    comptes_sel   = [c for c in comptes if label_compte(c) in labels_sel]
    total_attendu = len(comptes_sel) * len(annees_sel) * len(mois_sel)
    fichiers_ok   = []

    for compte in comptes_sel:
        for annee in annees_sel:
            for mois in mois_sel:
                safe    = re.sub(r"_+", "_", re.sub(r"[^\w]", "_", compte["intitule"])).strip("_")
                nom     = f"{safe}_{mois}_{annee}.pdf"
                dossier = os.path.join(PDF_BASE_PATH, annee, mois)
                chemin  = os.path.join(dossier, nom)
                os.makedirs(dossier, exist_ok=True)
                if os.path.exists(chemin):
                    st.success(f"✅ {nom} trouvé.")
                    fichiers_ok.append(chemin)
                else:
                    st.warning(f"❌ {nom} manquant.")
                    up = st.file_uploader(f"PDF — {label_compte(compte)} / {mois} {annee}",
                                          type="pdf", key=f"up_{compte['intitule']}_{mois}_{annee}")
                    if up:
                        with open(chemin, "wb") as fh: fh.write(up.getbuffer())
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
            periode_unique = len(annees_sel) == 1 and len(mois_sel) == 1
            with st.spinner("Chargement en cours…"):
                for path in fichiers_ok:
                    nom_source    = os.path.basename(path)
                    df_depuis_csv = None
                    if periode_unique:
                        df_csv = charger_csv(annees_sel[0], mois_sel[0])
                        if df_csv is not None and "Source" in df_csv.columns:
                            df_src = df_csv[df_csv["Source"] == nom_source].copy()
                            if not df_src.empty:
                                df_src = df_src.drop(columns=["Catégorie"], errors="ignore")
                                df_depuis_csv = df_src
                                st.caption(f"💾 {nom_source} → rechargé depuis le CSV")
                    if df_depuis_csv is not None:
                        dfs.append(df_depuis_csv)
                    else:
                        df_tmp = extraire_donnees_pdf(path)
                        if not df_tmp.empty:
                            df_tmp["Source"] = nom_source
                            dfs.append(df_tmp)
                            st.caption(f"📄 {nom_source} → extrait depuis le PDF")

            if dfs:
                consolidated = pd.concat(dfs, ignore_index=True)
                df_cat = categoriser(consolidated)
                st.session_state["combined_df"] = df_cat
                st.session_state["_annees_sel"] = annees_sel
                st.session_state["_mois_sel"]   = mois_sel

                cats_incompletes = {"À catégoriser", "À catégoriser (chèque)", "À catégoriser (virement)"}
                nb_a_cat = df_cat["Catégorie"].isin(cats_incompletes).sum()
                if nb_a_cat == 0:
                    st.session_state["_goto_tab"] = "analyse"
                    st.success(f"✅ {len(consolidated)} transactions — tout est catégorisé !")
                else:
                    st.session_state["_goto_tab"] = "categorisation"
                    st.success(f"✅ {len(consolidated)} transactions chargées.")
                    st.warning(f"👉 {nb_a_cat} transaction(s) à catégoriser.")
                st.rerun()
            else:
                st.error("Aucune donnée extraite.")


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

    # ── Virements opaques ────────────────────────────────────────────────────
    vir_opaques = df[df["Catégorie"] == "À catégoriser (virement)"].copy()
    if not vir_opaques.empty:
        st.subheader(f"❓ Virements non identifiés — {len(vir_opaques)} virement(s)")
        st.warning("Ces virements ne contiennent pas assez d'information. Indiquez leur objet.")
        cats_dispo_vir = sorted(st.session_state["categories"].keys(), key=str.lower)
        assign_vir = {}
        for _, row_vir in vir_opaques.iterrows():
            c1, c2, c3, c4 = st.columns([2, 1, 2, 3])
            with c1: st.write(f"❓ **{row_vir['Libellé']}**")
            with c2:
                sens = "💸" if row_vir["Débit"] > 0 else "💰"
                montant = row_vir["Débit"] if row_vir["Débit"] > 0 else row_vir["Crédit"]
                st.caption(f"{sens} {montant:,.2f} €")
            with c3: st.caption(f"Date : {row_vir['Date']}")
            with c4:
                choix_vir = st.selectbox("cat", ["— Choisir —"] + cats_dispo_vir + ["➕ Nouvelle catégorie…"],
                                         key=f"vir_{row_vir.name}", label_visibility="collapsed")
                if choix_vir == "➕ Nouvelle catégorie…":
                    nv = st.text_input("Nom", key=f"new_vir_{row_vir.name}", label_visibility="collapsed")
                    if nv.strip(): assign_vir[row_vir.name] = ("new", nv.strip())
                elif choix_vir != "— Choisir —":
                    assign_vir[row_vir.name] = ("existing", choix_vir)

        if st.button("✅ Valider les virements", key="btn_valider_vir"):
            cats = st.session_state["categories"]
            chq_connus = st.session_state["cheques_connus"]
            for idx_vir, (kind, valeur) in assign_vir.items():
                if kind == "new" and valeur not in cats: cats[valeur] = []
                row_data = st.session_state["combined_df"].loc[idx_vir]
                cle = _cle_cheque(row_data["Date"], row_data["Libellé"])
                chq_connus[cle] = {"categorie": valeur, "libelle": row_data["Libellé"],
                                   "date": row_data["Date"],
                                   "montant": float(row_data["Débit"] or row_data["Crédit"])}
                st.session_state["combined_df"].loc[idx_vir, "Catégorie"] = valeur
            if assign_vir:
                sauvegarder_categories(); sauvegarder_cheques()
                csv_ok = _sauvegarder_csv_si_complet()
                st.success(f"{len(assign_vir)} virement(s) catégorisé(s)." + (" CSV sauvegardé ✅" if csv_ok else ""))
                st.rerun()
        st.divider()

    # ── Chèques ──────────────────────────────────────────────────────────────
    cheques = df[df["Catégorie"] == "À catégoriser (chèque)"].copy()
    if not cheques.empty:
        st.subheader(f"🏦 Chèques — {len(cheques)} chèque(s)")
        st.warning("Les chèques ne peuvent pas être catégorisés automatiquement.")
        cats_dispo_chq = sorted(st.session_state["categories"].keys(), key=str.lower)
        assign_chq = {}
        for _, row_chq in cheques.iterrows():
            c1, c2, c3, c4 = st.columns([2, 1, 2, 3])
            with c1: st.write(f"🟠 **{row_chq['Libellé']}**")
            with c2:
                sens = "💸" if row_chq["Débit"] > 0 else "💰"
                montant = row_chq["Débit"] if row_chq["Débit"] > 0 else row_chq["Crédit"]
                st.caption(f"{sens} {montant:,.2f} €")
            with c3: st.caption(f"Date : {row_chq['Date']}")
            with c4:
                choix_chq = st.selectbox("cat", ["— Choisir —"] + cats_dispo_chq + ["➕ Nouvelle catégorie…"],
                                         key=f"chq_{row_chq.name}", label_visibility="collapsed")
                if choix_chq == "➕ Nouvelle catégorie…":
                    nc = st.text_input("Nom", key=f"new_chq_{row_chq.name}", label_visibility="collapsed")
                    if nc.strip(): assign_chq[row_chq.name] = ("new", nc.strip())
                elif choix_chq != "— Choisir —":
                    assign_chq[row_chq.name] = ("existing", choix_chq)

        if st.button("✅ Valider les chèques", key="btn_valider_chq"):
            cats = st.session_state["categories"]
            chq_connus = st.session_state["cheques_connus"]
            for idx_chq, (kind, valeur) in assign_chq.items():
                if kind == "new" and valeur not in cats: cats[valeur] = []
                row_data = st.session_state["combined_df"].loc[idx_chq]
                cle = _cle_cheque(row_data["Date"], row_data["Libellé"])
                chq_connus[cle] = {"categorie": valeur, "libelle": row_data["Libellé"],
                                   "date": row_data["Date"],
                                   "montant": float(row_data["Débit"] or row_data["Crédit"])}
                st.session_state["combined_df"].loc[idx_chq, "Catégorie"] = valeur
            if assign_chq:
                sauvegarder_categories(); sauvegarder_cheques()
                csv_ok = _sauvegarder_csv_si_complet()
                st.success(f"{len(assign_chq)} chèque(s) catégorisé(s)." + (" CSV sauvegardé ✅" if csv_ok else ""))
                st.rerun()
        st.divider()

    # ── Transactions non catégorisées ────────────────────────────────────────
    non_cat = df[df["Catégorie"] == "À catégoriser"].copy()
    st.subheader(f"Transactions à catégoriser — {len(non_cat)} libellé(s)")

    if non_cat.empty and cheques.empty and vir_opaques.empty:
        st.success("✅ Toutes les transactions sont catégorisées.")
    elif non_cat.empty:
        st.success("✅ Tous les libellés auto sont catégorisés.")
    else:
        resume = (
            non_cat.groupby("Libellé")
                   .agg(Occurrences=("Libellé","count"), Total_Débit=("Débit","sum"), Total_Crédit=("Crédit","sum"))
                   .reset_index().sort_values("Libellé")
        )
        st.info(f"{len(resume)} libellé(s) — validez ligne par ligne.")
        st.caption("💡 Chaque validation est immédiate.")
        st.divider()

        for _, rr in resume.iterrows():
            libelle = rr["Libellé"]
            occ     = int(rr["Occurrences"])
            t_deb   = rr["Total_Débit"]
            t_cred  = rr["Total_Crédit"]
            if t_deb > 0 and t_cred == 0:
                sens = "💸 Sortie"; montant = f"−{t_deb:,.2f} €"; icone = "🔴"
            elif t_cred > 0 and t_deb == 0:
                sens = "💰 Entrée"; montant = f"+{t_cred:,.2f} €"; icone = "🟢"
            else:
                sens = "↔️ Mixte"; montant = f"D:{t_deb:,.2f} € / C:{t_cred:,.2f} €"; icone = "🟡"

            cats_live = sorted(st.session_state["categories"].keys(), key=str.lower)
            with st.container(border=True):
                col_info, col_cat = st.columns([3, 4])
                with col_info:
                    st.write(f"{icone} **{libelle}**")
                    st.caption(f"{occ} occurrence(s) · {sens} · {montant}")
                with col_cat:
                    choix = st.selectbox("Catégorie",
                                         ["— Choisir —"] + cats_live + ["➕ Nouvelle catégorie…"],
                                         key=f"sel_{libelle}", label_visibility="collapsed")
                    if choix == "➕ Nouvelle catégorie…":
                        nouvelle = st.text_input("Nom", key=f"new_{libelle}",
                                                  placeholder="Ex : Santé…", label_visibility="collapsed")
                        cat_choisie  = nouvelle.strip() if nouvelle.strip() else None
                        est_nouvelle = True
                    elif choix != "— Choisir —":
                        cat_choisie  = choix
                        est_nouvelle = False
                    else:
                        cat_choisie = None; est_nouvelle = False

                    if cat_choisie:
                        tronc   = _extraire_tronc(libelle)
                        mot_cle = st.text_input("🔑 Mot-clé mémorisé", value=tronc,
                                                 key=f"motcle_{libelle}",
                                                 help="Raccourcissez si besoin (ex : Netflix).")
                        if st.button("✅ Valider", key=f"btn_val_{libelle}"):
                            cats = st.session_state["categories"]
                            if est_nouvelle and cat_choisie not in cats:
                                cats[cat_choisie] = []
                            mot_cle_final = (mot_cle.strip() or tronc).upper()
                            if mot_cle_final and mot_cle_final not in [m.upper() for m in cats.get(cat_choisie, [])]:
                                cats.setdefault(cat_choisie, []).append(mot_cle_final)
                            appliquer_categorisation()
                            st.session_state["combined_df"].loc[
                                st.session_state["combined_df"]["Libellé"] == libelle, "Catégorie"
                            ] = cat_choisie
                            sauvegarder_categories()
                            csv_ok = _sauvegarder_csv_si_complet()
                            if csv_ok:
                                st.session_state["_goto_tab"] = "analyse"
                                st.success("✅ Tout catégorisé ! CSV sauvegardé.")
                            st.rerun()


# ─────────────────────────────────────────────
# ONGLET 4 — Analyse
# ─────────────────────────────────────────────
with tab_analyse:
    st.subheader("📊 Analyse des flux financiers")
    df = st.session_state.get("combined_df")
    if df is None:
        st.info("Extrayez d'abord les données.")
        st.stop()

    total_sorties = df["Débit"].sum()
    total_entrees = df["Crédit"].sum()
    solde_net     = total_entrees - total_sorties
    m1, m2, m3 = st.columns(3)
    m1.metric("💸 Total sorties", f"{total_sorties:,.2f} €")
    m2.metric("💰 Total entrées", f"{total_entrees:,.2f} €")
    m3.metric("📊 Solde net", f"{solde_net:,.2f} €", delta=f"{solde_net:+,.2f} €", delta_color="normal")
    st.divider()

    rapport = (
        df.groupby("Catégorie")
          .agg(Sorties=("Débit","sum"), Entrées=("Crédit","sum"))
          .assign(Solde=lambda x: x["Entrées"] - x["Sorties"])
          .sort_index()
    )
    with st.expander("📋 Tableau récapitulatif", expanded=True):
        st.dataframe(
            rapport.style
                   .format({"Sorties": "{:,.2f} €", "Entrées": "{:,.2f} €", "Solde": "{:,.2f} €"})
                   .background_gradient(subset=["Solde"], cmap="RdYlGn"),
            use_container_width=True,
        )
    st.divider()

    palette = _palette_cat(rapport.index.tolist())
    col_g, col_d = st.columns(2)
    with col_g:
        st.markdown("### 💸 Sorties par catégorie")
        graphique_pie(rapport["Sorties"], "Sorties", palette)
    with col_d:
        st.markdown("### 💰 Entrées par catégorie")
        graphique_pie(rapport["Entrées"], "Entrées", palette)
    st.divider()

    st.markdown("### 🔍 Détail d'une catégorie")
    cat_detail = st.selectbox("Catégorie", sorted(df["Catégorie"].unique().tolist(), key=str.lower), key="detail_cat_sel")
    df_detail = df[df["Catégorie"] == cat_detail][["Date","Libellé","Débit","Crédit","Source"]].copy().sort_values("Date")
    d1, d2, d3 = st.columns(3)
    d1.metric("Nb transactions", len(df_detail))
    d2.metric("Total sorties",   f"{df_detail['Débit'].sum():,.2f} €")
    d3.metric("Total entrées",   f"{df_detail['Crédit'].sum():,.2f} €")
    st.dataframe(df_detail.style.format({"Débit": "{:,.2f} €", "Crédit": "{:,.2f} €"}),
                 use_container_width=True, hide_index=True)
    csv_detail = df_detail.to_csv(index=False, sep=";").encode("utf-8-sig")
    st.download_button(f"⬇️ Détail « {cat_detail} »", data=csv_detail,
                       file_name=f"detail_{cat_detail.replace(' ','_')}.csv", mime="text/csv", key="dl_detail")
    st.divider()
    csv = df.to_csv(index=False, sep=";").encode("utf-8-sig")
    st.download_button("⬇️ Toutes les transactions", data=csv,
                       file_name="transactions_categoriees.csv", mime="text/csv")


# ─────────────────────────────────────────────
# ONGLET 5 — Règles
# ─────────────────────────────────────────────
with tab_regles:
    st.subheader("⚙️ Gestion des catégories et mots-clés")
    cats = st.session_state["categories"]

    st.markdown("### 📋 Vue d'ensemble")
    if cats:
        st.dataframe(pd.DataFrame([{
            "Catégorie": cat, "Nb mots-clés": len(mots),
            "Mots-clés": ", ".join(mots) if mots else "— aucun",
        } for cat, mots in sorted(cats.items(), key=lambda x: x[0].lower())]),
            use_container_width=True, hide_index=True,
            column_config={"Catégorie": st.column_config.TextColumn(width="medium"),
                           "Nb mots-clés": st.column_config.NumberColumn(width="small"),
                           "Mots-clés": st.column_config.TextColumn(width="large")})
    st.divider()

    col_act1, col_act2, col_act3 = st.columns(3)
    with col_act1:
        with st.container(border=True):
            st.markdown("#### ➕ Nouvelle catégorie")
            new_cat_name = st.text_input("Nom", key="rg_new_name", placeholder="Ex : Santé")
            new_cat_mots = st.text_input("Mots-clés (virgules)", key="rg_new_mots", placeholder="pharmacie, médecin")
            if st.button("✅ Créer", key="rg_btn_create"):
                nom = new_cat_name.strip()
                if not nom: st.warning("Nom requis.")
                elif nom in cats: st.warning("Existe déjà.")
                else:
                    cats[nom] = [m.strip().upper() for m in new_cat_mots.split(",") if m.strip()]
                    sauvegarder_categories(); appliquer_categorisation()
                    st.success(f"« {nom} » créée."); st.rerun()

    with col_act2:
        with st.container(border=True):
            st.markdown("#### ✏️ Modifier")
            cat_edit = st.selectbox("Catégorie", sorted(cats.keys(), key=str.lower), key="rg_edit_sel")
            if cat_edit:
                new_edit_name = st.text_input("Renommer (vide = garder)", key="rg_edit_name", placeholder=cat_edit)
                new_edit_mots = st.text_area("Mots-clés (un par ligne)",
                                              value="\n".join(cats.get(cat_edit, [])),
                                              key="rg_edit_mots", height=120)
                if st.button("✅ Enregistrer", key="rg_btn_edit"):
                    raw = new_edit_mots.replace(",", "\n")
                    mots_list = [m.strip().upper() for m in raw.split("\n") if m.strip()]
                    nom_final = new_edit_name.strip() or cat_edit
                    if nom_final != cat_edit: del cats[cat_edit]
                    cats[nom_final] = mots_list
                    sauvegarder_categories(); appliquer_categorisation()
                    st.success("Enregistré."); st.rerun()

    with col_act3:
        with st.container(border=True):
            st.markdown("#### 🗑️ Supprimer")
            cat_del = st.selectbox("Catégorie", sorted(cats.keys(), key=str.lower), key="rg_del_sel")
            if cat_del:
                st.warning(f"Supprimera **{cat_del}** et ses {len(cats.get(cat_del,[]))} mot(s)-clé(s).")
                if st.checkbox("Je confirme", key="rg_del_confirm"):
                    if st.button("🗑️ Supprimer", key="rg_btn_del", type="primary"):
                        del cats[cat_del]; sauvegarder_categories(); appliquer_categorisation()
                        st.success(f"« {cat_del} » supprimée."); st.rerun()
    st.divider()

    st.markdown("### 🔑 Mots-clés détaillés")
    cat_detail_rg = st.selectbox("Catégorie", sorted(cats.keys(), key=str.lower), key="rg_detail_sel")
    if cat_detail_rg:
        mots = cats.get(cat_detail_rg, [])
        if mots:
            st.write(f"**{len(mots)} mot(s)-clé(s)**")
            st.columns([4,1])[0].markdown("**Mot-clé**")
            for i, mot in enumerate(mots):
                c_mot, c_del = st.columns([4,1])
                with c_mot: st.code(mot, language=None)
                with c_del:
                    if st.button("🗑️", key=f"rg_del_mot_{cat_detail_rg}_{i}", help=f"Supprimer « {mot} »"):
                        cats[cat_detail_rg].remove(mot)
                        sauvegarder_categories(); appliquer_categorisation(); st.rerun()
        else:
            st.info("Aucun mot-clé.")
        col_add1, col_add2 = st.columns([3,1])
        with col_add1:
            nouveau_mot = st.text_input("Ajouter", key="rg_new_mot", placeholder="Ex : LECLERC", label_visibility="collapsed")
        with col_add2:
            if st.button("➕ Ajouter", key="rg_btn_add_mot"):
                mot_clean = nouveau_mot.strip().upper()
                if not mot_clean: st.warning("Vide.")
                elif mot_clean in [m.upper() for m in cats.get(cat_detail_rg,[])]: st.warning("Existe déjà.")
                else:
                    cats.setdefault(cat_detail_rg, []).append(mot_clean)
                    sauvegarder_categories(); appliquer_categorisation()
                    st.success(f"« {mot_clean} » ajouté."); st.rerun()
    st.divider()

    st.markdown("### 🏦 Chèques et virements mémorisés")
    chq_connus = st.session_state.get("cheques_connus", {})
    if chq_connus:
        st.dataframe(pd.DataFrame([{
            "Date": info.get("date",""), "Libellé": info.get("libelle",""),
            "Montant": f"{info.get('montant',0):,.2f} €", "Catégorie": info.get("categorie",""),
        } for cle, info in sorted(chq_connus.items())]), use_container_width=True, hide_index=True)
        with st.expander("✏️ Corriger"):
            cles = list(chq_connus.keys())
            labels_cles = [f"{chq_connus[c]['date']} — {chq_connus[c]['libelle']} ({chq_connus[c]['montant']:.2f} €)" for c in cles]
            sel_label = st.selectbox("Opération", labels_cles, key="rg_chq_edit_sel")
            sel_cle   = cles[labels_cles.index(sel_label)]
            cats_list = sorted(cats.keys(), key=str.lower)
            cur_cat   = chq_connus[sel_cle]["categorie"]
            new_cat   = st.selectbox("Nouvelle catégorie", cats_list,
                                      index=cats_list.index(cur_cat) if cur_cat in cats_list else 0,
                                      key="rg_chq_new_cat")
            col_s, col_d = st.columns(2)
            with col_s:
                if st.button("✅ Corriger", key="rg_chq_save"):
                    chq_connus[sel_cle]["categorie"] = new_cat
                    sauvegarder_cheques(); appliquer_categorisation()
                    st.success("Mis à jour."); st.rerun()
            with col_d:
                if st.button("🗑️ Oublier", key="rg_chq_del"):
                    del chq_connus[sel_cle]; sauvegarder_cheques()
                    st.success("Supprimé."); st.rerun()
    else:
        st.info("Aucun chèque ou virement mémorisé.")
    st.divider()

    st.markdown("### ♻️ Réinitialiser toutes les catégories")
    st.caption("Remet les 8 catégories de base vides.")
    if st.checkbox("Je confirme", key="rg_confirm_reset"):
        if st.button("♻️ Réinitialiser", key="rg_btn_reset", type="primary"):
            st.session_state["categories"] = dict(CATEGORIES_DEFAUT)
            sauvegarder_categories(); appliquer_categorisation()
            st.success("Réinitialisé."); st.rerun()