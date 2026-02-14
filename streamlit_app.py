import streamlit as st
import pandas as pd
import random

# Nastavení vzhledu stránky
st.set_page_config(page_title="Petanque Turnaj", layout="wide")

st.title("🏆 Petanque Manažer (Swiss)")

# Inicializace dat (uložení stavu mezi kliknutími)
if 'tymy' not in st.session_state:
    st.session_state.tymy = []
if 'kolo' not in st.session_state:
    st.session_state.kolo = 0
if 'rozpis' not in st.session_state:
    st.session_state.rozpis = []
if 'historie' not in st.session_state:
    st.session_state.historie = []

# --- 1. ZADÁVÁNÍ TÝMŮ ---
if st.session_state.kolo == 0:
    st.header("1. Registrace týmů")
    vstup = st.text_area("Zadej názvy týmů (každý na nový řádek nebo oddělené čárkou):", height=150)
    
    if st.button("Zahájit turnaj", type="primary"):
        seznam = [s.strip() for s in vstup.replace('\n', ',').split(",") if s.strip()]
        if len(seznam) < 2:
            st.error("Potřebuješ aspoň 2 týmy!")
        else:
            # Vytvoření tabulky týmů
            tymy_data = []
            for jmeno in seznam:
                tymy_data.append({"Tým": jmeno, "Výhry": 0, "Skóre +": 0, "Skóre -": 0, "Rozdíl": 0})
            
            # Sudý počet pro BYE
            if len(tymy_data) % 2 != 0:
                tymy_data.append({"Tým": "BYE (Volno)", "Výhry": 0, "Skóre +": 0, "Skóre -": 0, "Rozdíl": 0})
            
            st.session_state.tymy = pd.DataFrame(tymy_data)
            st.session_state.kolo = 1
            st.rerun()

# --- 2. PRŮBĚH TURNAJE ---
else:
    # Seřazení tabulky (Swiss logika)
    st.session_state.tymy["Rozdíl"] = st.session_state.tymy["Skóre +"] - st.session_state.tymy["Skóre -"]
    st.session_state.tymy = st.session_state.tymy.sort_values(by=["Výhry", "Rozdíl", "Skóre +"], ascending=False).reset_index(drop=True)

    st.sidebar.header("Průběžná tabulka")
    st.sidebar.table(st.session_state.tymy)

    st.header(f"Kolo č. {st.session_state.kolo}")

    # Generování rozpisu pro nové kolo
    if not st.session_state.rozpis:
        t_list = st.session_state.tymy["Tým"].tolist()
        parovani = []
        for i in range(0, len(t_list), 2):
            parovani.append((t_list[i], t_list[i+1]))
        st.session_state.rozpis = parovani

    # Zobrazení rozpisu
    st.subheader("Rozpis zápasů")
    col1, col2 = st.columns(2)
    vysledky_kola = []

    for idx, (t1, t2) in enumerate(st.session_state.rozpis):
        with st.container():
            st.markdown(f"**Hřiště {idx+1}: {t1} vs {t2}**")
            if t2 == "BYE (Volno)":
                st.info(f"{t1} má automatickou výhru 13:0")
                vysledky_kola.append((t1, t2, 13, 0))
            elif t1 == "BYE (Volno)":
                st.info(f"{t2} má automatickou výhru 13:0")
                vysledky_kola.append((t1, t2, 0, 13))
            else:
                c1, c2 = st.columns(2)
                s1 = c1.number_input(f"Body {t1}", min_value=0, max_value=13, key=f"s1_{idx}_{st.session_state.kolo}")
                s2 = c2.number_input(f"Body {t2}", min_value=0, max_value=13, key=f"s2_{idx}_{st.session_state.kolo}")
                vysledky_kola.append((t1, t2, s1, s2))
            st.divider()

    if st.button("Uložit výsledky a další kolo", type="primary"):
        # Aktualizace databáze
        for t1, t2, s1, s2 in vysledky_kola:
            # Najít indexy v DataFrame a přičíst body
            idx1 = st.session_state.tymy[st.session_state.tymy["Tým"] == t1].index[0]
            idx2 = st.session_state.tymy[st.session_state.tymy["Tým"] == t2].index[0]
            
            st.session_state.tymy.at[idx1, "Skóre +"] += s1
            st.session_state.tymy.at[idx1, "Skóre -"] += s2
            st.session_state.tymy.at[idx2, "Skóre +"] += s2
            st.session_state.tymy.at[idx2, "Skóre -"] += s1
            
            if s1 > s2: st.session_state.tymy.at[idx1, "Výhry"] += 1
            elif s2 > s1: st.session_state.tymy.at[idx2, "Výhry"] += 1
        
        st.session_state.kolo += 1
        st.session_state.rozpis = [] # Reset pro nové losování
        st.rerun()

    if st.button("Resetovat celý turnaj"):
        st.session_state.clear()
        st.rerun()
