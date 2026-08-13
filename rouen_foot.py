import streamlit as st
import pandas as pd
import altair as alt
import json
import os
from datetime import date

# ----------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------
DATA_FILE = "data.json"
POINTS_VICTOIRE = 3
POINTS_NUL = 1
POINTS_DEFAITE = 0

st.set_page_config(page_title="Classement Foot", page_icon="⚽", layout="wide")


# ----------------------------------------------------------------
# Chargement / sauvegarde des données
# ----------------------------------------------------------------
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"joueurs": [], "matchs": []}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if "data" not in st.session_state:
    st.session_state.data = load_data()

data = st.session_state.data


# ----------------------------------------------------------------
# Calcul du classement
# ----------------------------------------------------------------
def calculer_classement(data, matchs=None):
    if matchs is None:
        matchs = data["matchs"]

    stats = {
        j: {"points": 0, "matchs_joues": 0, "victoires": 0, "nuls": 0}
        for j in data["joueurs"]
    }

    for match in matchs:
        if match["gagnant"] == "Nul":
            for joueur in match["equipe_a"] + match["equipe_b"]:
                if joueur in stats:
                    stats[joueur]["points"] += POINTS_NUL
                    stats[joueur]["matchs_joues"] += 1
                    stats[joueur]["nuls"] += 1
        else:
            gagnants = match["equipe_a"] if match["gagnant"] == "A" else match["equipe_b"]
            perdants = match["equipe_b"] if match["gagnant"] == "A" else match["equipe_a"]

            for joueur in gagnants:
                if joueur in stats:
                    stats[joueur]["points"] += POINTS_VICTOIRE
                    stats[joueur]["matchs_joues"] += 1
                    stats[joueur]["victoires"] += 1

            for joueur in perdants:
                if joueur in stats:
                    stats[joueur]["points"] += POINTS_DEFAITE
                    stats[joueur]["matchs_joues"] += 1

    lignes = []
    for joueur, s in stats.items():
        points_possibles = s["matchs_joues"] * POINTS_VICTOIRE
        pourcentage = (
            round(100 * s["points"] / points_possibles, 1)
            if points_possibles > 0
            else 0.0
        )
        lignes.append(
            {
                "Joueur": joueur,
                "Points": s["points"],
                "Matchs joués": s["matchs_joues"],
                "Victoires": s["victoires"],
                "Nuls": s["nuls"],
                "% Points": pourcentage,
            }
        )

    df = pd.DataFrame(lignes)
    if not df.empty:
        df = df.sort_values(by=["% Points", "Points"], ascending=False).reset_index(drop=True)
        df.index = df.index + 1
    return df


def ajouter_evolution(df_actuel, data, seuil=1):
    """Ajoute une colonne 'Évolution' comparant le rang actuel (dans le
    sous-ensemble filtré) au rang juste avant le dernier match enregistré,
    filtré de la même façon."""
    if not data["matchs"]:
        df_actuel["Évolution"] = "—"
        return df_actuel

    df_precedent = calculer_classement(data, data["matchs"][:-1])
    df_precedent = filtrer_et_reindexer(df_precedent, seuil)

    rang_actuel = {row["Joueur"]: idx for idx, row in df_actuel.iterrows()}
    rang_precedent = {row["Joueur"]: idx for idx, row in df_precedent.iterrows()}

    def format_evolution(joueur):
        if joueur not in rang_precedent:
            return "🆕"
        diff = rang_precedent[joueur] - rang_actuel[joueur]
        if diff > 0:
            return f"🔼 +{diff}"
        elif diff < 0:
            return f"🔽 {diff}"
        else:
            return "➖"

    df_actuel["Évolution"] = df_actuel["Joueur"].apply(format_evolution)
    return df_actuel


def filtrer_et_reindexer(df, seuil):
    """Ne garde que les joueurs ayant au moins `seuil` matchs joués,
    et recalcule le rang (1, 2, 3, ...) sur ce sous-ensemble."""
    df_f = df[df["Matchs joués"] >= seuil].reset_index(drop=True)
    df_f.index = df_f.index + 1
    return df_f


