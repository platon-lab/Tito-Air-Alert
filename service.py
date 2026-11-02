"""Фоновий сервіс (запускається як foreground service).

Раз на кілька секунд питає джерело тривог, порівнює з попереднім станом і:
- говорить «Тіто каже ...» гучно українською;
- показує картку поверх інших додатків з фото Тіто.
Працює, навіть коли додаток закритий.
"""
import time

import android_tools as at
import api, storage

RED = "#C62828"
YELLOW = "#F9A825"
GREEN = "#2E7D32"


def _names(items, limit=3):
    items = sorted(items)
    text = ", ".join(items[:limit])
    if len(items) > limit:
        text += f" та ще {len(items) - limit}"
    return text


def diff(prev, now):
    """Повертає (події для історії, повідомлення для голосу і картки)."""
    red_new = [r for r, lvl in now.items() if lvl == "red" and prev.get(r) != "red"]
    yellow_new = [r for r, lvl in now.items() if lvl == "yellow" and r not in prev]
    red_end = [r for r, lvl in prev.items() if lvl == "red" and now.get(r) != "red"]
    yellow_end = [r for r, lvl in prev.items() if lvl == "yellow" and r not in now]

    events, msgs = [], []
    if red_new:
        events += [(r, "red") for r in red_new]
        msgs.append(("Повітряна тривога", _names(red_new), RED))
    if yellow_new:
        events += [(r, "yellow") for r in yellow_new]
        msgs.append(("Жовтий рівень, загроза", _names(yellow_new), YELLOW))
    if red_end:
        events += [(r, "end") for r in red_end]
        msgs.append(("Відбій повітряної тривоги", _names(red_end), GREEN))
    if yellow_end:
        events += [(r, "end") for r in yellow_end]
        msgs.append(("Відбій жовтого рівня", _names(yellow_end), GREEN))
    return events, msgs


def main():
    ctx = at.service_context()
    speaker = at.Speaker(ctx)
    prev = storage.load_state().get("levels", {})
    storage.log("Моніторинг запущено")

    while True:
        cfg = storage.load_settings()
        try:
            if not cfg["token"]:
                raise RuntimeError("немає токена, додай його в налаштуваннях")

            now = api.get_levels(cfg["token"], cfg["yellow_url"])
            events, msgs = diff(prev, now)

            if events:
                ts = storage.now_iso()
                storage.add_history(
                    [{"ts": ts, "region": r, "event": e} for r, e in events]
                )

            if msgs:
                if cfg["voice"]:
                    phrase = ". ".join(f"{h}. {b}" for h, b, _ in msgs)
                    speaker.say("Тіто каже. " + phrase, loud=cfg["loud"])
                if cfg["overlay"] and at.can_draw_overlays(ctx):
                    title = msgs[0][0]
                    text = "\n".join(f"{b}" for _, b, _ in msgs)
                    at.show_overlay(
                        title,
                        text,
                        color=msgs[0][2],
                        photo=storage.tito_photo(),
                        ctx=ctx,
                    )

            prev = now
            storage.save_state({"levels": now})
        except Exception as e:
            storage.log(f"помилка: {e}")

        time.sleep(max(10, int(cfg["interval"])))


main()
