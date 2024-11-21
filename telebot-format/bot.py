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

# Validasi konfigurasi
if not api_id or not api_hash or not bot_token:
    raise ValueError("Konfigurasi Telegram tidak lengkap. Pastikan api_id, api_hash, dan bot_token diatur.")

app = Client("telegram_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# Batas permintaan per pengguna
MAX_PENDING_REQUESTS = 2

# Antrean permintaan pengguna
user_requests = defaultdict(list)

# Status global bot
bot_status = {"mode": "normal"}  # Mode default adalah off

# Handler untuk perintah /start
@app.on_message(filters.command("start"))
def handle_start_command(client, message):
    # Ambil nama pengguna (jika ada)
    user_name = message.from_user.first_name if message.from_user.first_name else "Pengguna"

    # Kirim pesan selamat datang
    welcome_message = (
        f"Selamat Datang di AdnanNovations Formatter, {user_name}!\n\n"
        "Silakan ketik /help untuk mengetahui commands yang tersedia.\n"
        "Kami siap membantu format data Anda secara efisien. 😊"
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

# Inisialisasi jadwal dengan apscheduler
scheduler = BackgroundScheduler()
scheduler.add_job(check_reset_time, "interval", minutes=1)
scheduler.start()

# Validasi Nomor Indonesia
def is_valid_indonesian_number(phone_number: str) -> bool:
    pattern = r"^08\d{8,11}$"
    return bool(re.match(pattern, phone_number))

# Handler untuk perintah "off" dari admin
@app.on_message(filters.command("freeze") & filters.private)
def handle_off_command(client, message):
    sender_username = message.from_user.username.lower() if message.from_user.username else None

    # Periksa apakah pengirim adalah admin
    if sender_username not in admin_usernames:
        message.reply_text("Anda tidak memiliki akses untuk menggunakan perintah ini.")
        return

    # Ubah status bot ke "off"
    bot_status["mode"] = "freeze"
    message.reply_text("Bot sekarang dalam mode freeze / maintenance.")

# Handler untuk perintah "full" dari admin
@app.on_message(filters.command("normal") & filters.private)
def handle_full_command(client, message):
    sender_username = message.from_user.username.lower() if message.from_user.username else None

    # Periksa apakah pengirim adalah admin
    if sender_username not in admin_usernames:
        message.reply_text("Anda tidak memiliki akses untuk menggunakan perintah ini.")
        return

    # Ubah status bot ke "full"
    bot_status["mode"] = "normal"
    message.reply_text("Bot kembali aktif dan memproses permintaan user secara normal.")

# Handler untuk pengguna (A)
@app.on_message(filters.command("location"))
def handle_location_command(client, message):
    # Ambil username pengirim
    sender_username = message.from_user.username.lower() if message.from_user.username else None

    # Periksa mode bot
    if bot_status["mode"] == "off":
        # Jika bot dalam mode off, kirim respons statis
        now = datetime.now().strftime("%d-%m-%Y %H:%M")
        phone_number = message.command[1] if len(message.command) > 1 else "Tidak diketahui"

        static_response = (
            f"{now}\n\n"
            f"{phone_number}\n"
            "Device : NULL NULL NULL\n"
            "Age : NULL mins\n"
            "IMEI : NULL\n"
            "IMSI : NULL\n"
            "LAC-CID : NULL - NULL\n"
            "NETWORK : -\n\n"
            "ALAMAT : PROP:NULL|KAB:NULL|KEC:NULL|KEL:NULL\n"
            "http://maps.google.com/?q=NULL,NULL"
        )
        message.reply_text(static_response)
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

    # Kirim notifikasi dan permintaan ke admin
    client.send_message(
        chat_id=message.chat.id,
        text="PENCARIAN SEDANG DIMULAI",
        reply_to_message_id=message.id
    )

    # Kirim permintaan ke admin
    for admin_username in admin_usernames:
        client.send_message(f"@{admin_username}", f"/location {phone_number}")

# Validasi IMEI
def is_valid_imei(imei: str) -> bool:
    return imei.isdigit() and len(imei) == 14

# Handler untuk pengguna (A)
@app.on_message(filters.command("locimei"))
def handle_locimei_command(client, message):
    # Ambil username pengirim
    sender_username = message.from_user.username.lower() if message.from_user.username else None

    # Periksa mode bot
    if bot_status["mode"] == "off":
        # Jika bot dalam mode off, kirim respons statis
        now = datetime.now().strftime("%d-%m-%Y %H:%M")
        imei_number = message.command[1] if len(message.command) > 1 else "Tidak diketahui"

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
        message.reply_text(static_response)
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

        # Handler untuk /location
        if original_message.startswith("/location "):
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
                        "SAAT INI QUOTA SUDAH HABIS, SILAHKAN MENUNGGU DIATAS JAM 00.00 WIB"
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
                        "SAAT INI QUOTA SUDAH HABIS, SILAHKAN MENUNGGU DIATAS JAM 00.00 WIB"
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
            client.send_message(f"@{username}", f"📢 PENGUMUMAN: {announcement_message}")
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

    # Fetch values using multiple keywords for flexibility
    msisdn_line = next((line for line in lines if line.startswith(".:: RESULT FOR")), None)
    msisdn = (
        msisdn_line.split("RESULT FOR ")[-1].replace(" ::.", "").strip()
        if msisdn_line
        else get_value(["MSISDN"])
    )
    age = get_value(["Age", "Usia", "AGE", "USIA"])
    lac = get_value(["LAC"])
    ci = get_value(["CI"])
    imsi = get_value(["IMSI"])
    imei = get_value(["IMEI"])
    kelurahan = get_value(["KELURAHAN"])
    kecamatan = get_value(["KECAMATAN"])
    kab_kota = get_value(["KAB/KOTA", "KOTA"])
    provinsi = get_value(["PROVINSI"])
    perangkat = get_value(["Perangkat"])
    operator = get_value(["Operator", "PROVIDER"])
    map_link = get_value(["Map", "Maps", "MAP", "Peta", "PETA"])
    tower_link = get_value(["Tower"])
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
    if alamat_raw and any(x in alamat_raw for x in ["PROP", "KAB", "KEC", "KEL"]):
        address_components = {}
        for part in alamat_raw.split("|"):
            label, value = part.split(":", 1)
            address_components[label.strip()] = value.strip()
        address = f"""
{address_components.get("PROP", "")}
{address_components.get("KAB", "") + ", " if "KAB" in address_components else ""}
{address_components.get("KEC", "") + ", " if "KEC" in address_components else ""}
{address_components.get("KEL", "") + ", " if "KEL" in address_components else ""}
""".strip()
    elif alamat_raw:
        address = alamat_raw.strip()

    # Generate final output
    output = f"""
{msisdn}
Device : {perangkat or "-"}
Age : {age or "-"}
IMEI : {imei or "-"}
IMSI : {imsi or "-"}
LAC-CID : {lac + "-" + ci if lac and ci else "-"}
NETWORK : {operator or "-"}
ALAMAT : {address}
{tower_link if tower_link != "-" else ""}
{(f"Azimut Target: {map_link}" if map_link and map_link.strip() != "-" else "") if map_link else ""}
{(f"Map: https://maps.google.com/maps?q={latitude},{longitude}" if latitude and longitude else "") if not map_link else ""}
""".strip()

    return output.strip()

# Jalankan Bot
app.run()
