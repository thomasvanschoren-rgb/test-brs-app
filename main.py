# main.py
# Black★Rock Shooter – style Android Launcher (Kivy)
# Features: animated background, particle field, glowing selection bar, app list, sounds, vibration
#
# Requirements (buildozer.spec):
#   requirements = python3,kivy,plyer,jnius
#   android.permissions = VIBRATE
#   android.api = 30
#   android.minapi = 21
#   android.archs = arm64-v8a, armeabi-v7a
#
# Assets: bg.jpg (background), select.wav (selection sound), hover.wav (optional)

import random
from functools import partial

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import FocusBehavior
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.core.audio import SoundLoader
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, Ellipse, RoundedRectangle
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import NumericProperty, ListProperty, ObjectProperty, StringProperty
from kivy.animation import Animation
from kivy.uix.label import Label

# Android support (jnius) to list & launch installed apps
try:
    from jnius import autoclass
    AndroidAvailable = True
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    Intent = autoclass('android.content.Intent')
    PackageManager = autoclass('android.content.pm.PackageManager')
except Exception:
    AndroidAvailable = False

# Plyer vibrator fallback
try:
    from plyer import vibrator
    VIBRATE_AVAILABLE = True
except Exception:
    VIBRATE_AVAILABLE = False

# Visual tuning
PARTICLE_COUNT = 24
PARTICLE_COLORS = [
    (0.2, 0.6, 1.0, 0.18),  # blue
    (0.6, 0.0, 1.0, 0.12),  # violet
    (0.1, 0.9, 0.8, 0.10),
]
GLOW_COLOR = (0.06, 0.4, 1.0, 0.85)


class Particle:
    def __init__(self, widget_width, widget_height):
        self.reset(widget_width, widget_height)

    def reset(self, w, h):
        self.x = random.uniform(0, w)
        self.y = random.uniform(0, h)
        self.vx = random.uniform(-10, 10)
        self.vy = random.uniform(5, 40)
        self.size = random.uniform(6, 28)
        self.color = random.choice(PARTICLE_COLORS)
        self.alpha = random.uniform(0.06, 0.22)

    def step(self, dt, w, h):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vx *= 0.995
        if self.y - self.size > h or self.x < -50 or self.x > w + 50:
            self.reset(w, h)
            self.y = -self.size
        # slight drift
        self.vx += random.uniform(-1, 1) * dt * 50


class GlowingSelection(BoxLayout):
    """A widget that draws a glowing selection bar behind target content."""
    intensity = NumericProperty(1.0)  # 0..1
    color = ListProperty(list(GLOW_COLOR))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # draw glow layers on canvas.before
        self.bind(pos=self._redraw, size=self._redraw, intensity=self._redraw)
        with self.canvas.before:
            # placeholders; actual rectangles replaced in _redraw
            self._glow_layers = []
        self._redraw()

    def _redraw(self, *a):
        self.canvas.before.clear()
        with self.canvas.before:
            # draw multiple rounded rectangles, progressive size & alpha to fake a glow
            layers = 5
            base_w, base_h = self.size
            for i in range(layers):
                scale = 1.0 + i * 0.08 + (1 - self.intensity) * 0.1
                alpha = (0.18 * (1.0 - i / layers)) * self.intensity
                c = self.color[:3] + [alpha]
                Color(*c)
                pad_w = (base_w * (scale - 1)) / 2
                pad_h = (base_h * (scale - 1)) / 2
                RoundedRectangle(pos=(self.x - pad_w, self.y - pad_h),
                                 size=(base_w * scale, base_h * scale),
                                 radius=[dp(8), ])
        # canvas.before done


class AppButton(Button):
    """Single app entry with icon text (icon omitted - keep simple)"""
    package = StringProperty('')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_color = (0, 0, 0, 0)
        self.color = (0.86, 0.95, 1, 1)
        self.font_size = dp(16)
        self.halign = 'left'
        self.valign = 'middle'
        self.size_hint_y = None
        self.height = dp(56)


