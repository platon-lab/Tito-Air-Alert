"""Запити до джерел тривог.

Червоний рівень: alerts.in.ua (потрібен токен, Bearer-авторизація).
Жовтий рівень: alerts.in.ua його не віддає, тому беремо свій JSON-файл
формату {"regions": ["Київська", "Харківська"]} (посилання в налаштуваннях).
"""
import json
import urllib.request

ALERTS_URL = "https://api.alerts.in.ua/v1/alerts/active.json"


def _get_json(url, headers=None):
    req = urllib.request.Request(
        url, headers={"User-Agent": "TitoAirAlert/1.0", **(headers or {})}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_red(token):
    if not token:
        raise ValueError("не вказано токен alerts.in.ua")
    data = _get_json(ALERTS_URL, {"Authorization": "Bearer " + token})
    regions = set()
    for alert in data.get("alerts", []):
        if alert.get("alert_type") != "air_raid":
            continue
        name = alert.get("location_oblast") or alert.get("location_title")
        if name:
            regions.add(name)
    return regions


def fetch_yellow(url):
    if not url:
        return set()
    data = _get_json(url)
    return set(data.get("regions", []))


def get_levels(token, yellow_url=""):
    """Повертає {область: 'red' | 'yellow'}. Червоний важливіший за жовтий."""
    levels = {r: "yellow" for r in fetch_yellow(yellow_url)}
    levels.update({r: "red" for r in fetch_red(token)})
    return levels
