# Telegram Bot - Location Tracking

Bot Telegram untuk tracking lokasi berdasarkan nomor HP, IMEI, dan lini masa dengan berbagai format data input.

## Fitur

- **Location Tracking** (`/location`) - Tracking lokasi berdasarkan nomor HP
- **IMEI Tracking** (`/locimei`) - Tracking lokasi berdasarkan IMEI
- **Timeline Tracking** (`/lm`) - Lini masa Telkomsel
- **Quota Management** - Sistem kuota pengguna dengan reset otomatis
- **Multi-format Data Support** - Mendukung berbagai format input data

## Format Data yang Didukung

Bot dapat memproses berbagai format data input:

### Format 1 - Basic
```
MSISDN: 6285649499864
Age: kurang dari 1 menit
LAC: 42002
CI: 571599
CGI: 510-01-42002-571599
Device: SAMSUNG Galaxy M54 5G
Operator: INDOSAT
```

### Format 2 - Extended
```
:: RESULT FOR 085866871XXX ::.
MSISDN : 6285866871XXX
PROVIDER : INDOSAT OOREDOO
LATITUDE : -7.57478
LONGITUDE : 110.71600
CGI : 510-01-30032-8478209
```

## Requirements

- Python 3.12+ (menggunakan venv)
- Dependencies dalam `requirements.txt`

## Setup

1. **Clone repository**
   ```bash
   git clone <repository-url>
   cd telebot-format
   ```

2. **Aktivasi virtual environment**
   ```bash
   source .venv/Scripts/activate  # Windows
   # atau
   source .venv/bin/activate      # Linux/Mac
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Konfigurasi**
   - Edit `config.ini` dengan API credentials Telegram
   - Update `admin.xlsx` dengan daftar admin
   - Update `users.xlsx` dengan daftar user dan kuota

## Build Instructions

### Prerequisites
Pastikan virtual environment aktif sebelum build:
```bash
source .venv/Scripts/activate
```

### Build Bot Executable

**Method 1: Single File (Recommended)**
```bash
python -m PyInstaller --onefile \
  --collect-all pandas \
  --collect-all pyrogram \
  --collect-all openpyxl \
  --collect-all apscheduler \
  --add-data "config.ini;." \
  --add-data "admin.xlsx;." \
  --add-data "users.xlsx;." \
  --name=bot bot.py
```

**Method 2: Directory Mode (Faster Loading)**
```bash
python -m PyInstaller --onedir \
  --collect-all pandas \
  --collect-all pyrogram \
  --collect-all openpyxl \
  --collect-all apscheduler \
  --add-data "config.ini;." \
  --add-data "admin.xlsx;." \
  --add-data "users.xlsx;." \
  --name=bot bot.py
```

### Build GUI Executable
```bash
python -m PyInstaller --onefile \
  --windowed \
  --name=gui gui.py
```

### Clean Build (jika diperlukan)
```bash
python -m PyInstaller --clean bot.spec
```

## Output

Build akan menghasilkan file di folder `dist/`:
- `bot.exe` - Bot Telegram executable
- `gui.exe` - GUI interface
- File konfigurasi dan data

## Testing

Test executable sebelum distribusi:
```bash
cd dist
timeout 3 ./bot.exe  # Test 3 detik
```

## Dependencies

### Core Dependencies
- `pyrogram` - Telegram API client
- `pandas` - Data processing
- `openpyxl` - Excel file handling
- `apscheduler` - Task scheduling
- `TgCrypto` - Pyrogram speed optimization

### Build Dependencies
- `pyinstaller` - Executable builder

## Notes

- **PENTING:** Selalu gunakan virtual environment saat build
- Bot membutuhkan `config.ini` dengan kredensial Telegram yang valid
- File session akan dibuat otomatis saat pertama kali dijalankan
- Sistem kuota reset otomatis setiap hari sesuai `reset_time` di config

## Troubleshooting

### Import Error saat menjalankan executable
```
ModuleNotFoundError: No module named 'pandas'
```
**Solusi:** Pastikan build menggunakan venv yang aktif

### File konfigurasi tidak ditemukan
**Solusi:** Pastikan `config.ini`, `admin.xlsx`, dan `users.xlsx` ada di folder yang sama dengan executable

### Bot tidak merespons
**Solusi:** Cek kredensial API di `config.ini` dan koneksi internet

## Changelog

### Latest Updates
- ✅ Support format data baru dengan Device field
- ✅ Extract LAC-CID dari CGI format lengkap
- ✅ Handle "kurang dari 1 menit" → "0 menit"
- ✅ Extract Operator ke field NETWORK
- ✅ Multi-format data input support

## License

[Sesuaikan dengan lisensi project Anda]