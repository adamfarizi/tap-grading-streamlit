# app.py
import streamlit as st
import pandas as pd
from datetime import datetime
import re

# Google Sheets libs (optional, for save)
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
    # Persentase
    pers = {
        "Mengkal": (mengkal / total * 100) if total else 0,
        "Over Ripe": (overripe / total * 100) if total else 0,
        "Tikus": (tikus / total * 100) if total else 0,
        "Tangkai Panjang": (tangkai / total * 100) if total else 0,
        "Parteno": (parteno / total * 100) if total else 0,
    }
    # Potongan sesuai logika di HTML:
    pot = {}
    pot["Mengkal"] = 0.5 * pers["Mengkal"]
    pot["Over Ripe"] = 0.25 * max(pers["Over Ripe"] - 5, 0)
    pot["Tikus"] = 0.15 * pers["Tikus"]
    pot["Tangkai Panjang"] = 0.01 * pers["Tangkai Panjang"]
    pot["Parteno"] = 0.15 * pers["Parteno"]

    total_potongan = 2 + sum(pot.values())
    return pers, pot, total_potongan

if submitted:
    if not total or total <= 0:
        st.error("Masukkan total janjang yang valid!")
    else:
        pers, pot, total_pot = compute_values(total, mengkal, overripe, tikus, tangkai, parteno)

        df = pd.DataFrame([
            {"Kondisi": k, "Persentase (%)": round(v, 2), "Potongan (%)": round(pot[k if k in pot else k], 2) if k in pot else None}
            for k, v in pers.items()
        ])
        # ensure proper order
        df = df[["Kondisi", "Persentase (%)", "Potongan (%)"]]

        st.table(df.style.format({"Persentase (%)": "{:.2f}", "Potongan (%)": "{:.2f}"}))
        st.markdown(f"**Total Potongan Akhir:** {total_pot:.2f}%")

        # Prepare row for Google Sheets
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
        st.success("Perhitungan berhasil dibuat — mau simpan ke Google Sheets?")

        st.write("### Simpan / Export")
        cols = st.columns([1,1,1])
        if cols[0].button("Download CSV"):
            st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8"), file_name="tap_grading.csv", mime="text/csv")
        # Google Sheets save
        st.write("---")
        sheet_url = st.text_input("Google Sheets URL (atau kosong jika nggak mau save):", value="https://docs.google.com/spreadsheets/d/1LLRTb93VBiJgGULdktW4Bfxa8ixnJG8t6GpxzOlB6zw/edit?usp=sharing")
        if sheet_url:
            if not GS_AVAILABLE:
                st.error("Library Google Sheets belum tersedia. Install 'gspread' dan 'google-auth' di environment.")
            else:
                # parse spreadsheet id
                m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", sheet_url)
                if not m:
                    st.error("URL Google Sheets tidak valid.")
                else:
                    spreadsheet_id = m.group(1)
                    st.info("Siapkan credentials: upload file service_account.json atau set `st.secrets['gcp_service_account']`.")
                    cred_option = st.radio("Pilih metode autentikasi", ("Upload service_account.json", "Gunakan Streamlit secrets (st.secrets)"))
                    save_btn = st.button("Simpan ke Google Sheets")
                    if save_btn:
                        try:
                            if cred_option == "Upload service_account.json":
                                uploaded = st.file_uploader("Upload service_account.json", type=["json"], accept_multiple_files=False)
                                if not uploaded:
                                    st.warning("Upload dulu file service account JSON.")
                                else:
                                    creds_dict = uploaded.getvalue()
                                    import json
                                    sa_info = json.loads(creds_dict.decode("utf-8"))
                                    creds = Credentials.from_service_account_info(sa_info, scopes=["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"])
                                    gc = gspread.authorize(creds)
                                    sh = gc.open_by_key(spreadsheet_id)
                                    ws = sh.sheet1
                                    # If sheet empty, write header
                                    header = list(result_row.keys())
                                    # append header if sheet is empty
                                    if ws.row_count == 0 or not ws.get_all_values():
                                        ws.append_row(header)
                                    ws.append_row([result_row[h] for h in header], value_input_option='USER_ENTERED')
                                    st.success("Berhasil menyimpan ke Google Sheets!")
                            else:
                                # st.secrets mode
                                sa_info = st.secrets["gcp_service_account"]
                                creds = Credentials.from_service_account_info(sa_info, scopes=["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"])
                                gc = gspread.authorize(creds)
                                sh = gc.open_by_key(spreadsheet_id)
                                ws = sh.sheet1
                                header = list(result_row.keys())
                                if ws.row_count == 0 or not ws.get_all_values():
                                    ws.append_row(header)
                                ws.append_row([result_row[h] for h in header], value_input_option='USER_ENTERED')
                                st.success("Berhasil menyimpan ke Google Sheets!")
                        except Exception as e:
                            st.exception(e)