def historique_rangs(data, seuil=1):
    """Calcule, pour chaque match joué, le classement (filtré) de tous les
    joueurs à ce moment-là. Retourne un DataFrame long: Match / Joueur / Rang / Points."""
    lignes = []
    for i in range(1, len(data["matchs"]) + 1):
        df = calculer_classement(data, data["matchs"][:i])
        df = filtrer_et_reindexer(df, seuil)
        for rang, row in df.iterrows():
            lignes.append(
                {"Match": i, "Joueur": row["Joueur"], "Rang": rang, "Points": row["Points"]}
            )
    return pd.DataFrame(lignes)


def calculer_buteurs(data):
    buts_total = {j: 0 for j in data["joueurs"]}
    matchs_avec_but = {j: 0 for j in data["joueurs"]}

    for match in data["matchs"]:
        for joueur, nb in match.get("buteurs", {}).items():
            if joueur in buts_total and nb > 0:
                buts_total[joueur] += nb
                matchs_avec_but[joueur] += 1

    lignes = [
        {
            "Joueur": j,
            "Buts": b,
            "Buts/match": round(b / matchs_avec_but[j], 2) if matchs_avec_but[j] > 0 else 0.0,
        }
        for j, b in buts_total.items()
        if b > 0
    ]
    df = pd.DataFrame(lignes)
    if not df.empty:
        df = df.sort_values(by="Buts", ascending=False).reset_index(drop=True)
        df.index = df.index + 1
    return df


# ----------------------------------------------------------------
# Interface
# ----------------------------------------------------------------
st.markdown(
    """
    <style>
    .app-title {
        font-size: clamp(1.3rem, 4.5vw, 2.3rem);
        font-weight: 700;
        line-height: 1.25;
        margin-bottom: 0.75rem;
    }
    </style>
    <div class="app-title">⚽ Classement Foot - Le Five - Saison 2026-2027</div>
    """,
    unsafe_allow_html=True,
)

tab_classement, tab_match, tab_joueurs, tab_evolution, tab_buteurs = st.tabs(
    ["🏆 Classement", "🆕 Nouveau match", "👥 Joueurs", "📈 Évolution", "⚽ Buteurs"]
)

# ------------------------- Onglet Classement -------------------------
with tab_classement:
    st.subheader("Classement général")

    if not data["joueurs"]:
        st.info("Ajoute d'abord des joueurs dans l'onglet 👥 Joueurs.")
    else:
        filtre_classement = st.radio(
            "Afficher",
            options=["tous", "10+"],
            format_func=lambda x: "Tous ceux qui ont joué" if x == "tous" else "Joueurs ayant joué au moins 10 matchs",
            horizontal=True,
            key="filtre_classement",
        )
        seuil_classement = 1 if filtre_classement == "tous" else 10

        df_classement = calculer_classement(data)
        df_classement = filtrer_et_reindexer(df_classement, seuil_classement)

        if df_classement.empty:
            st.info("Aucun joueur ne remplit ce critère pour l'instant.")
        else:
            df_classement = ajouter_evolution(df_classement, data, seuil_classement)

            def style_evolution(val):
                if "🔼" in val:
                    return "color: #2e7d32; font-weight: bold"
                elif "🔽" in val:
                    return "color: #c62828; font-weight: bold"
                return ""

            vue_detaillee = st.checkbox("Afficher le détail (matchs joués, victoires, nuls)", value=False)

            if vue_detaillee:
                colonnes = ["Joueur", "Points", "Matchs joués", "Victoires", "Nuls", "% Points", "Évolution"]
            else:
                colonnes = ["Joueur", "Points", "% Points", "Évolution"]

            df_affiche = df_classement[colonnes]

            try:
                styled = df_affiche.style.map(style_evolution, subset=["Évolution"])
            except AttributeError:
                # Compatibilité avec les anciennes versions de pandas (< 2.1)
                styled = df_affiche.style.applymap(style_evolution, subset=["Évolution"])

            st.dataframe(
                styled,
                use_container_width=True,
                column_config={
                    "Points": st.column_config.NumberColumn("Pts"),
                    "Matchs joués": st.column_config.NumberColumn("MJ"),
                    "Victoires": st.column_config.NumberColumn("V"),
                    "Nuls": st.column_config.NumberColumn("N"),
                    "% Points": st.column_config.NumberColumn("%", format="%.0f %%"),
                    "Évolution": st.column_config.TextColumn("Évol."),
                },
            )
            st.caption("🔼 hausse · 🔽 baisse · ➖ stable · 🆕 nouveau — vs. avant le dernier match")

            st.divider()
            col1, col2, col3 = st.columns(3)
            leader = df_classement.iloc[0]
            col1.metric("🥇 Premier", leader["Joueur"], f"{leader['Points']} pts")
            col2.metric("Nombre de joueurs affichés", len(df_classement))
            col3.metric("Nombre de matchs", len(data["matchs"]))

