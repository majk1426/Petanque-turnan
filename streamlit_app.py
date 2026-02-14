import streamlit as st
import pandas as pd

# Nastavení vzhledu stránky
st.set_page_config(page_title="Pétanque Hradec Králové", layout="wide")

# Záhlaví s názvem klubu
st.markdown("<h3 style='text-align: center; color: #555;'>Klub přátel pétanque Hradec Králové</h3>", unsafe_allow_index=True)
st.title("🏆 Turnajový manažer")
st.divider()

# Inicializace stavu
if 'tymy' not in st.session_state:
    st.session_state.tymy = []
if 'kolo' not in st.session_state:
    st.session_state.kolo = 0
if 'max_kol' not in st.session_state:
    st.session_state.max_kol = 3
if 'rozpis' not in st.session_state:
    st.session_state.rozpis = []
if 'nazev_akce' not in st.session_state:
    st.session_state.nazev_akce = "Místní turnaj"

# --- 1. NASTAVENÍ TURNAJE ---
if st.session_state.kolo == 0:
    st.header("⚙️ Nastavení turnaje")
    
    st.session_state.nazev_akce = st.text_input("Název turnaje:", value="Pohár Hradce Králové")
    
    col_a, col_b = st.columns(2)
    with col_a:
        vstup = st.text_area("Seznam týmů (každý tým na nový řádek):", height=200, placeholder="Např.:\nKoule HK\nDraci z Pardubic\nStřelci")
    with col_b:
        st.session_state.max_kol = st.number_input
