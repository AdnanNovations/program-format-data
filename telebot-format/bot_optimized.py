import time
from pyrogram import Client, filters
import re
import configparser
from datetime import datetime
from collections import defaultdict
from apscheduler.schedulers.background import BackgroundScheduler
import json
import os

# Lazy import pandas only when needed
def lazy_import_pandas():
    import pandas as pd
    return pd

print("Starting the bot...")

# Membaca konfigurasi dari file config.ini
config = configparser.ConfigParser()
config.read("config.ini")

# Membaca konfigurasi Telegram
api_id = config["Telegram"].get("api_id")
api_hash = config["Telegram"].get("api_hash")
bot_token = config["Telegram"].get("bot_token")
# Membaca reset_time dari file konfigurasi
reset_time = config["Settings"].get("reset_time", "07:00")  # Default ke 07:00 jika tidak ditemukan

# Validasi konfigurasi
if not api_id or not api_hash or not bot_token:
    raise ValueError("Konfigurasi Telegram tidak lengkap. Pastikan api_id, api_hash, dan bot_token diatur.")

print("Initializing client...")
app = Client("telegram_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# Cache untuk data user - akan di-load lazy
_data_cache = {
    'admin_usernames': None,
    'user_usernames': None,
    'user_quotas': None,
    'last_loaded': None
}

# Batas permintaan per pengguna
MAX_PENDING_REQUESTS = 4

# Antrean permintaan pengguna
user_requests = defaultdict(list)

def get_cache_file():
    return "user_data_cache.json"

def save_cache():
    """Save data to cache file"""
    cache_data = {
        'admin_usernames': _data_cache['admin_usernames'],
        'user_usernames': _data_cache['user_usernames'],
        'user_quotas': _data_cache['user_quotas'],
        'timestamp': time.time()
    }
    with open(get_cache_file(), 'w') as f:
        json.dump(cache_data, f)

def load_cache():
    """Load data from cache file if fresh"""
    cache_file = get_cache_file()
    if not os.path.exists(cache_file):
        return False

    try:
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)

        # Check if cache is less than 1 hour old
        if time.time() - cache_data.get('timestamp', 0) < 3600:
            _data_cache['admin_usernames'] = cache_data['admin_usernames']
            _data_cache['user_usernames'] = cache_data['user_usernames']
            _data_cache['user_quotas'] = cache_data['user_quotas']
            _data_cache['last_loaded'] = cache_data['timestamp']
            print("Data loaded from cache")
            return True
    except:
        pass
    return False

def load_data():
    """Load data dari Excel files, dengan caching"""
    if _data_cache['admin_usernames'] is not None:
        return

    # Try to load from cache first
    if load_cache():
        return

    print("Loading data from Excel files...")
    pd = lazy_import_pandas()

    # Load admin data
    df_admin = pd.read_excel("admin.xlsx")
    _data_cache['admin_usernames'] = df_admin["Admin"].dropna().str.lower().tolist()

    # Load user data
    df_users = pd.read_excel("users.xlsx")
    _data_cache['user_usernames'] = df_users["User"].dropna().str.lower().tolist()

    # Load user quotas
    user_data = df_users[["User", "Kuota", "Kuota_Terpakai"]].dropna().copy()
    user_data["User"] = user_data["User"].str.lower()
    _data_cache['user_quotas'] = {
        row["User"]: {"Kuota": row["Kuota"], "Kuota_Terpakai": row["Kuota_Terpakai"]}
        for _, row in user_data.iterrows()
    }

    _data_cache['last_loaded'] = time.time()
    save_cache()
    print("Data loaded successfully")

def get_admin_usernames():
    load_data()
    return _data_cache['admin_usernames']

def get_user_usernames():
    load_data()
    return _data_cache['user_usernames']

def get_user_quotas():
    load_data()
    return _data_cache['user_quotas']

# Fungsi untuk membaca status bot
def get_bot_status():
    config.read("config.ini")
    mode = config["Settings"].get("mode", "normal")
    return {"mode": mode}

# Fungsi untuk menyimpan kuota pengguna ke file Excel
def save_user_data(file_path: str):
    pd = lazy_import_pandas()
    user_quotas = get_user_quotas()
    data = pd.DataFrame(
        [{"User": user, "Kuota": values["Kuota"], "Kuota_Terpakai": values["Kuota_Terpakai"]}
         for user, values in user_quotas.items()]
    )
    data.to_excel(file_path, index=False)
    # Invalidate cache after save
    _data_cache['admin_usernames'] = None
    _data_cache['user_usernames'] = None
    _data_cache['user_quotas'] = None

# Handler untuk perintah /start
@app.on_message(filters.command("start"))
def handle_start_command(client, message):
    user_name = message.from_user.first_name if message.from_user.first_name else "Pengguna"
    welcome_message = (
        f"Selamat Datang, {user_name}!\n\n"
        "Silakan ketik /help untuk mengetahui commands yang tersedia."
    )
    message.reply_text(welcome_message)

