import streamlit as st
import pandas as pd
from datetime import datetime
import re
from io import BytesIO
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
import tempfile
import gspread
from google.oauth2.service_account import Credentials

# ===================== CONFIG =====================
st.set_page_config(page_title="Kalkulator Grading - PT EBL Mill", layout="centered", page_icon="🧾")

st.markdown("""
<style>
body {font-family:'Segoe UI',sans-serif;color:#0f172a;}
.title{text-align:center;color:#2d5a27;font-size:2em;font-weight:700;margin-bottom:0;}
.subtitle{text-align:center;color:#64748b;margin-bottom:20px;}
.section{border:1px solid #d1d5db;border-radius:10px;padding:20px;margin-bottom:25px;background-color:#f9fafb;}
</style>
""", unsafe_allow_html=True)

# ===================== HEADER =====================
from pathlib import Path
import base64

# Encode gambar logo biar bisa tampil di HTML
logo_path = Path("assets/logo.png")
if logo_path.exists():
    with open(logo_path, "rb") as f:
        logo_base64 = base64.b64encode(f.read()).decode()
    logo_html = f"<img src='data:image/png;base64,{logo_base64}' width='200'>"
else:
    logo_html = "<div style='color:red;'>⚠️ Logo tidak ditemukan</div>"

# Tampilkan header rapi dan tengah
st.markdown(f"""
<div style='text-align:center; margin-bottom:10px;'>
    {logo_html}
    <h1 class='title' style='margin-top:10px;'>Kalkulator Grading</h1>
    <p class='subtitle'>PT EBL Mill - Sistem Penilaian Kualitas Janjang</p>
</div>
""", unsafe_allow_html=True)


# ===================== SESSION =====================
if "step" not in st.session_state:
    st.session_state.step = 1
if "identitas" not in st.session_state:
    st.session_state.identitas = {}

# ===================== GOOGLE SETUP =====================
def get_gsheets_client():
    sa_info = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(sa_info, scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
    ])
    return gspread.authorize(creds)

def get_gdrive_client():
    sa_info = st.secrets["gcp_service_account"]
    gauth = GoogleAuth()
    gauth.settings['client_config_backend'] = 'service'
    gauth.service_config = sa_info
    gauth.LoadCredentialsFile = lambda *args, **kwargs: None
    gauth.SaveCredentialsFile = lambda *args, **kwargs: None
    gauth.LocalWebserverAuth = lambda *args, **kwargs: None
    
    # 🔑 Tambahkan full scope Drive di sini:
    gauth.credentials = Credentials.from_service_account_info(
        sa_info,
        scopes=[
            "https://www.googleapis.com/auth/drive",         # full access
            "https://www.googleapis.com/auth/drive.file"     # upload file
        ]
    )
    return GoogleDrive(gauth)

# ===================== FUNGSI =====================
def compute_values(kondisi: dict, total: int):
    """
    Hitung persentase dan potongan sesuai rumus PDF 'Kalkulator Grading'.
    - Persentase = (jumlah janjang kondisi / total janjang) * 100
    - Total potongan = 2% + (Mengkal + Over Ripe + Tikus + Tangkai Panjang + Partenocarpic)
    """
    if total <= 0:
        raise ValueError("Total janjang harus lebih dari 0")

    # Hitung persentase setiap kondisi
    pers = {k: (v / total * 100) for k, v in kondisi.items()}

    # Hitung potongan hanya untuk kondisi tertentu sesuai PDF
    pot = {
        "Mengkal": 0.5 * pers.get("Mengkal", 0),
        "Over Ripe": 0.25 * max(pers.get("Over Ripe", 0) - 5, 0),
        "Tikus": 0.15 * pers.get("Tikus", 0),  # ✅ diseragamkan tanpa >50%
        "Tangkai Panjang": 0.01 * pers.get("Tangkai Panjang", 0),
        "Partenocarpic": 0.15 * pers.get("Partenocarpic", 0)
    }

    # Total potongan sesuai rumus di PDF
    total_potongan = 2 + sum(pot.values())

    return pers, pot, total_potongan

