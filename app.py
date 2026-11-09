import csv
import io
import sqlite3
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Test budget annuel", layout="wide")

BASE = Path(__file__).resolve().parent / "budget.sqlite3"


def connexion():
    return sqlite3.connect(BASE, timeout=15)


with connexion() as db:
    db.execute("""
        CREATE TABLE IF NOT EXISTS budget (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            annee INTEGER NOT NULL,
            categorie TEXT NOT NULL,
            libelle TEXT NOT NULL,
            montant_centimes INTEGER NOT NULL
                CHECK(montant_centimes >= 0),
            commentaire TEXT NOT NULL
        )
    """)


def convertir_montant(texte):
    texte = (
        texte.strip()
        .replace(" ", "")
        .replace("\u00a0", "")
        .replace("\u202f", "")
        .replace(",", ".")
    )
    try:
        montant = Decimal(texte)
        if not montant.is_finite() or montant < 0:
            raise ValueError("Le montant doit être positif ou nul.")
        if montant > Decimal("999999999999.99"):
            raise ValueError("Le montant est trop élevé.")
        if montant != montant.quantize(Decimal("0.01")):
            raise ValueError("Deux décimales maximum.")
        return int(montant * 100)
    except InvalidOperation:
        raise ValueError("Montant invalide. Exemple : 1250,50.")


def euros(centimes):
    return (
        f"{Decimal(centimes) / 100:,.2f}"
        .replace(",", " ")
        .replace(".", ",")
    )


st.title("Construction budgétaire annuelle")
st.warning(
    "DÉMONSTRATION : données fictives uniquement. "
    "Le stockage sur cet hébergement n'est pas garanti durable. "
    "Exportez vos essais en CSV pour les conserver."
)

if "confirmation" in st.session_state:
    st.success(st.session_state.pop("confirmation"))

with st.form("saisie"):
    annee = st.number_input(
        "Année", min_value=1900, max_value=2100,
        value=date.today().year, step=1
    )
    categorie = st.text_input("Catégorie", max_chars=120)
    libelle = st.text_input("Libellé", max_chars=250)
    montant = st.text_input(
        "Montant annuel en euros", placeholder="1250,50"
    )
    commentaire = st.text_area("Commentaire", max_chars=4000)

    if st.form_submit_button("Enregistrer", type="primary"):
        try:
            if not categorie.strip() or not libelle.strip():
                raise ValueError(
                    "La catégorie et le libellé sont obligatoires."
                )
            centimes = convertir_montant(montant)
        except ValueError as erreur:
            st.error(str(erreur))
        else:
            with connexion() as db:
                db.execute("""
                    INSERT INTO budget (
                        annee, categorie, libelle,
                        montant_centimes, commentaire
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    int(annee), categorie.strip(), libelle.strip(),
                    centimes, commentaire.strip()
                ))
            st.session_state["confirmation"] = "Ligne enregistrée."
            st.rerun()

st.caption("Chaque validation ajoute une nouvelle ligne.")
st.divider()
st.subheader("Budget enregistré")

with connexion() as db:
    annees = [
        r[0] for r in db.execute(
            "SELECT DISTINCT annee FROM budget ORDER BY annee DESC"
        )
    ]

filtre = st.selectbox("Année à consulter", ["Toutes"] + annees)

with connexion() as db:
    requete = """
        SELECT id, annee, categorie, libelle,
               montant_centimes, commentaire
        FROM budget
    """
    if filtre == "Toutes":
        lignes = db.execute(
            requete + " ORDER BY annee DESC, id DESC"
        ).fetchall()
    else:
        lignes = db.execute(
            requete + " WHERE annee = ? ORDER BY id DESC",
            (filtre,)
        ).fetchall()

a, b = st.columns(2)
a.metric("Nombre de lignes", len(lignes))
b.metric(
    "Total de la sélection",
    euros(sum(r[4] for r in lignes)) + " €"
)

entetes = [
    "ID", "Année", "Catégorie", "Libellé",
    "Montant EUR", "Commentaire"
]
donnees = [
    [r[0], r[1], r[2], r[3], euros(r[4]), r[5]]
    for r in lignes
]

if donnees:
    st.dataframe(
        [dict(zip(entetes, r)) for r in donnees],
        hide_index=True,
        use_container_width=True
    )

    def securiser(valeur):
        if (
            isinstance(valeur, str)
            and valeur.lstrip().startswith(("=", "+", "-", "@"))
        ):
            return "'" + valeur
        return valeur

    tampon = io.StringIO(newline="")
    export = csv.writer(tampon, delimiter=";")
    export.writerow(entetes)
    for ligne in donnees:
        export.writerow([securiser(v) for v in ligne])

    st.download_button(
        "Exporter en CSV pour Excel",
        tampon.getvalue().encode("utf-8-sig"),
        file_name="budget_test.csv",
        mime="text/csv"
    )
else:
    st.info("Aucune ligne : commencez par remplir le formulaire.")
