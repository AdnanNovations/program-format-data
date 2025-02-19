import tkinter as tk
from tkinter import ttk
import asyncio
import configparser
import subprocess  # Untuk menjalankan bot secara terpisah

# Status bot dan konfigurasi
bot_status = {"mode": "normal"}
config = configparser.ConfigParser()
config.read("config.ini")

reset_time = config["Settings"].get("reset_time", "07:00")  # Default ke 07:00 jika tidak ditemukan

# Simpan konfigurasi
def save_config():
    config["Settings"] = {"mode": bot_status["mode"], "reset_time": reset_time}
    with open("config.ini", "w") as f:
        config.write(f)

# Fungsi untuk memperbarui label status
def update_status_label():
    status_label.config(text=f"Mode: {bot_status['mode']}")

# Fungsi untuk toggle freeze
def toggle_freeze():
    bot_status["mode"] = "freeze" if freeze_var.get() else "normal"
    save_config()
    update_status_label()

# Fungsi untuk menjalankan bot
def start_bot():
    try:
        # Menjalankan `bot.py` secara terpisah
        subprocess.Popen(["bot.exe"])
        print("Bot sedang dijalankan...")
    except Exception as e:
        print(f"Error saat menjalankan bot: {e}")

# Fungsi untuk menjalankan GUI
def create_gui():
    root = tk.Tk()
    root.title("Aesthetic BOT")
    root.geometry("300x150")

    # Label untuk status
    global status_label
    status_label = ttk.Label(root, text=f"Mode: {bot_status['mode']}", font=("Arial", 12))
    status_label.pack(pady=10)

    # Checkbox untuk Freeze
    global freeze_var
    freeze_var = tk.BooleanVar(value=(bot_status["mode"] == "freeze"))
    freeze_checkbox = ttk.Checkbutton(
        root, text="Freeze?", variable=freeze_var, command=toggle_freeze
    )
    freeze_checkbox.pack(pady=10)

    # Tombol untuk keluar
    exit_button = ttk.Button(root, text="Keluar", command=root.destroy)
    exit_button.pack(pady=10)

    # Jalankan bot segera setelah GUI selesai dimuat
    start_bot()

    # Integrasi tkinter dengan asyncio
    async def tkinter_loop():
        while True:
            root.update_idletasks()
            root.update()
            await asyncio.sleep(0.01)  # Memberikan kesempatan pada asyncio

    return tkinter_loop()

# Fungsi utama
async def main():
    # Load config file saat awal
    config.read("config.ini")
    if "Settings" in config:
        bot_status["mode"] = config["Settings"].get("mode", "normal")

    # Jalankan GUI
    await create_gui()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram dihentikan.")