def upload_to_drive(file, drive_folder_id=None):
    """Upload foto ke Google Drive folder yang dibagikan dan kembalikan URL-nya"""
    if not file:
        st.warning("⚠️ Tidak ada file yang diupload.")
        return ""

    try:
        st.info("🚀 Menghubungkan ke Google Drive...")
        drive = get_gdrive_client()

        # Simpan sementara file
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.write(file.getvalue())
        temp_file.close()

        # Debug info
        st.write(f"📁 Folder ID: {drive_folder_id}")
        st.write(f"📸 File: {file.name}")

        # Buat file di Drive
        gfile = drive.CreateFile({
            "title": file.name,
            "parents": [{"id": drive_folder_id}] if drive_folder_id else []
        })
        gfile.SetContentFile(temp_file.name)

        # Upload
        gfile.Upload()
        file_id = gfile["id"]

        # Cek apakah file bener-bener diupload
        if not file_id:
            st.error("❌ Upload gagal, file_id kosong.")
            return ""

        # Set file bisa dilihat publik
        gfile.InsertPermission({"type": "anyone", "value": "anyone", "role": "reader"})

        url = f"https://drive.google.com/uc?id={file_id}"
        st.success(f"✅ File berhasil diupload ke Google Drive!")
        st.write(f"🌐 URL file: {url}")
        return url

    except Exception as e:
        st.error(f"❌ Upload ke Google Drive gagal: {e}")
        return ""

def save_to_gsheets(data, sheet_url):
    try:
        client = get_gsheets_client()
        spreadsheet_id = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", sheet_url).group(1)
        sh = client.open_by_key(spreadsheet_id)
        ws = sh.sheet1

        # === Kolom sesuai sheet asli ===
        columns = [
            "Mill (PT)", "Tanggal", "Nama DO", "Afdeling", "Blok",
            "Nama Driver", "Plat Nomor", "Upload Foto Driver",
            "Mentah", "Mengkal", "Over Ripe", "Busuk",
            "Janjang Kosong", "Brondolan Segar", "Brondolan Busuk",
            "Sampah", "Abnormal", "Tikus", "Burung", "Tupai",
            "Tangkai Panjang", "Partenocarpic", "Kempet", "Total Potongan (%)", "Timestamp"
        ]

        # Kalau kosong, tulis header dulu
        if len(ws.get_all_values()) == 0:
            ws.append_row(columns)

        # Susun data sesuai urutan kolom
        row = [
            data.get("mill", ""),
            data.get("timestamp", ""),
            data.get("nama_do", ""),
            data.get("afdeling", ""),
            data.get("blok", ""),
            data.get("nama_driver", ""),
            data.get("plat", ""),
            data.get("foto_url", ""),
            data.get("mentah", 0),
            data.get("mengkal", 0),
            data.get("overripe", 0),
            data.get("busuk", 0),
            data.get("janjang_kosong", 0),
            data.get("brondolan_segar", 0),
            data.get("brondolan_busuk", 0),
            data.get("sampah", 0),
            data.get("abnormal", 0),
            data.get("tikus", 0),
            data.get("burung", 0),
            data.get("tupai", 0),
            data.get("tangkai_panjang", 0),
            data.get("partenocarpic", 0),
            data.get("kempet", 0),
            data.get("total_potongan_pct", 0),
        ]

        ws.append_row(row, value_input_option="USER_ENTERED")
        return True

    except Exception as e:
        st.error(f"❌ Gagal simpan ke Google Sheets: {e}")
        return False

