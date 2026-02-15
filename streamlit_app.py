import streamlit as st
import pandas as pd
import random
import os
import json
from fpdf import FPDF
from streamlit_gsheets import GSheetsConnection

# --- KONFIGURACE A STYLY ---
st.set_page_config(page_title="Organizátor pétanque", layout="wide")
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #1e3a8a; color: white; }
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- PŘIPOJENÍ GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def uloz_do_google():
    stav = {
        "nazev_akce": st.session_state.nazev_akce,
        "kolo": st.session_state.kolo,
        "max_kol": st.session_state.max_kol,
        "system": st.session_state.system,
        "tymy": st.session_state.tymy.to_dict(orient="records"),
        "historie": st.session_state.historie
    }
    df_save = pd.DataFrame([{"stav_json": json.dumps(stav, ensure_ascii=False)}])
    conn.update(worksheet="Stav", data=df_save)

def nacti_z_google():
    try:
        df = conn.read(worksheet="Stav", ttl=0)
        if not df.empty and "stav_json" in df.columns:
            r = df.iloc[0]["stav_json"]
            if r and r != "{}" and not pd.isna(r):
                return json.loads(r)
    except: pass
    return None

# --- INICIALIZACE STATE ---
if "kolo" not in st.session_state:
    data = nacti_z_google()
    if data:
        st.session_state.nazev_akce = data["nazev_akce"]
        st.session_state.kolo = data["kolo"]
        st.session_state.max_kol = data["max_kol"]
        st.session_state.system = data["system"]
        st.session_state.tymy = pd.DataFrame(data["tymy"])
        st.session_state.historie = data["historie"]
    else:
        st.session_state.nazev_akce = "Pétanque Turnaj"
        st.session_state.kolo = 0
        st.session_state.max_kol = 3
        st.session_state.system = "Švýcar"
        st.session_state.tymy = None
        st.session_state.historie = []

# --- FUNKCE PRO VÝPOČET BUCHHOLZE ---
def prepocitej_buchholz():
    tymy_df = st.session_state.tymy
    historie = st.session_state.historie
    nove_buchholzy = []
    
    for _, tym in tymy_df.iterrows():
        jmeno = tym["Hráč/Tým"]
        souperi = []
        for h in historie:
            if h["Hráč/Tým 1"] == jmeno: souperi.append(h["Hráč/Tým 2"])
            elif h["Hráč/Tým 2"] == jmeno: souperi.append(h["Hráč/Tým 1"])
        
        b_skore = 0
        for s in souperi:
            if s == "VOLNÝ LOS": continue
            vyhry_soupere = tymy_df[tymy_df["Hráč/Tým"] == s]["Výhry"].values
            if len(vyhry_soupere) > 0: b_skore += vyhry_soupere[0]
        nove_buchholzy.append(b_skore)
    
    st.session_state.tymy["Buchholz"] = nove_buchholzy

# --- PDF EXPORT ---
def export_pdf():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 10, f"Výsledky: {st.session_state.nazev_akce}", ln=True, align="C")
    pdf.set_font("Arial", "", 12)
    pdf.ln(10)
    
    df_v = st.session_state.tymy.sort_values(by=["Výhry", "Buchholz", "Rozdíl"], ascending=False)
    for i, (_, r) in enumerate(df_v.iterrows(), 1):
        line = f"{i}. {r['Hráč/Tým']} - Výhry: {r['Výhry']}, Buchholz: {r['Buchholz']}, Rozdíl: {r['Skóre +']-r['Skóre -']}"
        pdf.cell(190, 8, line, ln=True)
    return pdf.output(dest="S").encode("latin-1", errors="replace")

# --- HLAVNÍ ROZHRANÍ ---
st.title("🏆 Organizátor pétanque turnajů")

