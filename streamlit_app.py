import streamlit as st
import pandas as pd
import os, json, random
from fpdf import FPDF
from streamlit_gsheets import GSheetsConnection

# --- KONFIGURACE ---
st.set_page_config(page_title="Pétanque Pro", layout="wide")

def over_heslo():
    if "autentizovan" not in st.session_state:
        st.session_state.autentizovan = False
    
    if not st.session_state.autentizovan:
        # Načtení hesla ze Secrets a ošetření (strip odstraní nechtěné mezery)
        master_heslo = str(st.secrets.get("access_password", "admin123")).strip()
        
        st.title("🔒 Přístup omezen")
        vstup = st.text_input("Zadejte heslo turnaje:", type="password")
        
        if st.button("Vstoupit"):
            # .strip() použijeme i u vstupu, aby mezera na konci hesla nezpůsobila chybu
            if vstup.strip() == master_heslo:
                st.session_state.autentizovan = True
                st.rerun()
            else:
                st.error("Nesprávné heslo!")
                # Malý trik pro debug: Pokud jsi admin, můžeš si dočasně nechat 
                # vypsat, co si aplikace myslí, že je správné heslo (jen pro test!)
                # st.write(f"DEBUG: Systém čeká: '{master_heslo}'") 
        st.stop()

over_heslo()

