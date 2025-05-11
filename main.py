import requests
from bs4 import BeautifulSoup
import time
import threading
from flask import Flask
import os
from datetime import datetime

# --- CONFIGURATION ---
MOODLE_URL = "https://elearning.univ-bejaia.dz/course/view.php?id=18044"
TELEGRAM_BOT_TOKEN = "7826891551:AAFHFSg-J5WM9A4Qv942zK24xTPAVJConDI"
CHAT_ID = "-1002462776688"  # Updated to Life in Campus El-Kseur channel
CHECK_INTERVAL = 60  # seconds
STATE_FILE = "sent_today.txt"

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Moodle bot is running!"

# Load IDs already sent today
def load_sent_ids():
    if not os.path.exists(STATE_FILE):
        return set()
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

# Save a new ID
def save_sent_id(data_id):
    with open(STATE_FILE, "a", encoding="utf-8") as f:
        f.write(data_id + "\n")

# Reset IDs if the day has changed
def reset_if_new_day():
    today_marker = datetime.today().strftime("%Y-%m-%d")
    marker_file = "day_marker.txt"
    if os.path.exists(marker_file):
        with open(marker_file, "r") as f:
            last_day = f.read().strip()
        if last_day != today_marker:
            open(STATE_FILE, "w").close()
    with open(marker_file, "w") as f:
        f.write(today_marker)

# Clean and enhance content for Telegram
def clean_text(text, date_text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    filtered = [line for line in lines if date_text not in line]
    improved = []

    for line in filtered:
        line_lower = line.lower()
        keywords = ["groupe", "salle", "horaire", "planning", "interrogation", "consultation", "respect", "récupération"]
        if any(kw in line_lower for kw in keywords):
            line = f"<b>{line}</b>"
            improved.append(line)
            improved.append("")  # empty line after important content
        else:
            improved.append(line)

    # Remove consecutive empty lines
    result = []
    skip = False
    for line in improved:
        if line == "":
            if not skip:
                result.append("")
            skip = True
        else:
            result.append(line)
            skip = False

    return "\n".join(result).strip()

# Send formatted message to Telegram
def send_to_telegram(title, content, date_affichage):
    message = f"<b>{title}</b>\n📅 <i>{date_affichage}</i>\n\n{content}"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    response = requests.post(url, data=payload)
    print("📤 Message sent | Status:", response.status_code)

# Extract all affichages
def get_all_affichages():
    response = requests.get(MOODLE_URL)
    soup = BeautifulSoup(response.text, "html.parser")
    return soup.find_all("li", class_=["activity", "activity-wrapper", "label", "modtype_label"])

# Extract date
def extract_affichage_date(affichage_html):
    date_tag = affichage_html.find("span", string=lambda x: x and "Affiché le" in x)
    if not date_tag:
        return None, "Date inconnue"
    raw_text = date_tag.text.strip()
    try:
        parts = raw_text.split(":")[1].strip()
        date_part = parts.split("à")[0].strip()
        return datetime.strptime(date_part, "%d/%m/%Y").date(), raw_text
    except:
        return None, raw_text

# Extract title
def extract_title(affichage_html):
    strong_tags = affichage_html.find_all("strong")
    for tag in strong_tags:
        text = tag.get_text().strip()
        if len(text) > 5:
            return text
    return "📢 Nouvel affichage"

# Startup: send today's affichages
def send_today_affichages():
    print("📆 Checking today's affichages...")
    affichages = get_all_affichages()
    today = datetime.today().date()
    sent_ids = load_sent_ids()
    count = 0

    for item in affichages:
        data_id = item.get("data-id")
        if not data_id or data_id in sent_ids:
            continue
        aff_date, date_display = extract_affichage_date(item)
        if aff_date == today:
            title = extract_title(item)
            raw_text = item.get_text()
            content = clean_text(raw_text, date_display)
            send_to_telegram(title, content, date_display)
            save_sent_id(data_id)
            count += 1

    print(f"✅ {count} affichage(s) for {today} sent.")

# Continuous loop
def bot_loop():
    reset_if_new_day()
    send_today_affichages()
    while True:
        try:
            print("🔍 Checking...")
            affichages = get_all_affichages()
            sent_ids = load_sent_ids()
            latest = affichages[0]  
            data_id = latest.get("data-id")
            if data_id and data_id not in sent_ids:
                aff_date, date_display = extract_affichage_date(latest)
                if aff_date == datetime.today().date():
                    title = extract_title(latest)
                    raw_text = latest.get_text()
                    content = clean_text(raw_text, date_display)
                    send_to_telegram(title, content, date_display)
                    save_sent_id(data_id)
                    print("🆕 New affichage detected and sent.")
                else:
                    print("➖ Affichage found, but not from today.")
            else:
                print("🔁 No new affichages.")
        except Exception as e:
            print("❌ Error:", e)
        time.sleep(CHECK_INTERVAL)

# Start bot in background
threading.Thread(target=bot_loop).start()

# Run Flask
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