if st.session_state.kolo == 0:
    st.subheader("⚙️ Nastavení turnaje")
    
    st.session_state.nazev_akce = st.text_input("Název turnaje:", st.session_state.nazev_akce)
    st.session_state.system = st.radio("Zvolte systém:", ["Švýcar", "Každý s každým"])
    
    vystup_area = st.text_area("Seznam hráčů/týmů (každý na nový řádek):")
    h_list = [i.strip() for i in vystup_area.split('\n') if i.strip()]
    n_hracu = len(h_list)

    # Dynamická logika pro počet kol
    if st.session_state.system == "Každý s každým":
        if n_hracu > 1:
            vypocet_kol = n_hracu - 1 if n_hracu % 2 == 0 else n_hracu
            st.session_state.max_kol = vypocet_kol
            st.info(f"🔢 Pro {n_hracu} hráčů systém 'Každý s každým' vyžaduje **{vypocet_kol} kol**.")
            st.number_input("Počet kol:", value=vypocet_kol, disabled=True)
        else:
            st.warning("Zadejte jména hráčů pro výpočet kol.")
    else:
        st.session_state.max_kol = st.number_input("Počet kol (nastavte ručně):", 1, 15, st.session_state.max_kol)

    if st.button("Zahájit a uložit do cloudu", type="primary"):
        if n_hracu >= 2:
            h = h_list.copy()
            if len(h) % 2 != 0: h.append("VOLNÝ LOS")
            st.session_state.tymy = pd.DataFrame([{"Hráč/Tým": i, "Výhry": 0, "Skóre +": 0, "Skóre -": 0, "Rozdíl": 0, "Buchholz": 0} for i in h])
            st.session_state.kolo = 1
            st.session_state.historie = []
            uloz_do_google()
            st.rerun()
        else:
            st.error("Zadejte aspoň 2 účastníky!")

elif st.session_state.kolo <= st.session_state.max_kol:
    st.header(f"🏟️ {st.session_state.kolo}. kolo / {st.session_state.max_kol}")
    
    # Generování zápasů
    df_t = st.session_state.tymy
    if st.session_state.system == "Švýcar":
        # Jednoduché párování pro Švýcar (podle pořadí)
        df_s = df_t.sort_values(by=["Výhry", "Buchholz", "Rozdíl"], ascending=False)
        h = df_s["Hráč/Tým"].tolist()
        zap = [(h[i], h[i+1]) for i in range(0, len(h), 2)]
    else:
        # Round Robin (Každý s každým) algoritmus s rotací
        h = df_t["Hráč/Tým"].tolist()
        n = len(h)
        shift = (st.session_state.kolo - 1) % (n - 1)
        fixed = h[0]
        rest = h[1:]
        rotated = rest[-shift:] + rest[:-shift] if shift > 0 else rest
        curr = [fixed] + rotated
        zap = [(curr[i], curr[n-1-i]) for i in range(n // 2)]

    # Zápis výsledků
    vysledky_kola = []
    for i, (t1, t2) in enumerate(zap):
        col1, col2, col3, col4 = st.columns([3, 1, 1, 3])
        with col1: st.write(f"**{t1}**")
        with col2: s1 = st.number_input("Skóre", 0, 13, 0, key=f"s1_{i}")
        with col3: s2 = st.number_input("Skóre", 0, 13, 0, key=f"s2_{i}")
        with col4: st.write(f"**{t2}**")
        vysledky_kola.append((t1, s1, t2, s2))

    if st.button("Uložit kolo a pokračovat"):
        for t1, s1, t2, s2 in vysledky_kola:
            # Aktualizace statistik
            idx1 = st.session_state.tymy[st.session_state.tymy["Hráč/Tým"] == t1].index[0]
            idx2 = st.session_state.tymy[st.session_state.tymy["Hráč/Tým"] == t2].index[0]
            
            st.session_state.tymy.at[idx1, "Skóre +"] += s1
            st.session_state.tymy.at[idx1, "Skóre -"] += s2
            st.session_state.tymy.at[idx2, "Skóre +"] += s2
            st.session_state.tymy.at[idx2, "Skóre -"] += s1
            
            if s1 > s2: st.session_state.tymy.at[idx1, "Výhry"] += 1
            elif s2 > s1: st.session_state.tymy.at[idx2, "Výhry"] += 1
            
            st.session_state.historie.append({"Kolo": st.session_state.kolo, "Hráč/Tým 1": t1, "S1": s1, "S2": s2, "Hráč/Tým 2": t2})
        
        prepocitej_buchholz()
        st.session_state.kolo += 1
        uloz_do_google()
        st.rerun()

else:
    st.header("🏁 Turnaj ukončen")
    df_final = st.session_state.tymy.sort_values(by=["Výhry", "Buchholz", "Rozdíl"], ascending=False).reset_index(drop=True)
    df_final.index += 1
    st.table(df_final)
    
    st.download_button("📥 Stáhnout výsledky v PDF", data=export_pdf(), file_name="vysledky.pdf", mime="application/pdf")
    
    if st.button("Vymazat turnaj a začít znovu"):
        st.session_state.kolo = 0
        st.session_state.historie = []
        uloz_do_google()
        st.rerun()