# ------------------------- Onglet Nouveau match -------------------------
with tab_match:
    st.subheader("Enregistrer un nouveau match")

    if len(data["joueurs"]) < 2:
        st.info("Ajoute au moins 2 joueurs avant de créer un match.")
    else:
        match_date = st.date_input("Date du match", value=date.today())

        col_a, col_b = st.columns(2)
        with col_a:
            equipe_a = st.multiselect("Équipe A", options=data["joueurs"], key="eq_a")
        with col_b:
            equipe_b = st.multiselect("Équipe B", options=data["joueurs"], key="eq_b")

        # Vérification des doublons entre équipes
        doublons = set(equipe_a) & set(equipe_b)

        gagnant = st.radio(
            "Résultat",
            options=["A", "B", "Nul"],
            format_func=lambda x: f"Équipe {x}" if x != "Nul" else "Match nul",
            horizontal=True,
        )

        # --- Décompte des buts par joueur (version compacte) ---
        joueurs_du_match = [j for j in (equipe_a + equipe_b) if not doublons]

        buteurs = {}
        if joueurs_du_match:
            st.markdown("**⚽ Buts marqués**")
            for joueur in equipe_a:
                nb = st.number_input(
                    f"🅰️ {joueur}", min_value=0, step=1, value=0,
                    key=f"but_{joueur}", label_visibility="visible",
                )
                if nb > 0:
                    buteurs[joueur] = nb
            for joueur in equipe_b:
                nb = st.number_input(
                    f"🅱️ {joueur}", min_value=0, step=1, value=0,
                    key=f"but_{joueur}", label_visibility="visible",
                )
                if nb > 0:
                    buteurs[joueur] = nb

        if st.button("✅ Enregistrer le match", type="primary"):
            if not equipe_a or not equipe_b:
                st.error("Les deux équipes doivent contenir au moins un joueur.")
            elif doublons:
                st.error(f"Un joueur ne peut pas être dans les deux équipes : {', '.join(doublons)}")
            else:
                data["matchs"].append(
                    {
                        "date": str(match_date),
                        "equipe_a": equipe_a,
                        "equipe_b": equipe_b,
                        "gagnant": gagnant,
                        "buteurs": buteurs,
                    }
                )
                save_data(data)
                for j in joueurs_du_match:
                    st.session_state.pop(f"but_{j}", None)
                st.success("Match enregistré !")
                st.rerun()

    # Historique des matchs
    if data["matchs"]:
        st.divider()
        st.subheader("Historique des matchs")
        for i, m in enumerate(reversed(data["matchs"])):
            idx = len(data["matchs"]) - i
            if m["gagnant"] == "Nul":
                resultat = "Match nul"
            else:
                resultat = f"Équipe {m['gagnant']} gagnante"
            with st.expander(f"{m['date']} — Match #{idx} ({resultat})"):
                col1, col2 = st.columns(2)
                col1.write("**Équipe A** " + ("🏆" if m["gagnant"] == "A" else "🤝" if m["gagnant"] == "Nul" else ""))
                col1.write(", ".join(m["equipe_a"]))
                col2.write("**Équipe B** " + ("🏆" if m["gagnant"] == "B" else "🤝" if m["gagnant"] == "Nul" else ""))
                col2.write(", ".join(m["equipe_b"]))

                buteurs = m.get("buteurs", {})
                if buteurs:
                    st.write("**⚽ Buteurs :** " + ", ".join(
                        f"{j} ({n})" for j, n in sorted(buteurs.items(), key=lambda x: -x[1])
                    ))

                if st.button("🗑️ Supprimer ce match", key=f"del_match_{idx}"):
                    data["matchs"].remove(m)
                    save_data(data)
                    st.rerun()