class AppList(GridLayout, FocusBehavior):
    """Scrollable list of installed apps (simple text list)."""
    container = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cols = 1
        self.spacing = dp(6)
        self.padding = [dp(12), dp(12), dp(12), dp(12)]
        self.bind(minimum_height=self.setter('height'))
        Clock.schedule_once(self._load_apps, 0.5)

    def _load_apps(self, *args):
        self.clear_widgets()
        if AndroidAvailable:
            activity = PythonActivity.mActivity
            pm = activity.getPackageManager()
            main_intent = Intent(Intent.ACTION_MAIN, None)
            main_intent.addCategory(Intent.CATEGORY_LAUNCHER)
            apps = pm.queryIntentActivities(main_intent, 0)
            # gather tuples (label, launch_intent)
            entries = []
            for app in apps:
                try:
                    label = app.loadLabel(pm)
                    package_name = app.activityInfo.packageName
                    launch_intent = pm.getLaunchIntentForPackage(package_name)
                    if launch_intent:
                        entries.append((str(label), launch_intent))
                except Exception:
                    continue
            entries = sorted(entries, key=lambda e: e[0].lower())
            for label, launch_intent in entries:
                btn = AppButton(text=label)
                btn.package = str(label)
                btn.bind(on_release=partial(self._on_launch, launch_intent))
                btn.bind(on_touch_down=self._on_touch_down)
                self.add_widget(btn)
        else:
            # desktop fallback: create dummies
            for i in range(18):
                btn = AppButton(text=f"Sample App {i+1}")
                btn.bind(on_release=lambda *_: print("Launch sample"))
                self.add_widget(btn)

    def _on_touch_down(self, widget, touch):
        if widget.collide_point(*touch.pos):
            # animate a subtle selection glow when touched
            parent = widget.parent
            # find or create a glow widget overlayed
            sel = getattr(self, "_sel", None)
            if sel is None:
                sel = GlowingSelection(size=(widget.width, widget.height))
                self._sel = sel
                # place inside parent layout (we'll insert into root overlay)
                root = App.get_running_app().root
                root.add_glow_overlay(sel)
            # position and animate
            sel.pos = widget.to_window(widget.x, widget.y)
            sel.size = (widget.width, widget.height)
            sel.intensity = 1.0
            anim = Animation(intensity=0.9, d=0.18) + Animation(intensity=0.6, d=0.35)
            anim.start(sel)
            return False

    def _on_launch(self, intent, *a):
        # launch the app via Android activity intent
        if AndroidAvailable:
            try:
                PythonActivity.mActivity.startActivity(intent)
            except Exception as e:
                print("Launch error:", e)
        # feedback
        if VIBRATE_AVAILABLE:
            try:
                vibrator.vibrate(0.05)
            except Exception:
                pass
        sound = App.get_running_app().select_sound
        if sound:
            sound.play()


