import streamlit as st
import pandas as pd
from datetime import datetime
import re

# Google Sheets libs
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GS_AVAILABLE = True
except Exception:
    GS_AVAILABLE = False

st.set_page_config(page_title="TAP Grading Calculate", layout="centered")

st.markdown("<h1 style='text-align:center;color:#2d5a27'>PT EBL Mill</h1>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align:center;color:#2d5a27'>TAP Grading Calculate</h3>", unsafe_allow_html=True)

with st.form("input_form"):
    total = st.number_input("Total Janjang Sampel", min_value=1, step=1, format="%d", help="Masukkan total janjang yang di-grading")
    mengkal = st.number_input("Mengkal (jjg)", min_value=0, step=1, value=0)
    overripe = st.number_input("Over Ripe (jjg)", min_value=0, step=1, value=0)
    tikus = st.number_input("Tikus >50% (jjg)", min_value=0, step=1, value=0)
    tangkai = st.number_input("Tangkai Panjang (jjg)", min_value=0, step=1, value=0)
    parteno = st.number_input("Parteno (jjg)", min_value=0, step=1, value=0)
    submitted = st.form_submit_button("Hitung")

def compute_values(total, mengkal, overripe, tikus, tangkai, parteno):
    pers = {
        "Mengkal": (mengkal / total * 100) if total else 0,
        "Over Ripe": (overripe / total * 100) if total else 0,
        "Tikus": (tikus / total * 100) if total else 0,
        "Tangkai Panjang": (tangkai / total * 100) if total else 0,
        "Parteno": (parteno / total * 100) if total else 0,
    }
    pot = {}
    pot["Mengkal"] = 0.5 * pers["Mengkal"]
    pot["Over Ripe"] = 0.25 * max(pers["Over Ripe"] - 5, 0)
    pot["Tikus"] = 0.15 * pers["Tikus"]
    pot["Tangkai Panjang"] = 0.01 * pers["Tangkai Panjang"]
    pot["Parteno"] = 0.15 * pers["Parteno"]
    total_potongan = 2 + sum(pot.values())
    return pers, pot, total_potongan

# Auto connect ke Google Sheets (pakai secrets)
def save_to_gsheets(data: dict, sheet_url: str):
    if not GS_AVAILABLE:
        st.error("❌ Library Google Sheets belum terinstal di environment.")
        return False
    try:
        m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", sheet_url)
        if not m:
            st.error("URL Google Sheets tidak valid.")
            return False
        spreadsheet_id = m.group(1)

        sa_info = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(
            sa_info,
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"],
        )
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(spreadsheet_id)
        ws = sh.sheet1

        header = list(data.keys())
        all_values = ws.get_all_values()
        if len(all_values) == 0:
            ws.append_row(header)
        ws.append_row([data[h] for h in header], value_input_option="USER_ENTERED")
        return True
    except Exception as e:
        st.error(f"❌ Gagal menyimpan ke Google Sheets: {e}")
        return False

if submitted:
    if not total or total <= 0:
        st.error("Masukkan total janjang yang valid!")
    else:
        pers, pot, total_pot = compute_values(total, mengkal, overripe, tikus, tangkai, parteno)

        df = pd.DataFrame([
            {"Kondisi": k, "Persentase (%)": round(v, 2), "Potongan (%)": round(pot[k], 2)} for k, v in pers.items()
        ])
        st.table(df.style.format({"Persentase (%)": "{:.2f}", "Potongan (%)": "{:.2f}"}))
        st.markdown(f"**Total Potongan Akhir:** {total_pot:.2f}%")

        # Prepare data to save
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        result_row = {
            "timestamp": timestamp,
            "total_janjang": int(total),
            "mengkal_jjg": int(mengkal),
            "overripe_jjg": int(overripe),
            "tikus_jjg": int(tikus),
            "tangkai_jjg": int(tangkai),
            "parteno_jjg": int(parteno),
            "mengkal_pct": round(pers["Mengkal"], 4),
            "overripe_pct": round(pers["Over Ripe"], 4),
            "tikus_pct": round(pers["Tikus"], 4),
            "tangkai_pct": round(pers["Tangkai Panjang"], 4),
            "parteno_pct": round(pers["Parteno"], 4),
            "total_potongan_pct": round(total_pot, 4)
        }

        # AUTO SAVE ke Google Sheets
        sheet_url = "https://docs.google.com/spreadsheets/d/1LLRTb93VBiJgGULdktW4Bfxa8ixnJG8t6GpxzOlB6zw/edit?usp=sharing"
        st.info("⏳ Menyimpan hasil ke Google Sheets...")

        if save_to_gsheets(result_row, sheet_url):
            st.success("✅ Data berhasil disimpan ke Google Sheets!")