# ------------------------- Onglet Joueurs -------------------------
with tab_joueurs:
    st.subheader("Gérer les joueurs")

    with st.form("ajout_joueur", clear_on_submit=True):
        nouveau_joueur = st.text_input("Nom du joueur")
        submitted = st.form_submit_button("➕ Ajouter")
        if submitted:
            nom = nouveau_joueur.strip()
            if not nom:
                st.error("Le nom ne peut pas être vide.")
            elif nom in data["joueurs"]:
                st.warning(f"{nom} existe déjà.")
            else:
                data["joueurs"].append(nom)
                save_data(data)
                st.success(f"{nom} ajouté !")
                st.rerun()

    st.divider()
    st.subheader("Liste des joueurs")

    if not data["joueurs"]:
        st.info("Aucun joueur pour l'instant.")
    else:
        for joueur in sorted(data["joueurs"]):
            col1, col2 = st.columns([4, 1])
            col1.write(joueur)
            if col2.button("🗑️ Supprimer", key=f"del_{joueur}"):
                data["joueurs"].remove(joueur)
                save_data(data)
                st.rerun()

# ------------------------- Onglet Évolution -------------------------
with tab_evolution:
    st.subheader("Évolution du classement dans le temps")

    if len(data["matchs"]) < 2:
        st.info("Il faut au moins 2 matchs enregistrés pour voir une évolution.")
    else:
        filtre_evolution = st.radio(
            "Afficher",
            options=["tous", "10+"],
            format_func=lambda x: "Tous ceux qui ont joué" if x == "tous" else "Joueurs ayant joué au moins 10 matchs",
            horizontal=True,
            key="filtre_evolution",
        )
        seuil_evolution = 1 if filtre_evolution == "tous" else 10

        df_hist = historique_rangs(data, seuil_evolution)

        if df_hist.empty:
            st.info("Aucun joueur ne remplit ce critère pour l'instant.")
        else:
            joueurs_disponibles = sorted(df_hist["Joueur"].unique())
            joueurs_selection = st.multiselect(
                "Joueurs à afficher",
                options=joueurs_disponibles,
                default=joueurs_disponibles,
            )

            df_filtre = df_hist[df_hist["Joueur"].isin(joueurs_selection)]

            if df_filtre.empty:
                st.info("Sélectionne au moins un joueur.")
            else:
                rang_max = int(df_filtre["Rang"].max())
                chart = (
                    alt.Chart(df_filtre)
                    .mark_line(point=alt.OverlayMarkDef(size=45), strokeWidth=2.5)
                    .encode(
                        x=alt.X("Match:O", title="Match n°", axis=alt.Axis(labelAngle=0)),
                        y=alt.Y(
                            "Rang:Q",
                            title="Rang",
                            scale=alt.Scale(domain=[rang_max + 0.5, 0.5]),
                            axis=alt.Axis(tickMinStep=1),
                        ),
                        color=alt.Color("Joueur:N", title=None),
                        tooltip=["Joueur", "Match", "Rang", "Points"],
                    )
                    .properties(height=480)
                    .configure_axis(labelFontSize=11, titleFontSize=12)
                    .configure_legend(
                        orient="bottom",
                        columns=3,
                        labelFontSize=11,
                        symbolSize=60,
                        labelLimit=100,
                    )
                    .interactive()
                )
                st.altair_chart(chart, use_container_width=True)
                st.caption("Le rang 1 (meilleur) est en haut du graphique. Pince pour zoomer, glisse pour te déplacer.")

# ------------------------- Onglet Buteurs -------------------------
with tab_buteurs:
    st.subheader("Classement des buteurs")

    df_buteurs = calculer_buteurs(data)

    if df_buteurs.empty:
        st.info("Aucun but enregistré pour l'instant. Renseigne les buteurs lors de la saisie d'un match.")
    else:
        st.dataframe(
            df_buteurs,
            use_container_width=True,
            column_config={
                "Buts/match": st.column_config.NumberColumn("Buts/match", format="%.2f"),
            },
        )

        st.divider()
        col1, col2 = st.columns(2)
        top_buteur = df_buteurs.iloc[0]
        col1.metric("👟 Meilleur buteur", top_buteur["Joueur"], f"{top_buteur['Buts']} buts")
        col2.metric("Total de buts marqués", int(df_buteurs["Buts"].sum()))
