import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

st.title("Test připojení")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(worksheet="Stav")
    st.success("Připojení k Google Sheets funguje!")
    st.write("Data v tabulce:", df)
except Exception as e:
    st.error(f"Chyba připojení: {e}")
    st.info("Zkontrolujte, zda máte v Secrets správné URL a v tabulce list 'Stav'.")