# Reset kuota pengguna
def reset_user_quotas():
    user_quotas = get_user_quotas()
    for user, values in user_quotas.items():
        user_quotas[user]["Kuota_Terpakai"] = 0
    save_user_data("users.xlsx")
    notify_admins("Kuota pengguna telah di-reset.")

@app.on_message(filters.command("quota"))
def handle_cekkuota_command(client, message):
    sender_username = message.from_user.username.lower() if message.from_user.username else None

    bot_status = get_bot_status()
    if bot_status["mode"] == "freeze":
        message.reply_text(f"Sistem Sedang Maintenance")
        return

    user_quotas = get_user_quotas()
    if sender_username not in user_quotas:
        message.reply_text("Anda tidak memiliki akses untuk menggunakan perintah ini.")
        return

    user_data = user_quotas.get(sender_username, {"Kuota": 0, "Kuota_Terpakai": 0})
    max_quota = user_data["Kuota"]
    kuota_terpakai = user_data["Kuota_Terpakai"]
    used_percentage = (kuota_terpakai / max_quota) * 100 if max_quota > 0 else 0

    message.reply_text(
        f"Penggunaan transaksi Anda {kuota_terpakai} dari {max_quota} ({used_percentage:.2f}%). Quota reset setiap jam {reset_time} WIB."
    )

# Notifikasi ke semua admin
def notify_admins(message):
    admin_usernames = get_admin_usernames()
    for admin in admin_usernames:
        try:
            app.send_message(f"@{admin}", message)
        except Exception as e:
            print(f"Gagal mengirim notifikasi ke admin {admin}: {e}")

# Cek waktu reset
def check_reset_time():
    now = datetime.now().strftime("%H:%M")
    if now == reset_time:
        reset_user_quotas()

def remove_message_by_id(user_id, message_id_to_remove):
    if user_id in user_requests:
        user_requests[user_id] = [
            request for request in user_requests[user_id] if request["message_id"] != message_id_to_remove
        ]
        if not user_requests[user_id]:
            del user_requests[user_id]

# Validasi Nomor Indonesia
def is_valid_indonesian_number(phone_number: str) -> bool:
    pattern = r"^(08\d{8,11}|62\d{8,13})$"
    return bool(re.match(pattern, phone_number))

# Handler untuk pengguna (A)
@app.on_message(filters.command("location"))
def handle_location_command(client, message):
    sender_username = message.from_user.username.lower() if message.from_user.username else None

    bot_status = get_bot_status()
    if bot_status["mode"] == "freeze":
        message.reply_text(f"Sistem Sedang Maintenance")
        return

    user_usernames = get_user_usernames()
    if sender_username not in user_usernames:
        message.reply_text("Anda tidak memiliki akses untuk menggunakan perintah ini.")
        return

    user_id = message.from_user.id

    if len(user_requests[user_id]) >= MAX_PENDING_REQUESTS:
        message.reply_text("HARAP MENUNGGU, ADA PERMINTAAN BELUM TERPROSES.")
        return

    if len(message.command) < 2:
        message.reply_text("Format salah. Gunakan: /location <nomor>")
        return

    phone_number = message.command[1]

    if not is_valid_indonesian_number(phone_number):
        message.reply_text("Nomor tidak valid! Pastikan menggunakan format nomor Indonesia.")
        return

    user_quotas = get_user_quotas()
    if user_quotas.get(sender_username, {"Kuota": 0, "Kuota_Terpakai": 0})["Kuota_Terpakai"] >= \
            user_quotas.get(sender_username, {"Kuota": 0, "Kuota_Terpakai": 0})["Kuota"]:
        message.reply_text("KUOTA PENCARIAN ANDA HABIS.")
        return

    user_quotas[sender_username]["Kuota_Terpakai"] += 1
    save_user_data("users.xlsx")

    user_requests[user_id].append({"phone_number": phone_number, "message_id": message.id})

    client.send_message(
        chat_id=message.chat.id,
        text="PENCARIAN SEDANG DIMULAI",
        reply_to_message_id=message.id
    )

    admin_usernames = get_admin_usernames()
    for admin_username in admin_usernames:
        client.send_message(f"@{admin_username}", f"/location {phone_number}")

# [Continue with other handlers - keeping them the same for now]
@app.on_message(filters.command("lm"))
def handle_lm_command(client, message):
    # Implementation sama seperti sebelumnya, tapi gunakan get_user_usernames() dan get_user_quotas()
    pass

@app.on_message(filters.command("locimei"))
def handle_locimei_command(client, message):
    # Implementation sama seperti sebelumnya
    pass

# Validasi IMEI
def is_valid_imei(imei: str) -> bool:
    return imei.isdigit() and len(imei) == 14

# [Continue with format_data functions and other handlers...]

print("Starting scheduler...")
# Inisialisasi jadwal dengan apscheduler - defer startup
def init_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_reset_time, "interval", minutes=1)
    scheduler.start()
    return scheduler

print("Bot ready to start!")
app.run()