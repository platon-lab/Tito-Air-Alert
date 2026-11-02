"""Все, що стосується Android: голос (TTS), картка поверх екрана, дозволи, сервіс.
На ПК функції лише друкують у консоль, щоб логіку можна було перевірити."""
import os

import storage

try:
    from jnius import PythonJavaClass, autoclass, java_method
    ON_ANDROID = True
except ImportError:  # на ПК pyjnius немає
    ON_ANDROID = False

    def autoclass(name):
        raise RuntimeError("це не Android")

    class PythonJavaClass:  # заглушка, щоб класи нижче оголошувались на ПК
        def __init__(self, *a, **k):
            pass

    def java_method(*args, **kwargs):
        return lambda f: f


SERVICE_CLASS = "org.tito.airalert.ServiceAlertmonitor"  # має збігатися з buildozer.spec

_keep = []        # посилання на Runnable, щоб збирач сміття їх не прибрав
_gen = 0          # номер поточної картки, щоб старий таймер не сховав нову
_overlay = None   # (WindowManager, View) поточної картки
_handler = None


def is_android():
    return ON_ANDROID


def activity_context():
    return autoclass("org.kivy.android.PythonActivity").mActivity


def service_context():
    return autoclass("org.kivy.android.PythonService").mService


class _Runnable(PythonJavaClass):
    __javainterfaces__ = ["java/lang/Runnable"]
    __javacontext__ = "app"

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    @java_method("()V")
    def run(self):
        try:
            self.fn()
        except Exception as e:
            storage.log(f"UI помилка: {e}")
        finally:
            if self in _keep:
                _keep.remove(self)


def _post(fn, delay_ms=0):
    """Виконує fn на головному потоці UI (з таймером, якщо задано)."""
    global _handler
    if not ON_ANDROID:
        fn()
        return
    if _handler is None:
        Handler = autoclass("android.os.Handler")
        Looper = autoclass("android.os.Looper")
        _handler = Handler(Looper.getMainLooper())
    r = _Runnable(fn)
    _keep.append(r)
    if delay_ms:
        _handler.postDelayed(r, delay_ms)
    else:
        _handler.post(r)


class _InitListener(PythonJavaClass):
    __javainterfaces__ = ["android/speech/tts/TextToSpeech$OnInitListener"]
    __javacontext__ = "app"

    def __init__(self, cb):
        super().__init__()
        self.cb = cb

    @java_method("(I)V")
    def onInit(self, status):
        self.cb(status)


class Speaker:
    """Озвучка українською через системний TTS Android."""

    def __init__(self, ctx=None):
        self.ctx = ctx
        self.tts = None
        self.ready = False
        self.pending = []
        self._listener = None
        if ON_ANDROID:
            _post(self._create)

    def _create(self):
        self.ctx = self.ctx or activity_context()
        self._listener = _InitListener(self._on_init)
        TTS = autoclass("android.speech.tts.TextToSpeech")
        self.tts = TTS(self.ctx, self._listener)

    def _on_init(self, status):
        if status != 0:
            storage.log("TTS не запустився")
            return
        Locale = autoclass("java.util.Locale")
        if self.tts.setLanguage(Locale("uk", "UA")) < 0:
            self.tts.setLanguage(Locale("uk"))
        AudioAttributes = autoclass("android.media.AudioAttributes")
        builder = autoclass("android.media.AudioAttributes$Builder")()
        attrs = (
            builder.setUsage(AudioAttributes.USAGE_ALARM)
            .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
            .build()
        )
        self.tts.setAudioAttributes(attrs)
        self.ready = True
        for text, loud in self.pending:
            self._speak(text, loud)
        self.pending.clear()

    def say(self, text, loud=True):
        if not ON_ANDROID:
            print(f"[ГОЛОС] {text}")
            return
        _post(lambda: self._queue(text, loud))

    def _queue(self, text, loud):
        if self.ready:
            self._speak(text, loud)
        else:
            self.pending.append((text, loud))

    def _speak(self, text, loud):
        if loud:
            boost_alarm_volume(self.ctx)
        flush = autoclass("android.speech.tts.TextToSpeech").QUEUE_FLUSH
        self.tts.speak(text, flush, None, "tito")


def boost_alarm_volume(ctx=None):
    if not ON_ANDROID:
        return
    try:
        ctx = ctx or activity_context()
        am = ctx.getSystemService(autoclass("android.content.Context").AUDIO_SERVICE)
        stream = autoclass("android.media.AudioManager").STREAM_ALARM
        am.setStreamVolume(stream, am.getStreamMaxVolume(stream), 0)
    except Exception as e:
        storage.log(f"гучність: {e}")


def can_draw_overlays(ctx=None):
    if not ON_ANDROID:
        return False
    Settings = autoclass("android.provider.Settings")
    return bool(Settings.canDrawOverlays(ctx or activity_context()))


