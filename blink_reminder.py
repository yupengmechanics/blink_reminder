"""
Blink Reminder v2 - an always-on-top eye-care overlay for Windows.

Features
--------
1. Blink reminder every BLINK_INTERVAL seconds (fade-in/out banner, 8 s).
2. 20-20-20 reminder every 20 minutes (look 20 ft / 6 m away for 20 s).
3. Optional hourly stretch/posture reminder.
4. Idle detection: reminders are skipped if you have been away from the
   keyboard/mouse for more than IDLE_THRESHOLD seconds.
5. Pause/Resume and "Snooze 10 min" buttons.
6. Rotating message texts to fight habituation.
7. Click-through overlay: never steals focus, safe while typing or gaming.
8. Optional beep as a cue for exclusive-fullscreen games.
9. Session statistics in the small control window.

Requirements: Python 3.8+ on Windows. Standard library only.
Run:   python blink_reminder.py    (or pythonw.exe for no console)
Quit:  "Quit" button on the control window (bottom-right corner).
"""

import ctypes
import itertools
import time
import tkinter as tk

# ----------------------- USER SETTINGS -----------------------
BLINK_INTERVAL        = 60    # seconds between blink reminders (3 min)
BLINK_SHOW_TIME       = 8      # seconds the blink banner stays visible
RULE_202020_INTERVAL  = 1200   # 20 minutes
RULE_202020_SHOW_TIME = 20     # seconds
STRETCH_ENABLED       = True
STRETCH_INTERVAL      = 3600   # 1 hour
STRETCH_SHOW_TIME     = 15     # seconds
IDLE_THRESHOLD        = 120    # skip reminders if idle longer than this (s)
SNOOZE_MINUTES        = 10
PLAY_BEEP             = True
OVERLAY_ALPHA         = 0.88   # max opacity 0..1
FADE_STEPS            = 10     # animation smoothness
FADE_STEP_MS          = 40     # ms per fade step (total fade ~0.4 s)
FONT = ("Segoe UI", 14, "bold")
BG, FG = "#1e1e2e", "#a6e3a1"

# Overlay position: anchor preset + pixel offset.
# Anchors: "top-left", "top-center", "top-right", "center",
#          "bottom-left", "bottom-center", "bottom-right"
OVERLAY_ANCHOR   = "top-center"
OVERLAY_OFFSET_X = 0     # +right / -left shift from the anchor (pixels)
OVERLAY_OFFSET_Y = 40    # +down  / -up   shift from the anchor (pixels)

BLINK_MESSAGES = [
    "\U0001F441  Blink!  Blink slowly a few times \U0001F441",
    "\U0001F441  Time to blink \u2014 close your eyes fully for a second",
    "\U0001F441  Blink break: 5 slow, complete blinks",
    "\U0001F441  Eyes dry? Blink gently and roll your eyes around",
]
RULE_202020_MESSAGE = ("\U0001F304  20-20-20: look at something 20 ft (6 m) "
                       "away for 20 seconds")
STRETCH_MESSAGE = ("\U0001F9D8  Hourly break: stand up, stretch your neck "
                   "and shoulders, sip some water")
# --------------------------------------------------------------

# ---- Windows API: click-through layered topmost window ----
GWL_EXSTYLE = -20
WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW = 0x80000, 0x20, 0x80
HWND_TOPMOST = -1
SWP_NOMOVE, SWP_NOSIZE, SWP_NOACTIVATE = 0x2, 0x1, 0x10
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def idle_seconds() -> float:
    """Seconds since last keyboard/mouse input (system-wide)."""
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    user32.GetLastInputInfo(ctypes.byref(lii))
    return (kernel32.GetTickCount() - lii.dwTime) / 1000.0


def make_click_through(root) -> int:
    hwnd = user32.GetParent(root.winfo_id())
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    return hwnd


def force_topmost(hwnd):
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


class BlinkReminderApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()

        self.paused = False
        self.snooze_until = 0.0
        self.start_time = time.time()
        self.reminder_count = 0
        self.blink_msgs = itertools.cycle(BLINK_MESSAGES)
        self._fade_job = None
        self._hide_job = None

        # ---- overlay banner ----
        self.overlay = tk.Toplevel(self.root)
        self.overlay.overrideredirect(True)
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-alpha", 0.0)
        self.overlay.configure(bg=BG)
        self.label = tk.Label(self.overlay, text="", font=FONT,
                              bg=BG, fg=FG, padx=24, pady=10,
                              wraplength=650, justify="center")
        self.label.pack()
        self.overlay.update_idletasks()
        self.hwnd = make_click_through(self.overlay)
        self.overlay.withdraw()

        # ---- control window ----
        self.ctrl = tk.Toplevel(self.root)
        self.ctrl.title("Blink Reminder")
        self.ctrl.attributes("-topmost", True)
        self.ctrl.resizable(False, False)
        self.status_var = tk.StringVar(value="\U0001F441 Running")
        self.stats_var = tk.StringVar(value="Reminders: 0 | Session: 0 min")
        tk.Label(self.ctrl, textvariable=self.status_var,
                 font=("Segoe UI", 10, "bold")).pack(padx=10, pady=(6, 0))
        tk.Label(self.ctrl, textvariable=self.stats_var,
                 font=("Segoe UI", 8)).pack(padx=10)
        row = tk.Frame(self.ctrl); row.pack(padx=8, pady=6)
        self.pause_btn = tk.Button(row, text="Pause", width=8,
                                   command=self.toggle_pause)
        self.pause_btn.grid(row=0, column=0, padx=2)
        tk.Button(row, text=f"Snooze {SNOOZE_MINUTES}m", width=10,
                  command=self.snooze).grid(row=0, column=1, padx=2)
        tk.Button(row, text="Quit", width=6,
                  command=self.quit).grid(row=0, column=2, padx=2)
        self.ctrl.update_idletasks()
        self._place_corner(self.ctrl)
        self.ctrl.protocol("WM_DELETE_WINDOW", self.quit)

        # ---- schedule loops ----
        self.root.after(BLINK_INTERVAL * 1000, self.blink_reminder)
        self.root.after(RULE_202020_INTERVAL * 1000, self.rule_202020)
        if STRETCH_ENABLED:
            self.root.after(STRETCH_INTERVAL * 1000, self.stretch_reminder)
        self.root.after(5000, self._keep_on_top)
        self.root.after(15000, self._update_stats)

    # ---------------- geometry ----------------
    def _place_corner(self, win):
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        win.geometry(f"+{sw - w - 20}+{sh - h - 90}")

    def _place_overlay(self):
        """Position the banner according to OVERLAY_ANCHOR + offsets,
        clamped so it never goes off-screen."""
        self.overlay.update_idletasks()
        w = self.label.winfo_reqwidth()
        h = self.label.winfo_reqheight()
        sw = self.overlay.winfo_screenwidth()
        sh = self.overlay.winfo_screenheight()

        anchors = {
            "top-left":      (20,            20),
            "top-center":    ((sw - w) // 2, 20),
            "top-right":     (sw - w - 20,   20),
            "center":        ((sw - w) // 2, (sh - h) // 2),
            "bottom-left":   (20,            sh - h - 80),
            "bottom-center": ((sw - w) // 2, sh - h - 80),
            "bottom-right":  (sw - w - 20,   sh - h - 80),
        }
        x, y = anchors.get(OVERLAY_ANCHOR, anchors["top-center"])
        x += OVERLAY_OFFSET_X
        y += OVERLAY_OFFSET_Y
        x = max(0, min(x, sw - w))
        y = max(0, min(y, sh - h))
        self.overlay.geometry(f"{w}x{h}+{x}+{y}")

    # ---------------- fade animation ----------------
    def _cancel_pending(self):
        for job in (self._fade_job, self._hide_job):
            if job is not None:
                try:
                    self.root.after_cancel(job)
                except Exception:
                    pass
        self._fade_job = self._hide_job = None

    def _fade(self, target, step=0, on_done=None):
        frac = (step + 1) / FADE_STEPS
        current = self.overlay.attributes("-alpha")
        alpha = current + (target - current) * frac if step == 0 else None
        # simple linear interpolation recomputed each call:
        start = getattr(self, "_fade_start", current)
        if step == 0:
            self._fade_start = current
            start = current
        alpha = start + (target - start) * frac
        self.overlay.attributes("-alpha", max(0.0, min(1.0, alpha)))
        if step + 1 < FADE_STEPS:
            self._fade_job = self.root.after(
                FADE_STEP_MS, self._fade, target, step + 1, on_done)
        else:
            self._fade_job = None
            if on_done:
                on_done()

    # ---------------- reminder core ----------------
    def _suppressed(self) -> bool:
        if self.paused or time.time() < self.snooze_until:
            return True
        if idle_seconds() > IDLE_THRESHOLD:
            return True  # user is away; stay silent
        return False

    def show_banner(self, text, duration_s):
        if self._suppressed():
            return
        self.reminder_count += 1
        self._cancel_pending()
        self.label.config(text=text)
        self._place_overlay()
        self.overlay.attributes("-alpha", 0.0)
        self.overlay.deiconify()
        force_topmost(self.hwnd)
        if PLAY_BEEP:
            kernel32.Beep(880, 120)
        self._fade(OVERLAY_ALPHA)
        self._hide_job = self.root.after(
            duration_s * 1000,
            lambda: self._fade(0.0, on_done=self.overlay.withdraw))

    def blink_reminder(self):
        self.show_banner(next(self.blink_msgs), BLINK_SHOW_TIME)
        self.root.after(BLINK_INTERVAL * 1000, self.blink_reminder)

    def rule_202020(self):
        self.show_banner(RULE_202020_MESSAGE, RULE_202020_SHOW_TIME)
        self.root.after(RULE_202020_INTERVAL * 1000, self.rule_202020)

    def stretch_reminder(self):
        self.show_banner(STRETCH_MESSAGE, STRETCH_SHOW_TIME)
        self.root.after(STRETCH_INTERVAL * 1000, self.stretch_reminder)

    # ---------------- controls ----------------
    def toggle_pause(self):
        self.paused = not self.paused
        self.pause_btn.config(text="Resume" if self.paused else "Pause")
        self.status_var.set("\u23F8 Paused" if self.paused
                            else "\U0001F441 Running")
        if self.paused:
            self._cancel_pending()
            self.overlay.withdraw()

    def snooze(self):
        self.snooze_until = time.time() + SNOOZE_MINUTES * 60
        self.status_var.set(f"\U0001F4A4 Snoozed {SNOOZE_MINUTES} min")
        self._cancel_pending()
        self.overlay.withdraw()
        self.root.after(SNOOZE_MINUTES * 60 * 1000, self._end_snooze)

    def _end_snooze(self):
        if not self.paused and time.time() >= self.snooze_until:
            self.status_var.set("\U0001F441 Running")

    # ---------------- housekeeping ----------------
    def _keep_on_top(self):
        if self.overlay.state() == "normal":
            force_topmost(self.hwnd)
        self.root.after(5000, self._keep_on_top)

    def _update_stats(self):
        mins = int((time.time() - self.start_time) / 60)
        self.stats_var.set(
            f"Reminders: {self.reminder_count} | Session: {mins} min")
        self.root.after(15000, self._update_stats)

    def quit(self):
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    # Make coordinates true physical pixels under Windows display
    # scaling (125%/150%); also renders text sharper. Safe to fail
    # silently on systems where shcore is unavailable.
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    BlinkReminderApp().run()
