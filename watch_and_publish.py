import time
import os
import yaml
import subprocess
import logging
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# === SETUP LOGGING ===
SCRIPT_DIR = os.path.dirname(__file__)
LOG_PATH = os.path.join(SCRIPT_DIR, "log", "app.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)

# Batasi log dari modul eksternal
logging.getLogger("watchdog").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# === LOAD CONFIG ===
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.yaml")
with open(CONFIG_PATH, "r") as f:
    config = yaml.safe_load(f)

DRAFT_FOLDER = config["vault_folder"]
SCRIPT_PATH = config["script_path"]
PYTHON_PATH = config["python_path"]
TELEGRAM_TOKEN = config["telegram_token"]
TELEGRAM_CHAT_ID = config["telegram_chat_id"]

# === TELEGRAM NOTIFICATION ===
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.ok:
            logging.info(f"Berhasil kirim ke Telegram: {message}")
        else:
            logging.error(f"[TELEGRAM ERROR] Status {response.status_code}: {response.text}")
    except Exception as e:
        logging.error(f"[TELEGRAM EXCEPTION] Gagal kirim notifikasi: {e}")

# === Handler ===
class MarkdownHandler(FileSystemEventHandler):
    processed_files = set()

    def on_created(self, event):
        if event.is_directory or not event.src_path.endswith(".md"):
            return

        filepath = event.src_path
        if filepath in self.processed_files:
            return

        self.processed_files.add(filepath)
        time.sleep(2)

        processing_path = filepath + ".processing"
        try:
            os.rename(filepath, processing_path)
            logging.info(f"File dikunci: {processing_path}")
        except Exception as e:
            logging.warning(f"Gagal rename file: {filepath}. Error: {e}")
            return

        try:
            subprocess.run(
                [PYTHON_PATH, SCRIPT_PATH, processing_path],
                check=True,
                cwd=os.path.dirname(SCRIPT_PATH),
                capture_output=True,
                text=True
            )
            logging.info(f"Berhasil kirim ke Notion: {processing_path}")
            filename = os.path.basename(filepath)
            send_telegram_message(f"✅ Berhasil Publish ke Notion {filename}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Gagal jalankan script publish. Error: {e}")
            filename = os.path.basename(filepath)
            send_telegram_message(f"❌ Gagal Publish ke Notion {filename}")

# === VALIDASI FOLDER ===
if not os.path.exists(DRAFT_FOLDER):
    logging.error(f"[FATAL] Folder tidak ditemukan: '{DRAFT_FOLDER}'")
    exit(1)

# === Main ===
if __name__ == "__main__":
    logging.info(f"Memantau folder: {DRAFT_FOLDER}")
    event_handler = MarkdownHandler()
    observer = Observer()
    observer.schedule(event_handler, path=DRAFT_FOLDER, recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