def open_overlay_settings(ctx=None):
    if not ON_ANDROID:
        print("Відкрий налаштування: Поверх інших додатків")
        return
    ctx = ctx or activity_context()
    Intent = autoclass("android.content.Intent")
    Settings = autoclass("android.provider.Settings")
    Uri = autoclass("android.net.Uri")
    intent = Intent(
        Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
        Uri.parse("package:" + ctx.getPackageName()),
    )
    intent.addFlags(0x10000000)  # FLAG_ACTIVITY_NEW_TASK
    ctx.startActivity(intent)


def request_runtime_permissions():
    if not ON_ANDROID:
        return
    try:
        from android.permissions import request_permissions
        request_permissions(["android.permission.POST_NOTIFICATIONS"])
    except Exception as e:
        storage.log(f"дозволи: {e}")


def show_overlay(title, text, color="#C62828", seconds=15, photo=None, ctx=None):
    """Картка поверх усіх додатків, з фото Тіто. Сама зникає через seconds."""
    if not ON_ANDROID:
        print(f"[ПОВЕРХ ЕКРАНУ] {title}: {text}")
        return
    ctx = ctx or activity_context()
    _post(lambda: _build_overlay(ctx, title, text, color, seconds, photo))


def _remove_overlay():
    global _overlay
    if _overlay is not None:
        wm, view = _overlay
        _overlay = None
        try:
            wm.removeView(view)
        except Exception:
            pass


def _remove_if(gen):
    if gen == _gen:
        _remove_overlay()


def _build_overlay(ctx, title, text, color, seconds, photo):
    global _overlay, _gen
    _remove_overlay()
    _gen += 1
    gen = _gen

    LinearLayout = autoclass("android.widget.LinearLayout")
    TextView = autoclass("android.widget.TextView")
    ImageView = autoclass("android.widget.ImageView")
    Color = autoclass("android.graphics.Color")
    Typeface = autoclass("android.graphics.Typeface")
    Gravity = autoclass("android.view.Gravity")
    GradientDrawable = autoclass("android.graphics.drawable.GradientDrawable")
    BitmapFactory = autoclass("android.graphics.BitmapFactory")
    LayoutParams = autoclass("android.view.WindowManager$LayoutParams")
    PixelFormat = autoclass("android.graphics.PixelFormat")
    Build = autoclass("android.os.Build$VERSION")
    Context = autoclass("android.content.Context")

    root = LinearLayout(ctx)
    root.setOrientation(LinearLayout.VERTICAL)
    root.setPadding(40, 32, 40, 32)
    bg = GradientDrawable()
    bg.setColor(Color.parseColor(color))
    bg.setCornerRadius(48.0)
    root.setBackground(bg)

    if photo and os.path.exists(photo):
        opts = autoclass("android.graphics.BitmapFactory$Options")()
        opts.inSampleSize = 4  # фото з камери велике, зменшуємо для пам'яті
        iv = ImageView(ctx)
        iv.setImageBitmap(BitmapFactory.decodeFile(photo, opts))
        lp = LinearLayout.LayoutParams(220, 220)
        lp.gravity = Gravity.CENTER_HORIZONTAL
        root.addView(iv, lp)

    t1 = TextView(ctx)
    t1.setText(title)
    t1.setTextSize(24.0)
    t1.setTextColor(Color.WHITE)
    t1.setTypeface(Typeface.DEFAULT_BOLD)
    t1.setGravity(Gravity.CENTER)
    root.addView(t1)

    t2 = TextView(ctx)
    t2.setText(text)
    t2.setTextSize(17.0)
    t2.setTextColor(Color.WHITE)
    t2.setGravity(Gravity.CENTER)
    root.addView(t2)

    wm = ctx.getSystemService(Context.WINDOW_SERVICE)
    wtype = 2038 if Build.SDK_INT >= 26 else 2002  # TYPE_APPLICATION_OVERLAY або TYPE_PHONE
    params = LayoutParams(
        LayoutParams.WRAP_CONTENT,
        LayoutParams.WRAP_CONTENT,
        wtype,
        LayoutParams.FLAG_NOT_FOCUSABLE,
        PixelFormat.TRANSLUCENT,
    )
    params.gravity = Gravity.TOP | Gravity.CENTER_HORIZONTAL
    params.y = 120
    wm.addView(root, params)
    _overlay = (wm, root)
    _post(lambda: _remove_if(gen), seconds * 1000)


def start_monitor_service(ctx=None):
    if not ON_ANDROID:
        print("[СЕРВІС] фоновий моніторинг працює тільки на телефоні")
        return
    autoclass(SERVICE_CLASS).start(ctx or activity_context(), "")


def stop_monitor_service(ctx=None):
    if not ON_ANDROID:
        return
    autoclass(SERVICE_CLASS).stop(ctx or activity_context())
