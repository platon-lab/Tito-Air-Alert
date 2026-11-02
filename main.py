"""«Тіто — Повітряна тривога». Екрани: карта, історія, налаштування."""
import datetime as dt
import threading

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.switch import Switch
from kivy.uix.textinput import TextInput

import android_tools as at
import api, icons, storage
from regions import REGION_COORDS, UKRAINE_CENTER

try:
    from kivy_garden.mapview import MapMarker, MapView
    HAS_MAP = True
except Exception:  # без MapView покажемо список областей
    HAS_MAP = False

LEVEL_TEXT = {
    "red": "[color=c62828]червоний[/color]: повітряна тривога",
    "yellow": "[color=f9a825]жовтий[/color]: загроза",
}
EVENT_TEXT = {
    "red": "[color=c62828]Повітряна тривога[/color]",
    "yellow": "[color=f9a825]Жовтий рівень[/color]",
    "end": "[color=2e7d32]Відбій[/color]",
}


def fit_label(text, size=16, **kw):
    """Підпис, який переносить текст і займає рівно стільки висоти, скільки треба."""
    lbl = Label(text=text, font_size=dp(size), markup=True, halign="left",
                valign="middle", size_hint_y=None, **kw)
    lbl.bind(width=lambda w, v: setattr(w, "text_size", (v, None)))
    lbl.bind(texture_size=lambda w, v: setattr(w, "height", v[1] + dp(12)))
    return lbl


def btn(text, cb):
    b = Button(text=text, size_hint_y=None, height=dp(48))
    b.bind(on_release=lambda *_: cb())
    return b


class MapScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))

        top = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(8))
        top.add_widget(Image(source=storage.tito_photo(), size_hint_x=None, width=dp(56)))
        self.status = Label(markup=True, halign="left", valign="middle", font_size=dp(15))
        self.status.bind(size=lambda w, v: setattr(w, "text_size", v))
        top.add_widget(self.status)
        root.add_widget(top)

        self.map = None
        self.markers = []
        if HAS_MAP:
            self.map = MapView(lat=UKRAINE_CENTER[0], lon=UKRAINE_CENTER[1], zoom=6)
            root.add_widget(self.map)
        else:
            self.list = GridLayout(cols=1, size_hint_y=None, spacing=dp(6))
            self.list.bind(minimum_height=self.list.setter("height"))
            scroll = ScrollView()
            scroll.add_widget(self.list)
            root.add_widget(scroll)
            self.status.text = "Карта недоступна, показую список областей."

        self.add_widget(root)

    def show(self, levels=None, error=None):
        if error:
            self.status.text = f"[color=f9a825]Помилка:[/color] {error}"
            return
        levels = levels or {}
        if levels:
            self.status.text = f"[b]Тривога[/b] в областях: {len(levels)}"
        else:
            self.status.text = "[b]Тихо.[/b] Тривог немає."

        if self.map is not None:
            icon_paths = App.get_running_app().icons
            for m in self.markers:
                self.map.remove_marker(m)
            self.markers = []
            for region, level in levels.items():
                lat, lon = REGION_COORDS.get(region, UKRAINE_CENTER)
                marker = MapMarker(lat=lat, lon=lon, source=icon_paths[level])
                self.map.add_marker(marker)
                self.markers.append(marker)
        else:
            self.list.clear_widgets()
            for region, level in sorted(levels.items()):
                self.list.add_widget(fit_label(f"{LEVEL_TEXT[level]}  —  {region}"))


class HistoryScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        bar = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        bar.add_widget(btn("Оновити", self.refresh))
        bar.add_widget(btn("Очистити", self.clear))
        root.add_widget(bar)

        scroll = ScrollView()
        self.list = GridLayout(cols=1, size_hint_y=None, spacing=dp(6))
        self.list.bind(minimum_height=self.list.setter("height"))
        scroll.add_widget(self.list)
        root.add_widget(scroll)
        self.add_widget(root)

    def on_enter(self, *args):
        self.refresh()

    def refresh(self):
        self.list.clear_widgets()
        events = list(reversed(storage.load_history()))
        if not events:
            self.list.add_widget(fit_label("Історія порожня. Тіто ще нічого не бачив."))
            return
        for e in events[:300]:
            try:
                when = dt.datetime.fromisoformat(e["ts"]).strftime("%d.%m %H:%M")
            except Exception:
                when = e.get("ts", "")
            kind = EVENT_TEXT.get(e["event"], e["event"])
            self.list.add_widget(fit_label(f"{when}  {kind} — {e['region']}"))

    def clear(self):
        storage.clear_history()
        self.refresh()


class SettingsScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        s = storage.load_settings()

        scroll = ScrollView()
        self.box = GridLayout(cols=1, size_hint_y=None, padding=dp(12), spacing=dp(10))
        self.box.bind(minimum_height=self.box.setter("height"))

        photo_row = AnchorLayout(size_hint_y=None, height=dp(200))
        self.photo = Image(source=storage.tito_photo(), size_hint=(None, None),
                           size=(dp(160), dp(160)))
        photo_row.add_widget(self.photo)
        self._add(photo_row)

        self.token = self._field("Токен alerts.in.ua (обов'язково)", s["token"])
        self.yellow = self._field("Посилання на JSON жовтого рівня (необов'язково)",
                                  s["yellow_url"])
        self.interval = self._field("Інтервал опитування, сек (мінімум 10)",
                                    str(s["interval"]), numeric=True)
        self.voice = self._switch("Голос Тіто", s["voice"])
        self.loud = self._switch("Гучно (максимум гучності будильника)", s["loud"])
        self.overlay = self._switch("Картка поверх інших додатків", s["overlay"])

        self._add(btn("Дати дозволи", self.grant))
        self._add(btn("Зберегти налаштування", self.save))
        self._add(btn("Запустити фоновий моніторинг", self.start_monitor))
        self._add(btn("Зупинити моніторинг", self.stop_monitor))
        self._add(btn("Тест голосу", self.test_voice))
        self._add(btn("Тест анімації і картки", self.test_animation))

        self.hint = fit_label("", size=14)
        self._add(self.hint)

        scroll.add_widget(self.box)
        self.add_widget(scroll)

    def _add(self, widget):
        self.box.add_widget(widget)
        return widget

    def _field(self, label, value, numeric=False):
        self._add(fit_label(label, size=14))
        return self._add(TextInput(
            text=value, multiline=False, size_hint_y=None, height=dp(44),
            input_filter="int" if numeric else None,
        ))

    def _switch(self, label, value):
        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        lbl = Label(text=label, font_size=dp(15), halign="left")
        lbl.bind(size=lambda w, v: setattr(w, "text_size", v))
        row.add_widget(lbl)
        sw = Switch(active=value, size_hint_x=None, width=dp(70))
        row.add_widget(sw)
        self._add(row)
        return sw

    def save(self):
        cfg = storage.load_settings()
        try:
            interval = max(10, int(self.interval.text or 20))
        except ValueError:
            interval = 20
        cfg.update(
            token=self.token.text.strip(),
            yellow_url=self.yellow.text.strip(),
            interval=interval,
            voice=self.voice.active,
            loud=self.loud.active,
            overlay=self.overlay.active,
        )
        storage.save_settings(cfg)
        self.hint.text = "Збережено."

    def grant(self):
        App.get_running_app().ask_permissions()
        self.hint.text = "Увімкни «Поверх інших додатків» і поверніться в додаток."

    def start_monitor(self):
        self.save()
        if not storage.load_settings()["token"]:
            self.hint.text = "Спершу встав токен і натисни «Зберегти»."
            return
        at.start_monitor_service()
        self.hint.text = "Фоновий моніторинг запущено. Тіто на варті."

    def stop_monitor(self):
        at.stop_monitor_service()
        self.hint.text = "Моніторинг зупинено."

    def test_voice(self):
        App.get_running_app().get_speaker().say(
            "Тіто каже. Це тест голосу. Повітряна тривога.", loud=self.loud.active
        )

    def _pulse(self, *_):
        grow = Animation(size=(dp(200), dp(200)), duration=0.25, t="out_back")
        shrink = Animation(size=(dp(160), dp(160)), duration=0.25)
        (grow + shrink).start(self.photo)

    def test_animation(self):
        for i in range(3):
            Clock.schedule_once(self._pulse, i * 0.6)
        if self.voice.active:
            App.get_running_app().get_speaker().say(
                "Тіто каже. Тест. Повітряна тривога. Київська область.",
                loud=self.loud.active,
            )
        if at.can_draw_overlays():
            at.show_overlay("Повітряна тривога", "Тестова картка Тіто",
                            color="#C62828", photo=storage.tito_photo())
        else:
            self.hint.text = "Немає дозволу «Поверх інших додатків». Натисни «Дати дозволи»."