# --- PŘIPOJENÍ GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def uloz_do_google():
    stav = {
        "nazev_akce": st.session_state.nazev_akce,
        "datum_akce": st.session_state.get("datum_akce", ""),
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

# --- INICIALIZACE ---
if "kolo" not in st.session_state:
    data = nacti_z_google()
    if data:
        st.session_state.nazev_akce = data.get("nazev_akce", "Pétanque Turnaj")
        st.session_state.datum_akce = data.get("datum_akce", "")
        st.session_state.kolo = data.get("kolo", 0)
        st.session_state.max_kol = data.get("max_kol", 3)
        st.session_state.system = data.get("system", "Švýcar")
        st.session_state.tymy = pd.DataFrame(data["tymy"])
        st.session_state.historie = data.get("historie", [])
    else:
        st.session_state.nazev_akce = "Pétanque Turnaj"
        st.session_state.datum_akce = ""
        st.session_state.kolo = 0
        st.session_state.max_kol = 3
        st.session_state.system = "Švýcar"
        st.session_state.tymy = None
        st.session_state.historie = []

# --- LOGIKA PÁROVÁNÍ (ŠVÝCAR BEZ OPAKOVÁNÍ) ---
def generuj_parovani_svycar(tymy_list, historie):
    hraci = tymy_list.copy()
    odehrane_zapasy = set()
    for h in historie:
        p = tuple(sorted((h["Hráč/Tým 1"], h["Hráč/Tým 2"])))
        odehrane_zapasy.add(p)

    parovani = []
    pracovni_hraci = hraci.copy()
    
    while len(pracovni_hraci) > 1:
        h1 = pracovni_hraci[0]
        nasel_se = False
        for i in range(1, len(pracovni_hraci)):
            h2 = pracovni_hraci[i]
            if tuple(sorted((h1, h2))) not in odehrane_zapasy:
                parovani.append((h1, h2))
                pracovni_hraci.pop(i)
                pracovni_hraci.pop(0)
                nasel_se = True
                break
        
        if not nasel_se:
            # Nouzový režim: Pokud nelze najít unikátní dvojici, vezmi prvního možného
            h2 = pracovni_hraci[1]
            parovani.append((h1, h2))
            pracovni_hraci.pop(1)
            pracovni_hraci.pop(0)
            
    return parovani

def prepocitej_buchholz():
    tymy_df = st.session_state.tymy
    historie = st.session_state.historie
    nove_buchholzy = []
    nove_zapasy = []
    for _, tym in tymy_df.iterrows():
        jmeno = tym["Hráč/Tým"]
        souperi = [h["Hráč/Tým 2"] if h["Hráč/Tým 1"] == jmeno else h["Hráč/Tým 1"] 
                   for h in historie if h["Hráč/Tým 1"] == jmeno or h["Hráč/Tým 2"] == jmeno]
        
        b_skore = sum(tymy_df[tymy_df["Hráč/Tým"] == s]["Výhry"].iloc[0] for s in souperi if s != "VOLNÝ LOS")
        nove_buchholzy.append(int(b_skore))
        nove_zapasy.append(len(souperi))
        
    st.session_state.tymy["Buchholz"] = nove_buchholzy
    st.session_state.tymy["Zápasy"] = nove_zapasy
    st.session_state.tymy["Rozdíl"] = st.session_state.tymy["Skóre +"] - st.session_state.tymy["Skóre -"]

# --- PDF EXPORT ---
def export_pdf():
    pdf = FPDF()
    pdf.add_page()
    font_path = "DejaVuSans.ttf"
    if os.path.exists(font_path):
        pdf.add_font("DejaVu", "", font_path, uni=True)
        use_font = "DejaVu"
    else: use_font = "Arial"

    pdf.set_font(use_font, "", 16)
    pdf.cell(190, 10, f"{st.session_state.nazev_akce}", ln=True, align="C")
    pdf.set_font(use_font, "", 10)
    pdf.ln(5)

    # Tabulka výsledků
    df_v = st.session_state.tymy[st.session_state.tymy["Hráč/Tým"] != "VOLNÝ LOS"].sort_values(by=["Výhry", "Buchholz", "Rozdíl"], ascending=False)
    
    pdf.set_font(use_font, "", 12)
    pdf.cell(190, 10, "Konečné pořadí:", ln=True)
    pdf.set_font(use_font, "", 9)
    
    head = ["Poř.", "Hráč/Tým", "Výhry", "Buchholz", "Rozdíl skóre", "Zápasy"]
    cols = [10, 80, 25, 25, 25, 25]
    
    for i, h in enumerate(head):
        pdf.cell(cols[i], 8, h, border=1)
    pdf.ln()

    for i, (_, r) in enumerate(df_v.iterrows(), 1):
        pdf.cell(cols[0], 7, str(i), border=1)
        pdf.cell(cols[1], 7, str(r['Hráč/Tým']), border=1)
        pdf.cell(cols[2], 7, str(int(r['Výhry'])), border=1)
        pdf.cell(cols[3], 7, str(int(r['Buchholz'])), border=1)
        pdf.cell(cols[4], 7, str(int(r['Rozdíl'])), border=1)
        pdf.cell(cols[5], 7, str(int(r['Zápasy'])), border=1)
        pdf.ln()

    try: return bytes(pdf.output())
    except: return pdf.output(dest='S').encode('latin-1', 'replace')

# --- MAIN UI ---
st.title("🏆 Organizátor pétanque")

if st.session_state.kolo == 0:
    col_a, col_b = st.columns(2)
    with col_a:
        st.session_state.nazev_akce = st.text_input("Název turnaje:", st.session_state.nazev_akce)
        st.session_state.datum_akce = st.text_input("Datum turnaje:", st.session_state.datum_akce)
        st.session_state.system = st.radio("Systém:", ["Švýcar", "Každý s každým"])
    with col_b:
        v = st.text_area("Seznam hráčů (jeden na řádek):", height=150)
        if st.session_state.system == "Každý s každým":
            h_count = len([i for i in v.split('\n') if i.strip()])
            st.session_state.max_kol = h_count - 1 if h_count % 2 == 0 else h_count
            st.info(f"Počet kol: {st.session_state.max_kol}")
        else:
            st.session_state.max_kol = st.number_input("Počet kol:", 1, 15, 3)

    if st.button("Zahájit turnaj", type="primary"):
        h_list = [i.strip() for i in v.split('\n') if i.strip()]
        if len(h_list) >= 2:
            if len(h_list) % 2 != 0: h_list.append("VOLNÝ LOS")
            st.session_state.tymy = pd.DataFrame([{"Hráč/Tým": x, "Výhry": 0, "Skóre +": 0, "Skóre -": 0, "Rozdíl": 0, "Buchholz": 0, "Zápasy": 0} for x in h_list])
            st.session_state.kolo = 1
            st.session_state.historie = []
            uloz_do_google()
            st.rerun()

elif st.session_state.kolo <= st.session_state.max_kol:
    st.header(f"🏟️ {st.session_state.kolo}. kolo / {st.session_state.max_kol}")
    
    # Generování párů
    if st.session_state.system == "Švýcar":
        df_s = st.session_state.tymy.sort_values(by=["Výhry", "Buchholz", "Rozdíl"], ascending=False)
        seznam_jmen = df_s["Hráč/Tým"].tolist()
        zapasy = generuj_parovani_svycar(seznam_jmen, st.session_state.historie)
    else:
        h_orig = st.session_state.tymy["Hráč/Tým"].tolist()
        n = len(h_orig)
        s = (st.session_state.kolo - 1) % (n - 1)
        res = h_orig[1:]
        rotated = res[-s:] + res[:-s] if s > 0 else res
        h = [h_orig[0]] + rotated
        zapasy = [(h[i], h[len(h)-1-i]) for i in range(len(h)//2)]

    vysledky_kola = []
    for i, (t1, t2) in enumerate(zapasy):
        c1, c2, c3, c4 = st.columns([3, 1, 1, 3])
        is_bye = (t1 == "VOLNÝ LOS" or t2 == "VOLNÝ LOS")
        with c1: st.markdown(f"**{t1}**")
        with c2: 
            s1 = (13 if t2 == "VOLNÝ LOS" else 0) if is_bye else st.number_input("Body", 0, 13, 0, key=f"s1_{i}")
            if is_bye: st.write(f"**{s1}**")
        with c3: 
            s2 = (13 if t1 == "VOLNÝ LOS" else 0) if is_bye else st.number_input("Body", 0, 13, 0, key=f"s2_{i}")
            if is_bye: st.write(f"**{s2}**")
        with c4: st.markdown(f"**{t2}**")
        vysledky_kola.append((t1, s1, t2, s2))
        st.divider()

    if st.button("Uložit výsledky kola", type="primary"):
        for t1, s1, t2, s2 in vysledky_kola:
            for t, sp, sm in [(t1, s1, s2), (t2, s2, s1)]:
                idx = st.session_state.tymy[st.session_state.tymy["Hráč/Tým"] == t].index[0]
                st.session_state.tymy.at[idx, "Skóre +"] += sp
                st.session_state.tymy.at[idx, "Skóre -"] += sm
                if sp > sm: st.session_state.tymy.at[idx, "Výhry"] += 1
            st.session_state.historie.append({"Kolo": st.session_state.kolo, "Hráč/Tým 1": t1, "S1": s1, "S2": s2, "Hráč/Tým 2": t2})
        
        prepocitej_buchholz()
        st.session_state.kolo += 1
        uloz_do_google()
        st.rerun()

else:
    st.header("🏁 Konečné pořadí turnaje")
    df_final = st.session_state.tymy[st.session_state.tymy["Hráč/Tým"] != "VOLNÝ LOS"].sort_values(by=["Výhry", "Buchholz", "Rozdíl"], ascending=False).reset_index(drop=True)
    df_final.index += 1
    df_final.index.name = "Pořadí"
    
    st.table(df_final[["Hráč/Tým", "Výhry", "Buchholz", "Rozdíl", "Zápasy"]])
    
    col_pdf, col_reset = st.columns(2)
    with col_pdf:
        pdf_bytes = export_pdf()
        st.download_button("📥 Stáhnout výsledky (PDF)", pdf_bytes, "vysledky.pdf", "application/pdf")
    with col_reset:
        if st.button("Smazat turnaj a začít znovu"):
            st.session_state.kolo = 0
            uloz_do_google()
            st.rerun()
