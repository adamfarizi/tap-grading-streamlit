# 🧾 Kalkulator Grading - PT EBL Mill

Aplikasi berbasis **Streamlit** untuk menghitung dan mencatat hasil **grading janjang TBS (Tandan Buah Segar)** secara otomatis ke **Google Sheets**, dengan dukungan upload foto driver langsung ke **Google Drive**.

---

## 🚀 Fitur Utama

✅ **2 Tahap Input Data**
- **Langkah 1:** Identitas Pengiriman  
  (Mill, Nama DO, Afdeling, Blok, Driver, Plat, dan Foto Driver)
- **Langkah 2:** Grading Janjang  
  (Isian jumlah janjang per kondisi sesuai form resmi PDF)

✅ **Perhitungan Otomatis**
- Menghitung persentase tiap kondisi terhadap total janjang
- Menghitung potongan otomatis sesuai rumus resmi PT EBL Mill:
  - Mengkal → `0.5 × %Mengkal`
  - Over Ripe → `0.25 × (%OverRipe - 5)`
  - Tikus >50% → `0.15 × %Tikus`
  - Tangkai Panjang → `0.01 × %TangkaiPanjang`
  - Partenocarpic → `0.15 × %Partenocarpic`
  - Total Potongan = `2% + (semua potongan di atas)`

✅ **Integrasi Cloud**
- Upload foto otomatis ke Google Drive  
- Simpan hasil ke Google Sheets  
- URL foto otomatis tersimpan di spreadsheet

✅ **Desain Profesional**
- Tampilan rapi, dengan warna khas PT EBL (hijau #2d5a27)
- Struktur form seperti di PDF grading form resmi
- Tampilan tabel hasil yang clean tanpa nomor urut

---

## ⚙️ Persiapan Sebelum Menjalankan

### 1️⃣ Aktifkan API di Google Cloud Console
Pastikan API berikut **aktif** di project Google Cloud kamu:
- [Google Drive API](https://console.cloud.google.com/apis/library/drive.googleapis.com)
- [Google Sheets API](https://console.cloud.google.com/apis/library/sheets.googleapis.com)

### 2️⃣ Buat Service Account
1. Masuk ke [Google Cloud Console → IAM & Admin → Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts)
2. Klik **Create Service Account**
3. Download file **JSON key** → simpan sebagai `service_account.json`
4. Tambahkan email service account ke **folder Google Drive kamu** dengan akses **Editor**

### 3️⃣ Tambahkan ke Streamlit Secrets
Buat file `.streamlit/secrets.toml` dan isi:

```toml
[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "your-private-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY\n-----END PRIVATE KEY-----\n"
client_email = "service-account@your-project-id.iam.gserviceaccount.com"
client_id = "your-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/service-account@your-project-id.iam.gserviceaccount.com"
