import time
from pyrogram import Client, filters
import re
import pandas as pd
import configparser
from datetime import datetime
from collections import defaultdict
from apscheduler.schedulers.background import BackgroundScheduler

# Membaca konfigurasi dari file config.ini
config = configparser.ConfigParser()
config.read("config.ini")

# Membaca konfigurasi Telegram
api_id = config["Telegram"].get("api_id")
api_hash = config["Telegram"].get("api_hash")
bot_token = config["Telegram"].get("bot_token")
# Membaca reset_time dari file konfigurasi
reset_time = config["Settings"].get("reset_time", "07:00")  # Default ke 07:00 jika tidak ditemukan

# Fungsi untuk membaca status bot
def get_bot_status():
    config.read("config.ini")
    mode = config["Settings"].get("mode", "normal")
    return {"mode": mode}

# Validasi konfigurasi
if not api_id or not api_hash or not bot_token:
    raise ValueError("Konfigurasi Telegram tidak lengkap. Pastikan api_id, api_hash, dan bot_token diatur.")

print("Starting the bot...")
app = Client("telegram_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)
print("Client initialized.")

# Batas permintaan per pengguna
MAX_PENDING_REQUESTS = 4

# Antrean permintaan pengguna
user_requests = defaultdict(list)

# Handler untuk perintah /start
@app.on_message(filters.command("start"))
def handle_start_command(client, message):
    # Ambil nama pengguna (jika ada)
    user_name = message.from_user.first_name if message.from_user.first_name else "Pengguna"

    # Kirim pesan selamat datang
    welcome_message = (
        f"Selamat Datang, {user_name}!\n\n"
        "Silakan ketik /help untuk mengetahui commands yang tersedia."
    )
    message.reply_text(welcome_message)

# Fungsi untuk membaca file admin.xlsx
def load_admin_data(file_path: str):
    df = pd.read_excel(file_path)  # Membaca file Excel
    l_admin_usernames = df["Admin"].dropna().str.lower().tolist()  # Ambil kolom Admin
    return l_admin_usernames

# Fungsi untuk membaca file admin.xlsx
def load_user_data(file_path: str):
    df = pd.read_excel(file_path)  # Membaca file Excel
    l_user_usernames = df["User"].dropna().str.lower().tolist()  # Ambil kolom Admin
    return l_user_usernames

# Fungsi untuk menyimpan kuota pengguna ke file Excel
def save_user_data(file_path: str):
    data = pd.DataFrame(
        [{"User": user, "Kuota": values["Kuota"], "Kuota_Terpakai": values["Kuota_Terpakai"]} for user, values in user_quotas.items()]
    )
    data.to_excel(file_path, index=False)

# Fungsi untuk membaca file users.xlsx
def load_user_quotas(file_path: str):
    df = pd.read_excel(file_path)  # Membaca file Excel
    user_data = df[["User", "Kuota", "Kuota_Terpakai"]].dropna().copy()
    user_data["User"] = user_data["User"].str.lower()
    l_user_quotas = {row["User"]: {"Kuota": row["Kuota"], "Kuota_Terpakai": row["Kuota_Terpakai"]}
                     for _, row in user_data.iterrows()}
    return l_user_quotas

# Load data dari file
admin_usernames = load_admin_data("admin.xlsx")
user_usernames = load_user_data("users.xlsx")
user_quotas = load_user_quotas("users.xlsx")

# Reset kuota pengguna
def reset_user_quotas():
    global user_quotas
    for user, values in user_quotas.items():
        # Reset Kuota_Terpakai ke 0, namun Kuota tetap mengikuti nilai yang ada di file
        user_quotas[user]["Kuota_Terpakai"] = 0

    save_user_data("users.xlsx")  # Simpan perubahan ke file Excel
    notify_admins("Kuota pengguna telah di-reset.")


@app.on_message(filters.command("quota"))
def handle_cekkuota_command(client, message):
    # Ambil username pengirim
    sender_username = message.from_user.username.lower() if message.from_user.username else None

    # Periksa mode bot
    bot_status = get_bot_status()
    if bot_status["mode"] == "freeze":
        message.reply_text(f"Sistem Sedang Maintenance")
        return

    # Periksa apakah pengguna termasuk dalam daftar user
    if sender_username not in user_quotas:
        message.reply_text("Anda tidak memiliki akses untuk menggunakan perintah ini.")
        return

    # Ambil kuota dan kuota terpakai dari user_quotas
    user_data = user_quotas.get(sender_username, {"Kuota": 0, "Kuota_Terpakai": 0})
    max_quota = user_data["Kuota"]  # Kuota maksimal dari field "Kuota"
    kuota_terpakai = user_data["Kuota_Terpakai"]  # Kuota yang sudah terpakai

    # Hitung persentase kuota yang terpakai
    used_percentage = (kuota_terpakai / max_quota) * 100 if max_quota > 0 else 0

    # Kirim respons kuota ke pengguna
    message.reply_text(
        f"Penggunaan transaksi Anda {kuota_terpakai} dari {max_quota} ({used_percentage:.2f}%). Quota reset setiap jam {reset_time} WIB."
    )

# Notifikasi ke semua admin
def notify_admins(message):
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
        # Filter out the message with the specified message_id
        user_requests[user_id] = [
            request for request in user_requests[user_id] if request["message_id"] != message_id_to_remove
        ]
        # Optional: Remove user_id key if the list is empty
        if not user_requests[user_id]:
            del user_requests[user_id]

# Inisialisasi jadwal dengan apscheduler
scheduler = BackgroundScheduler()
scheduler.add_job(check_reset_time, "interval", minutes=1)
scheduler.start()

# Validasi Nomor Indonesia
def is_valid_indonesian_number(phone_number: str) -> bool:
    pattern = r"^(08\d{8,11}|62\d{8,13})$"
    return bool(re.match(pattern, phone_number))

# Handler untuk pengguna (A)
@app.on_message(filters.command("location"))
def handle_location_command(client, message):
    # Ambil username pengirim
    sender_username = message.from_user.username.lower() if message.from_user.username else None

    # Periksa mode bot
    bot_status = get_bot_status()
    if bot_status["mode"] == "freeze":
        message.reply_text(f"Sistem Sedang Maintenance")
        return

    # Periksa apakah pengguna termasuk dalam daftar user
    if sender_username not in user_usernames:
        message.reply_text("Anda tidak memiliki akses untuk menggunakan perintah ini.")
        return

    user_id = message.from_user.id

    # Cek jumlah permintaan aktif
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

    # Cek kuota user
    if user_quotas.get(sender_username, {"Kuota": 0, "Kuota_Terpakai": 0})["Kuota_Terpakai"] >= \
            user_quotas.get(sender_username, {"Kuota": 0, "Kuota_Terpakai": 0})["Kuota"]:
        message.reply_text("KUOTA PENCARIAN ANDA HABIS.")
        return

    # Kurangi kuota user
    user_quotas[sender_username]["Kuota_Terpakai"] += 1  # Tambahkan 1 ke kuota yang terpakai
    save_user_data("users.xlsx")  # Simpan perubahan ke file Excel

    # Tambahkan permintaan ke antrean
    user_requests[user_id].append({"phone_number": phone_number, "message_id": message.id})
    user_requests[user_id].append({"phone_number": phone_number, "message_id": message.id})

    # Kirim notifikasi dan permintaan ke admin
    client.send_message(
        chat_id=message.chat.id,
        text="PENCARIAN SEDANG DIMULAI",
        reply_to_message_id=message.id
    )

    # Kirim permintaan ke admin
    for admin_username in admin_usernames:
        client.send_message(f"@{admin_username}", f"/location {phone_number}")

# Handler untuk pengguna (A)
@app.on_message(filters.command("lm"))
def handle_lm_command(client, message):
    # Ambil username pengirim
    sender_username = message.from_user.username.lower() if message.from_user.username else None

    # Periksa mode bot
    bot_status = get_bot_status()
    if bot_status["mode"] == "freeze":
        message.reply_text(f"Sistem Sedang Maintenance")
        return

    # Periksa apakah pengguna termasuk dalam daftar user
    if sender_username not in user_usernames:
        message.reply_text("Anda tidak memiliki akses untuk menggunakan perintah ini.")
        return

    user_id = message.from_user.id

    # Cek jumlah permintaan aktif
    if len(user_requests[user_id]) >= MAX_PENDING_REQUESTS:
        message.reply_text("HARAP MENUNGGU, ADA PERMINTAAN BELUM TERPROSES.")
        return

    if len(message.command) < 2:
        message.reply_text("Format salah. Gunakan: /lm <nomor>")
        return

    phone_number = message.command[1]

    if not is_valid_indonesian_number(phone_number):
        message.reply_text("Nomor tidak valid! Pastikan menggunakan format nomor Indonesia.")
        return

    # Cek kuota user
    user_quota = user_quotas.get(sender_username, {"Kuota": 0, "Kuota_Terpakai": 0})
    if user_quota["Kuota_Terpakai"] >= user_quota["Kuota"]:
        message.reply_text("KUOTA PENCARIAN ANDA HABIS.")
        return

    # Kurangi kuota user
    user_quotas[sender_username]["Kuota_Terpakai"] += 1
    save_user_data("users.xlsx")  # Simpan perubahan ke file Excel

    # Tambahkan permintaan ke antrean
    if user_id not in user_requests:
        user_requests[user_id] = []

    user_requests[user_id].append({"phone_number": phone_number, "message_id": message.id})
    user_requests[user_id].append({"phone_number": phone_number, "message_id": message.id})

    # Kirim notifikasi dan permintaan ke admin
    client.send_message(
        chat_id=message.chat.id,
        text="PENCARIAN SEDANG DIMULAI",
        reply_to_message_id=message.id
    )

    # Kirim permintaan ke admin
    for admin_username in admin_usernames:
        client.send_message(f"@{admin_username}", f"/lm {phone_number}")

# Validasi IMEI
def is_valid_imei(imei: str) -> bool:
    return imei.isdigit() and len(imei) == 14

# Handler untuk pengguna (A)
@app.on_message(filters.command("locimei"))
def handle_locimei_command(client, message):
    # Ambil username pengirim
    sender_username = message.from_user.username.lower() if message.from_user.username else None

    # Periksa mode bot
    bot_status = get_bot_status()
    if bot_status["mode"] == "freeze":
        message.reply_text(f"Sistem Sedang Maintenance")
        return

    # Periksa apakah pengguna termasuk dalam daftar user
    if sender_username not in user_usernames:
        message.reply_text("Anda tidak memiliki akses untuk menggunakan perintah ini.")
        return

    user_id = message.from_user.id

    # Cek jumlah permintaan aktif
    if len(user_requests[user_id]) >= MAX_PENDING_REQUESTS:
        message.reply_text("HARAP MENUNGGU, ADA PERMINTAAN BELUM TERPROSES.")
        return

    if len(message.command) < 2:
        message.reply_text("Format salah. Gunakan: /locimei <14_digit_imei>")
        return

    imei_number = message.command[1]

    if not is_valid_imei(imei_number):
        message.reply_text("IMEI tidak valid! Pastikan IMEI terdiri dari 14 angka.")
        return

    # Cek kuota user
    if user_quotas.get(sender_username, {"Kuota": 0, "Kuota_Terpakai": 0})["Kuota_Terpakai"] >= \
            user_quotas.get(sender_username, {"Kuota": 0, "Kuota_Terpakai": 0})["Kuota"]:
        message.reply_text("KUOTA PENCARIAN ANDA HABIS.")
        return

    # Kurangi kuota user
    user_quotas[sender_username]["Kuota_Terpakai"] += 1  # Tambahkan 1 ke kuota yang terpakai
    save_user_data("users.xlsx")  # Simpan perubahan ke file Excel

    # Tambahkan permintaan ke antrean
    user_requests[user_id].append({"imei": imei_number, "message_id": message.id})
    user_requests[user_id].append({"imei": imei_number, "message_id": message.id})

    # Kirim notifikasi dan permintaan ke admin
    client.send_message(
        chat_id=message.chat.id,
        text="PENCARIAN SEDANG DIMULAI",
        reply_to_message_id=message.id
    )

    # Kirim permintaan ke admin
    for admin_username in admin_usernames:
        client.send_message(f"@{admin_username}", f"/locimei {imei_number}")

# Handler untuk admin (B)
@app.on_message(filters.reply)
def handle_reply_from_admin(client, message):
    sender_username = message.from_user.username.lower() if message.from_user.username else None

    # Periksa apakah pengirim adalah admin
    if sender_username not in admin_usernames:
        message.reply_text("Anda tidak memiliki akses untuk membalas permintaan ini.")
        return

    if message.reply_to_message:
        original_message = message.reply_to_message.text

        if original_message.startswith("/lm "):
            phone_number = original_message.split("/lm ")[-1].strip()

            # Cari pengguna dan permintaan terkait
            user_id, request_data = next(
                ((uid, req) for uid, requests in user_requests.items() for req in requests if
                 req["phone_number"] == phone_number),
                (None, None)
            )

            if user_id and request_data:
                # Jika admin membalas dengan "off"
                if message.text.lower() == "off":
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    static_response = (
                        f"PENCARIAN LINI MASA\n"
                        f"MSISDN {phone_number}\n\n"
                        f"{now}\n\n"
                        "Tidak ada data saat ini."
                    )
                    client.send_message(
                        chat_id=user_id,
                        text=static_response,
                        reply_to_message_id=request_data["message_id"]
                    )

                    # Hapus permintaan dari antrean
                    user_requests[user_id].remove(request_data)
                elif message.text.lower() == "lmoff":
                    static_response = (
                        f"PENCARIAN LINI MASA "
                        f"{phone_number} Tidak Dapat Kami Temukan"
                    )
                    client.send_message(
                        chat_id=user_id,
                        text=static_response,
                        reply_to_message_id=request_data["message_id"]
                    )

                    # Hapus permintaan dari antrean
                    user_requests[user_id].remove(request_data)
                elif message.text.lower() == "full":
                    response = (
                        f"PENCARIAN LINI MASA\n"
                        f"MSISDN {phone_number}\n\n"
                        f"SAAT INI QUOTA SUDAH HABIS, SILAHKAN MENUNGGU DIATAS JAM {reset_time} WIB"
                    )
                    client.send_message(
                        chat_id=user_id,
                        text=response,
                        reply_to_message_id=request_data["message_id"]
                    )

                    # Hapus permintaan dari antrean
                    user_requests[user_id].remove(request_data)
                elif message.text.lower() == "slow":
                    response = (
                        f"PENCARIAN LINI MASA\n"
                        f"MSISDN {phone_number}\n\n"
                        "SAAT INI PERMINTAAN ANDA SEDANG DALAM ANTRIAN, MOHON MENUNGGU, TERIMAKASIH!!!"
                    )
                    client.send_message(
                        chat_id=user_id,
                        text=response,
                        reply_to_message_id=request_data["message_id"]
                    )
                else:
                    # Format data dan balas langsung ke pesan pengguna jika bukan kata kunci khusus
                    formatted_response = format_data_lm(message.text)
                    client.send_message(
                        chat_id=user_id,
                        text=formatted_response,
                        reply_to_message_id=request_data["message_id"]
                    )

                    # Hapus permintaan dari antrean
                    user_requests[user_id].remove(request_data)

        # Handler untuk /location
        elif original_message.startswith("/location "):
            phone_number = original_message.split("/location ")[-1].strip()

            # Cari pengguna dan permintaan terkait
            user_id, request_data = next(
                ((uid, req) for uid, requests in user_requests.items() for req in requests if req["phone_number"] == phone_number),
                (None, None)
            )

            if user_id and request_data:
                if message.text.lower() == "off":
                    now = datetime.now().strftime("%d-%m-%Y %H:%M")
                    static_response = (
                        f"{now}\n\n"
                        f"IMEI: {phone_number}\n"
                        "Device : NULL NULL NULL\n"
                        "Age : NULL mins\n"
                        "IMSI : NULL\n"
                        "LAC-CID : NULL - NULL\n"
                        "NETWORK : -\n\n"
                        "ALAMAT : PROP:NULL|KAB:NULL|KEC:NULL|KEL:NULL\n"
                        "http://maps.google.com/?q=NULL,NULL"
                    )
                    client.send_message(
                        chat_id=user_id,
                        text=static_response,
                        reply_to_message_id=request_data["message_id"]
                    )

                    # Hapus permintaan dari antrean
                    user_requests[user_id].remove(request_data)
                elif message.text.lower() == "full":
                    response = (
                        f"{phone_number}\n\n"
                        f"SAAT INI QUOTA SUDAH HABIS, SILAHKAN MENUNGGU DIATAS JAM {reset_time} WIB"
                    )
                    client.send_message(
                        chat_id=user_id,
                        text=response,
                        reply_to_message_id=request_data["message_id"]
                    )

                    # Hapus permintaan dari antrean
                    user_requests[user_id].remove(request_data)
                elif message.text.lower() == "slow":
                    response = (
                        f"{phone_number}\n\n"
                        "SAAT INI PERMINTAAN ANDA SEDANG DALAM ANTRIAN, MOHON MENUNGGU, TERIMAKASIH!!!"
                    )
                    client.send_message(
                        chat_id=user_id,
                        text=response,
                        reply_to_message_id=request_data["message_id"]
                    )
                else:
                    # Format data dan balas langsung ke pesan pengguna jika bukan kata kunci khusus
                    formatted_response = format_data(message.text)
                    client.send_message(
                        chat_id=user_id,
                        text=formatted_response,
                        reply_to_message_id=request_data["message_id"]
                    )

                    # Hapus permintaan dari antrean
                    user_requests[user_id].remove(request_data)

        # Handler untuk /locimei
        elif original_message.startswith("/locimei "):
            imei_number = original_message.split("/locimei ")[-1].strip()

            # Cari pengguna dan permintaan terkait
            user_id, request_data = next(
                ((uid, req) for uid, requests in user_requests.items() for req in requests if req["imei"] == imei_number),
                (None, None)
            )

            if user_id and request_data:
                if message.text.lower() == "off":
                    now = datetime.now().strftime("%d-%m-%Y %H:%M")
                    static_response = (
                        f"{now}\n\n"
                        f"IMEI: {imei_number}\n"
                        "Device : NULL NULL NULL\n"
                        "Age : NULL mins\n"
                        "IMSI : NULL\n"
                        "LAC-CID : NULL - NULL\n"
                        "NETWORK : -\n\n"
                        "ALAMAT : PROP:NULL|KAB:NULL|KEC:NULL|KEL:NULL\n"
                        "http://maps.google.com/?q=NULL,NULL"
                    )
                    client.send_message(
                        chat_id=user_id,
                        text=static_response,
                        reply_to_message_id=request_data["message_id"]
                    )

                    # Hapus permintaan dari antrean
                    user_requests[user_id].remove(request_data)
                elif message.text.lower() == "full":
                    response = (
                        f"{imei_number}\n\n"
                        f"SAAT INI QUOTA SUDAH HABIS, SILAHKAN MENUNGGU DIATAS JAM {reset_time} WIB"
                    )
                    client.send_message(
                        chat_id=user_id,
                        text=response,
                        reply_to_message_id=request_data["message_id"]
                    )

                    # Hapus permintaan dari antrean
                    user_requests[user_id].remove(request_data)
                elif message.text.lower() == "slow":
                    response = (
                        f"{imei_number}\n\n"
                        "SAAT INI PERMINTAAN ANDA SEDANG DALAM ANTRIAN, MOHON MENUNGGU, TERIMAKASIH!!!"
                    )
                    client.send_message(
                        chat_id=user_id,
                        text=response,
                        reply_to_message_id=request_data["message_id"]
                    )
                else:
                    # Format data dan balas langsung ke pesan pengguna jika bukan kata kunci khusus
                    formatted_response = format_data(message.text)
                    client.send_message(
                        chat_id=user_id,
                        text=formatted_response,
                        reply_to_message_id=request_data["message_id"]
                    )

                    # Hapus permintaan dari antrean
                    user_requests[user_id].remove(request_data)

        else:
            message.reply_text("Pesan ini bukan balasan yang diharapkan.")
    else:
        message.reply_text("Silakan balas pesan dengan format yang benar.")

@app.on_message(filters.command("help"))
def handle_help_command(client, message):
    # Ambil username pengirim pesan
    sender_username = message.from_user.username.lower() if message.from_user.username else None

    # Periksa apakah pengirim adalah admin
    if sender_username in admin_usernames:
        # Tampilkan menu untuk admin
        help_text_admin = """
Silahkan pilih menu berikut:
/admin - Untuk mengecek status Anda sebagai admin
/P [pesan] - Untuk pengumuman
off
lmoff
full
slow
/help - Melihat daftar perintah
"""
        message.reply_text(help_text_admin)
    else:
        # Tampilkan menu untuk user
        help_text_user = """
SELAMAT DATANG BRO
Silahkan pilih menu berikut:
/location [nohp] - Untuk cek no hp
/locimei [noimei] - Untuk trace IMEI
/lm [nohp] - Linimasa Telkomsel
/quota - Melihat informasi kuota dan pemakaian harian
/help - Melihat daftar perintah
SELAMAT BERTUGAS
"""
        message.reply_text(help_text_user)

@app.on_message(filters.command("admin") & filters.private)
def handle_admin_command(client, message):
    sender_username = message.from_user.username.lower() if message.from_user.username else None

    # Periksa apakah pengirim adalah admin
    if sender_username in admin_usernames:
        message.reply_text("✅ Anda adalah admin.")
    else:
        message.reply_text("❌ Anda bukan admin. Akses ditolak.")

# Handler untuk perintah pengumuman dari admin
@app.on_message(filters.command("P") & filters.private)
def handle_announcement(client, message):
    sender_username = message.from_user.username.lower() if message.from_user.username else None

    # Periksa apakah pengirim adalah admin
    if sender_username not in admin_usernames:
        message.reply_text("Anda tidak memiliki akses untuk menggunakan perintah ini.")
        return

    # Periksa apakah ada pesan pengumuman
    if len(message.command) < 2:
        message.reply_text("Format salah. Gunakan: /P [pesan pengumuman]")
        return

    # Gabungkan pesan setelah perintah
    announcement_message = " ".join(message.command[1:])

    # Kirim pengumuman ke semua user
    failed_users = []
    for username in user_usernames:
        try:
            for _ in range(10):  # Loop 10 times
                client.send_message(f"@{username}", f"📢 PENGUMUMAN: {announcement_message}")
                time.sleep(1)  # Wait for 1 second before sending the next message
        except Exception as e:
            failed_users.append(username)

    # Feedback ke admin
    if not failed_users:
        message.reply_text("Pengumuman berhasil dikirim ke semua pengguna.")
    else:
        failed_list = ", ".join(failed_users)
        message.reply_text(f"Pengumuman gagal dikirim ke pengguna berikut: {failed_list}")

def format_data(input_text):
    lines = input_text.split("\n")

    def get_value(keywords):
        for keyword in keywords:
            line = next((line for line in lines if keyword in line), None)
            if line:
                return (
                    line.split(": ", 1)[-1]
                    or line.split(" : ", 1)[-1]
                    or line.split(":", 1)[-1]
                ).strip()
        return "-"
    
    # Remove the line containing "🕵️ Hasil MSISDN Tracking" if it exists
    lines = [line for line in lines if "🕵️ Hasil MSISDN Tracking" not in line]

    # Fetch values using multiple keywords for flexibility
    # remove unneeded text if exists 🕵️ Hasil MSISDN Tracking
    msisdn_line = next((line for line in lines if line.startswith(".:: RESULT FOR")), None)
    msisdn = (
        msisdn_line.split("RESULT FOR ")[-1].replace(" ::.", "").strip()
        if msisdn_line
        else get_value(["MSISDN"])
    )
    
    date = get_value(["TANGGAL"])
    age = get_value(["Age", "Usia", "AGE", "USIA"])
    lac = get_value(["LAC"])
    ci = get_value(["CI"])
    cgi = get_value(["CGI"])
    imsi = get_value(["IMSI"])
    imei = get_value(["IMEI"])
    kelurahan = get_value(["KELURAHAN"])
    kecamatan = get_value(["KECAMATAN"])
    kab_kota = get_value(["KAB/KOTA", "KOTA"])
    provinsi = get_value(["PROVINSI"])
    perangkat = get_value(["Perangkat"])
    operator = get_value(["Operator", "PROVIDER"])
    map_link = get_value(["Map", "Maps", "MAP", "Peta", "PETA", "MAPS"])
    tower_link = get_value(["Tower"])
    # Try to get coordinates from KOORDINAT field first
    koordinat = get_value(["KOORDINAT"])
    if koordinat and koordinat != "-":
        try:
            latitude, longitude = koordinat.split(",")
            latitude = latitude.strip()
            longitude = longitude.strip()
        except:
            # Fallback to individual LAT/LONG fields if KOORDINAT parsing fails
            latitude = get_value(["LAT", "LATITUDE", "Lat"])
            longitude = get_value(["LONG", "LONGITUDE", "Long"])
    else:
        # If no KOORDINAT field, try individual LAT/LONG fields
        latitude = get_value(["LAT", "LATITUDE", "Lat"]) 
        longitude = get_value(["LONG", "LONGITUDE", "Long"])
    

    # Address parsing logic
    address = f"""
{kelurahan + ", " if kelurahan else ""}
{kecamatan + ", " if kecamatan else ""}
{kab_kota + ", " if kab_kota else ""}
{provinsi if provinsi else ""}
""".strip() or "-"

    alamat_raw = get_value(["Alamat", "ALAMAT"])
    if alamat_raw:
        # Hapus header yang tidak relevan seperti "=====- Alamat -======"
        alamat_raw = alamat_raw.replace("=====- Alamat -======", "").strip()

        # Periksa apakah format masukan sesuai dengan pola "PROP", "KAB", "KEC", "KEL"
        if any(x in alamat_raw for x in ["PROP", "KAB", "KEC", "KEL"]):
            address_components = {}
            for part in alamat_raw.split("|"):
                if ":" in part:  # Pastikan ada pemisah label dan nilai
                    label, value = part.split(":", 1)
                    address_components[label.strip()] = value.strip()
            address = f"""
    {address_components.get("PROP", "")}
    {address_components.get("KAB", "") + ", " if "KAB" in address_components else ""}
    {address_components.get("KEC", "") + ", " if "KEC" in address_components else ""}
    {address_components.get("KEL", "") + ", " if "KEL" in address_components else ""}
    """.strip()
        else:
            # Jika format tidak sesuai, gunakan data mentah tanpa modifikasi
            address = alamat_raw.strip()
    else:
        # Gunakan "-" jika tidak ada alamat
        address = "-"

    # Generate final output
    output = f"""
{msisdn}
Device : {perangkat or "-"}
Age : {age or "-"}
IMEI : {imei or "-"}
IMSI : {imsi or "-"}
LAC-CID : {lac + "-" + ci if lac and ci else cgi or "-"}
NETWORK : {operator or "-"}
\nALAMAT : {address}
Tanggal : {date}
"""

    # Handle tower_link, map_link, and coordinates
    if tower_link != "-":
        output += f"\nMap: {tower_link}" if tower_link and tower_link.strip() != "-" else ""
        output += f"\n\nAzimut Target: {map_link}" if map_link and map_link.strip() != "-" else ""
    else:
        output += f"\nMap: {map_link}" if map_link and map_link.strip() != "-" else ""

    # Jika map_link kosong, cek apakah ada koordinat (latitude dan longitude)
    if not map_link and latitude and longitude:
        output += f"\nMap: https://maps.google.com/maps?q={latitude},{longitude}"

    output = output.strip()
    return output


def format_data_lm(raw_text):
    # Pisahkan teks menjadi baris-baris
    lines = raw_text.strip().split("\n")

    # Buat variabel untuk menyimpan hasil format
    formatted_lines = []

    for line in lines:
        # Tambahkan baris ke hasil jika belum mencapai tulisan tidak diperlukan
        formatted_lines.append(line)
        # Hentikan jika mendeteksi pola "Geolocation" pada baris terakhir
        if "Geolocation" in line:
            last_relevant_line = line

    # Buang tulisan setelah data terakhir (jika ada)
    result = []
    for line in formatted_lines:
        result.append(line)
        if line == last_relevant_line:
            break

    # Gabungkan kembali hasil menjadi teks
    return "\n".join(result)

app.run()