class TitoApp(App):
    title = "Тіто — Повітряна тривога"
    _speaker = None

    def build(self):
        self.icons = icons.ensure_icons()
        self.sm = ScreenManager()
        self.map_screen = MapScreen(name="map")
        self.history_screen = HistoryScreen(name="history")
        self.settings_screen = SettingsScreen(name="settings")
        for screen in (self.map_screen, self.history_screen, self.settings_screen):
            self.sm.add_widget(screen)

        root = BoxLayout(orientation="vertical")
        root.add_widget(self.sm)
        nav = BoxLayout(size_hint_y=None, height=dp(52))
        for name, label in (("map", "Карта"), ("history", "Історія"),
                            ("settings", "Налаштування")):
            nav.add_widget(Button(text=label, on_release=lambda _b, n=name: self.go(n)))
        root.add_widget(nav)

        Clock.schedule_once(lambda _dt: self.refresh(), 1)
        Clock.schedule_interval(lambda _dt: self.refresh(), 30)
        Clock.schedule_once(lambda _dt: self.first_run(), 1.5)
        return root

    def go(self, name):
        self.sm.current = name

    def get_speaker(self):
        if self._speaker is None:
            self._speaker = at.Speaker()
        return self._speaker

    def refresh(self):
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        cfg = storage.load_settings()
        if not cfg["token"]:
            Clock.schedule_once(
                lambda _dt: self.map_screen.show(None, "Додай токен у налаштуваннях"))
            return
        try:
            levels = api.get_levels(cfg["token"], cfg["yellow_url"])
            Clock.schedule_once(lambda _dt: self.map_screen.show(levels))
        except Exception as e:
            err = str(e)
            Clock.schedule_once(lambda _dt: self.map_screen.show(None, err))

    def ask_permissions(self):
        at.request_runtime_permissions()
        if at.is_android() and not at.can_draw_overlays():
            at.open_overlay_settings()

    def first_run(self):
        if storage.load_settings()["onboarded"]:
            return
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(12))
        box.add_widget(fit_label(
            "Привіт, я Тіто. Щоб попереджати про тривогу навіть коли ти в інших "
            "додатках, мені потрібні два дозволи: показ поверх екрана і сповіщення."
        ))

        def accept():
            cfg = storage.load_settings()
            cfg["onboarded"] = True
            storage.save_settings(cfg)
            self.ask_permissions()
            popup.dismiss()

        popup = Popup(title="Тіто просить дозволи", content=box,
                      size_hint=(0.9, 0.55), auto_dismiss=False)
        box.add_widget(btn("Дати дозволи", accept))
        box.add_widget(btn("Пізніше", popup.dismiss))
        popup.open()


if __name__ == "__main__":
    TitoApp().run()
