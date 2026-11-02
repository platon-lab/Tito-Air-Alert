"""Збереження налаштувань, історії та стану. Працює і на ПК, і на Android."""
import datetime as dt
import json
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("ANDROID_PRIVATE") or os.path.join(APP_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
LOG_FILE = os.path.join(DATA_DIR, "log.txt")

DEFAULT_SETTINGS = {
    "token": "",
    "yellow_url": "",
    "voice": True,
    "loud": True,
    "overlay": True,
    "interval": 20,
    "onboarded": False,
}
MAX_HISTORY = 1000


def _read(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_settings():
    s = dict(DEFAULT_SETTINGS)
    s.update(_read(SETTINGS_FILE, {}))
    return s


def save_settings(settings):
    _write(SETTINGS_FILE, settings)


def load_state():
    return _read(STATE_FILE, {"levels": {}})


def save_state(state):
    _write(STATE_FILE, state)


def load_history():
    return _read(HISTORY_FILE, [])


def add_history(events):
    history = load_history() + events
    _write(HISTORY_FILE, history[-MAX_HISTORY:])


def clear_history():
    _write(HISTORY_FILE, [])


def log(message):
    stamp = dt.datetime.now().strftime("%d.%m %H:%M:%S")
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{stamp} {message}\n")
    except Exception:
        pass


def now_iso():
    return dt.datetime.now().isoformat(timespec="minutes")


def tito_photo():
    return os.path.join(APP_DIR, "tito.jpg")


def icon_path(name):
    return os.path.join(DATA_DIR, f"icon_{name}.png")