class BackgroundWidget(Widget := BoxLayout):
    """A full-screen widget that draws a background image and particles and manages subtle motion."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (1, 1)
        with self.canvas:
            self.bg_rect = Rectangle(source='bg.jpg', pos=self.pos, size=Window.size)
        self.bind(pos=self._update_rect, size=self._update_rect)
        # particle system
        self.particles = [Particle(Window.width, Window.height) for _ in range(PARTICLE_COUNT)]
        Clock.schedule_interval(self._update, 1/30.0)
        self._frame = 0
        # small parallax offsets
        self.parallax_x = 0.0
        self.parallax_y = 0.0

    def _update_rect(self, *a):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def _update(self, dt):
        # animate background scale/pulse
        self._frame += 1
        # subtle scaling (zoom in/out)
        scale_mod = 1.0 + 0.008 * (1 + (0.5 * (1 + __import__('math').sin(self._frame * 0.02))))
        # reposition + scale by creating a transformed source pos/size (simulate by adjusting size)
        # we cannot change source scale easily without shader; we'll reposition to emulate motion
        # Keep central rectangle - small shift for parallax
        offset_x = self.parallax_x * 0.2
        offset_y = self.parallax_y * 0.2
        w, h = Window.size
        ns = (w * scale_mod, h * scale_mod)
        self.bg_rect.pos = (self.x - (ns[0]-w)/2 + offset_x, self.y - (ns[1]-h)/2 + offset_y)
        self.bg_rect.size = ns
        # step particles
        self.canvas.after.clear()
        with self.canvas.after:
            for p in self.particles:
                p.step(dt, Window.width, Window.height)
                Color(*p.color[:3], p.alpha)
                Ellipse(pos=(p.x, p.y), size=(p.size, p.size))
                # small halo
                Color(*p.color[:3], p.alpha * 0.6)
                Ellipse(pos=(p.x - p.size*0.6/2, p.y - p.size*0.6/2), size=(p.size*1.6, p.size*1.6))


class RootWidget(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        # background and overlays
        self.bg = BackgroundWidget()
        self.add_widget(self.bg)

        # overlay container - we'll place UI over the bg
        self.ui_layer = BoxLayout(orientation='vertical', padding=[dp(12), dp(24), dp(12), dp(12)])
        self.ui_layer.size_hint = (1, 1)
        # transparent background to sit above bg
        self.add_widget(self.ui_layer)

        # top header with logo-like label
        header = BoxLayout(size_hint=(1, None), height=dp(80))
        title = Label(text="[b][size=22]BLACK★ROCK SHOOTER[/size][/b]\n[size=12]Launcher Mode[/size]",
                      markup=True, halign='left', valign='middle')
        header.add_widget(title)
        self.ui_layer.add_widget(header)

        # main area: Scrollable app list
        scroll = ScrollView(size_hint=(1, 1))
        self.app_list = AppList(size_hint=(1, None))
        self.app_list.cols = 1
        self.app_list.bind(minimum_height=self.app_list.setter('height'))
        scroll.add_widget(self.app_list)
        self.ui_layer.add_widget(scroll)

        # bottom bar with fake menu buttons
        bottom = BoxLayout(size_hint=(1, None), height=dp(64), spacing=dp(8))
        btn_settings = Button(text="Settings", size_hint=(None, 1), width=dp(120))
        btn_settings.bind(on_release=self.open_settings)
        bottom.add_widget(Label())  # spacer
        bottom.add_widget(btn_settings)
        self.ui_layer.add_widget(bottom)

        # overlay for glowing selection - will be added as child of parent window manually
        self._glow_overlay = None

    def add_glow_overlay(self, widget):
        # convert window coords to local and add overlay to root window
        if self._glow_overlay:
            # replace pos/size
            self._glow_overlay.pos = widget.pos
            self._glow_overlay.size = widget.size
        else:
            self._glow_overlay = widget
            # We add to Window's children so it sits above everything else
            from kivy.base import EventLoop
            EventLoop.window.add_widget(widget)

    def open_settings(self, *a):
        # fallback: open Android settings if available
        if AndroidAvailable:
            try:
                Settings = autoclass('android.provider.Settings')
                intent = Intent(Intent.ACTION_MAIN)
                intent.setClassName("com.android.settings", "com.android.settings.Settings")
                PythonActivity.mActivity.startActivity(intent)
            except Exception as e:
                print("Settings open failed:", e)


class BRSLauncherApp(App):
    def build(self):
        Window.clearcolor = (0, 0, 0, 1)
        self.select_sound = SoundLoader.load('select.wav')
        self.hover_sound = SoundLoader.load('hover.wav') if SoundLoader else None
        return RootWidget()

    def on_start(self):
        # on Android make sure this app can be selected as launcher (Buildozer config)
        pass


if __name__ == '__main__':
    BRSLauncherApp().run()