# ===================== STEP 1 =====================
if st.session_state.step == 1:
    st.subheader("🧍 Data Identitas Pengiriman")

    with st.form("identitas_form"):
        mill = st.text_input("Mill (PT)")
        tanggal = st.date_input("Tanggal", datetime.now())
        nama_do = st.text_input("Nama DO")
        afdeling = st.text_input("Afdeling")
        blok = st.text_input("Blok")
        nama_driver = st.text_input("Nama Driver")
        plat = st.text_input("Plat Nomor")
        foto = st.file_uploader("Upload Foto Driver", type=["jpg", "jpeg", "png"])
        next_btn = st.form_submit_button("Lanjut ke Grading ➜")

    if next_btn:
        foto_url = upload_to_drive(foto, drive_folder_id="1vPgGRxquOZBAvMsY1xxBqYBcQiZdTFzK") if foto else ""
        st.session_state.identitas = {
            "mill": mill,
            "tanggal": str(tanggal),
            "nama_do": nama_do,
            "afdeling": afdeling,
            "blok": blok,
            "nama_driver": nama_driver,
            "plat": plat,
            "foto_url": foto_url
        }
        st.session_state.step = 2
        st.rerun()

# ===================== STEP 2 =====================
elif st.session_state.step == 2:
    st.subheader("🌾 Data Grading Janjang")

    with st.form("grading_form"):
        # BAGIAN A: Total Janjang
        total = st.number_input("Total Janjang Sampel", min_value=1, step=1)

        # BAGIAN B: Kondisi Janjang (sesuai PDF)
        st.markdown("#### 🍈 Kondisi Janjang (Isi Jumlah Janjang per Kondisi)")
        col1, col2, col3 = st.columns(3)

        with col1:
            mentah = st.number_input("Mentah (jjg)", min_value=0, step=1)
            mengkal = st.number_input("Mengkal (jjg)", min_value=0, step=1)
            overripe = st.number_input("Over Ripe (jjg)", min_value=0, step=1)
            busuk = st.number_input("Busuk (jjg)", min_value=0, step=1)
            janjang_kosong = st.number_input("Janjang Kosong (jjg)", min_value=0, step=1)

        with col2:
            brondolan_segar = st.number_input("Brondolan Segar (jjg)", min_value=0, step=1)
            brondolan_busuk = st.number_input("Brondolan Busuk (jjg)", min_value=0, step=1)
            sampah = st.number_input("Sampah (jjg)", min_value=0, step=1)
            abnormal = st.number_input("Abnormal (jjg)", min_value=0, step=1)
            tikus = st.number_input("Tikus >50% (jjg)", min_value=0, step=1)

        with col3:
            burung = st.number_input("Burung (jjg)", min_value=0, step=1)
            tupai = st.number_input("Tupai (jjg)", min_value=0, step=1)
            tangkai = st.number_input("Tangkai Panjang (jjg)", min_value=0, step=1)
            parteno = st.number_input("Partenocarpic (jjg)", min_value=0, step=1)
            kempet = st.number_input("Kempet (jjg)", min_value=0, step=1)

        # Tombol submit custom style (lebih kuat)
        submitted = st.form_submit_button("Hitung & Simpan")

        # CSS baru: selector sesuai struktur DOM Streamlit form terbaru
        st.markdown("""
            <style>
            /* Styling tombol submit di dalam form */
            div[data-testid="stFormSubmitButton"] button {
                background-color: #2d5a27 !important;
                color: white !important;
                width: 100% !important;
                border: none !important;
                border-radius: 6px !important;
                height: 48px !important;
                font-size: 16px !important;
                font-weight: 600 !important;
                transition: all 0.2s ease-in-out;
            }
            div[data-testid="stFormSubmitButton"] button:hover {
                background-color: #3b742f !important;
                transform: scale(1.01);
                cursor: pointer;
            }
            </style>
        """, unsafe_allow_html=True)

    if submitted:
        # Hitung persentase
        kondisi = {
            "Mentah": mentah,
            "Mengkal": mengkal,
            "Over Ripe": overripe,
            "Busuk": busuk,
            "Janjang Kosong": janjang_kosong,
            "Brondolan Segar": brondolan_segar,
            "Brondolan Busuk": brondolan_busuk,
            "Sampah": sampah,
            "Abnormal": abnormal,
            "Tikus >50%": tikus,
            "Burung": burung,
            "Tupai": tupai,
            "Tangkai Panjang": tangkai,
            "Partenocarpic": parteno,
            "Kempet": kempet
        }

        pers, pot, total_potongan = compute_values(kondisi, total)

        # =========================
        # Tampilkan hasil tabel dengan style profesional
        # =========================
        st.markdown("#### 📊 Hasil Perhitungan Persentase dan Potongan (Sesuai PDF)")

        rows_display = []
        pot_numeric = {}

        for k in kondisi.keys():
            # Ambil nilai persentase dan potongan
            perc = round(pers.get(k, 0), 2)
            pval = pot.get(k, None)
            pot_numeric[k] = round(pval, 2) if pval is not None else None

            # Format tampilan
            perc_display = f"{perc:.2f}%" if perc != 0 else "-"
            pot_display = f"{round(pval,2):.2f}%" if pval is not None and pval != 0 else "-"

            rows_display.append({
                "Kondisi": k,
                "Persentase (%)": perc_display,
                "Potongan (%)": pot_display
            })

        df_display = pd.DataFrame(rows_display)

        # Styling agar tabel tanpa nomor & lebih elegan
        st.markdown("""
        <style>
        thead tr th:first-child {display:none}
        tbody th {display:none}
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 15px;
            border: 1px solid #d1d5db;
        }
        th, td {
            text-align: center !important;
            border: 1px solid #e2e8f0 !important;
            padding: 8px !important;
        }
        th {
            background-color: #f1f5f9 !important;
            color: #0f172a !important;
            font-weight: 600 !important;
        }
        tr:nth-child(even) td {
            background-color: #f9fafb !important;
        }
        </style>
        """, unsafe_allow_html=True)

        # Render tabel tanpa index
        st.dataframe(
            df_display,
            hide_index=True,
            width="stretch"
        )

        # Total potongan
        st.markdown(
            f"<h4 style='text-align:center;color:#2d5a27;'>💯 Total Potongan Akhir: {total_potongan:.2f}%</h4>",
            unsafe_allow_html=True
        )

        # Gabungkan semua data untuk disimpan
        identitas = st.session_state.identitas
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        data_row = {
            "timestamp": timestamp,
            **identitas,
            "total_janjang": int(total),
            "mentah": int(mentah),
            "mengkal_pot": pot_numeric.get("Mengkal"),
            "overripe_pot": pot_numeric.get("Over Ripe"),
            "busuk": int(busuk),
            "janjang_kosong": int(janjang_kosong),
            "brondolan_segar": int(brondolan_segar),
            "brondolan_busuk": int(brondolan_busuk),
            "sampah": int(sampah),
            "abnormal": int(abnormal),
            "tikus_pot": pot_numeric.get("Tikus"),
            "burung": int(burung),
            "tupai": int(tupai),
            "tangkai_pot": pot_numeric.get("Tangkai Panjang"),
            "parteno_pot": pot_numeric.get("Partenocarpic"),
            "kempet": int(kempet),
            "total_potongan_pct": round(total_potongan, 2)
        }

        # Simpan ke Google Sheets
        st.info("⏳ Menyimpan ke Google Sheets...")
        sheet_url = "https://docs.google.com/spreadsheets/d/1LLRTb93VBiJgGULdktW4Bfxa8ixnJG8t6GpxzOlB6zw/edit?usp=sharing"
        if save_to_gsheets(data_row, sheet_url):
            st.success("✅ Data berhasil disimpan ke Google Sheets!")

        # Tombol kembali
        if st.button("⬅️ Kembali ke Awal"):
            st.session_state.step = 1
            st.rerun()
