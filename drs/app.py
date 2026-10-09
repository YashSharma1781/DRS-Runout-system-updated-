"""Tkinter user interface and application logic for the DRS."""

from __future__ import annotations

import logging
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import cv2
import numpy as np
import PIL.Image
import PIL.ImageTk

from .config import CONFIG, Config
from .overlay import ReviewState, Verdict, apply_review_overlay, letterbox, make_splash
from .video import VideoError, VideoSource

log = logging.getLogger(__name__)


def format_time(seconds: float) -> str:
    minutes, secs = divmod(max(0.0, seconds), 60)
    return f"{int(minutes):02d}:{secs:05.2f}"


class DRSApp:
    def __init__(self, root: tk.Tk, video_path: str | Path | None = None,
                 cfg: Config = CONFIG) -> None:
        self.root = root
        self.cfg = cfg

        self.video: VideoSource | None = None
        self._frame: np.ndarray | None = None
        self._photo: PIL.ImageTk.PhotoImage | None = None

        self._playing = False
        self._speed = cfg.default_speed
        self._play_job: str | None = None

        self.state = ReviewState.IDLE
        self.verdict: Verdict | None = None
        self._dots = 0
        self._review_start = 0.0
        self._review_job: str | None = None

        self._updating_slider = False

        self._build_ui()
        self._bind_keys()
        root.protocol("WM_DELETE_WINDOW", self.close)

        if video_path:
            self.open_video(video_path)
        else:
            self._render()
            self._update_status()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        cfg = self.cfg
        self.root.title(cfg.title)
        self.root.geometry(f"{cfg.initial_width}x{cfg.initial_height + 150}")
        self.root.minsize(cfg.min_width, cfg.min_height)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Menu
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Open video...", accelerator="Ctrl+O",
                              command=self.choose_video)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.close)
        menubar.add_cascade(label="File", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="Keyboard shortcuts", command=self._show_shortcuts)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menubar)

        # Video canvas
        self.canvas = tk.Canvas(self.root, width=cfg.initial_width,
                                height=cfg.initial_height, highlightthickness=0,
                                bg=self._hex(cfg.background))
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda _e: self._render())
        self.canvas.bind("<Button-1>", lambda _e: self.canvas.focus_set())

        # Seek bar
        self.slider_var = tk.DoubleVar(value=0)
        self.slider = ttk.Scale(self.root, from_=0, to=1, variable=self.slider_var,
                                command=self._on_slider, takefocus=False)
        self.slider.grid(row=1, column=0, sticky="ew", padx=12, pady=(8, 2))

        # Controls
        controls = ttk.Frame(self.root, padding=(12, 6))
        controls.grid(row=2, column=0, sticky="ew")
        controls.columnconfigure(1, weight=1)

        playback = ttk.Frame(controls)
        playback.grid(row=0, column=0, sticky="w")
        big, small = self.cfg.step_large, self.cfg.step_small
        self.play_btn = ttk.Button(playback, text="Play", width=8,
                                   command=self.toggle_play, takefocus=False)
        buttons = (
            (f"<< -{big}", lambda: self.step(-big)),
            (f"< -{small}", lambda: self.step(-small)),
            None,
            (f"+{small} >", lambda: self.step(small)),
            (f"+{big} >>", lambda: self.step(big)),
        )
        for item in buttons:
            if item is None:
                self.play_btn.pack(side="left", padx=2)
            else:
                ttk.Button(playback, text=item[0], width=8, command=item[1],
                           takefocus=False).pack(side="left", padx=2)

        speed_box = ttk.Frame(controls)
        speed_box.grid(row=0, column=1)
        ttk.Label(speed_box, text="Speed").pack(side="left", padx=(0, 6))
        self.speed_var = tk.StringVar(value=self._speed_label(self._speed))
        speed_combo = ttk.Combobox(
            speed_box, textvariable=self.speed_var, state="readonly", width=7,
            values=[self._speed_label(s) for s in cfg.speeds], takefocus=False)
        speed_combo.pack(side="left")
        speed_combo.bind("<<ComboboxSelected>>", self._on_speed)

        decision = ttk.Frame(controls)
        decision.grid(row=0, column=2, sticky="e")
        self.out_btn = self._decision_button(decision, "OUT", cfg.out_color,
                                             lambda: self.start_review(Verdict.OUT))
        self.not_out_btn = self._decision_button(decision, "NOT OUT", cfg.not_out_color,
                                                 lambda: self.start_review(Verdict.NOT_OUT))
        self.out_btn.pack(side="left", padx=3)
        self.not_out_btn.pack(side="left", padx=3)
        ttk.Button(decision, text="Reset", width=7, command=self.reset_review,
                   takefocus=False).pack(side="left", padx=(10, 0))

        # Status bar
        self.status_var = tk.StringVar()
        ttk.Label(self.root, textvariable=self.status_var, anchor="w",
                  relief="sunken", padding=(8, 3)).grid(row=3, column=0, sticky="ew")

    def _decision_button(self, parent: tk.Misc, text: str, color: tuple[int, int, int],
                         command) -> tk.Button:
        return tk.Button(parent, text=text, width=9, command=command, fg="white",
                         bg=self._hex(color), activebackground=self._hex(color),
                         activeforeground="white", relief="flat", takefocus=False,
                         font=("Segoe UI", 9, "bold"), cursor="hand2")

    def _bind_keys(self) -> None:
        big, small = self.cfg.step_large, self.cfg.step_small
        bindings = {
            "<space>": self.toggle_play,
            "<Left>": lambda: self.step(-small),
            "<Right>": lambda: self.step(small),
            "<Shift-Left>": lambda: self.step(-big),
            "<Shift-Right>": lambda: self.step(big),
            "<Control-o>": self.choose_video,
            "o": lambda: self.start_review(Verdict.OUT),
            "n": lambda: self.start_review(Verdict.NOT_OUT),
            "r": self.reset_review,
        }
        for sequence, handler in bindings.items():
            self.root.bind(sequence, lambda _e, h=handler: h())

    def _show_shortcuts(self) -> None:
        messagebox.showinfo("Keyboard shortcuts", (
            "Space\t\tPlay / pause\n"
            "Left / Right\tStep 1 frame\n"
            "Shift + Left / Right\tStep 25 frames\n"
            "O\t\tReview: OUT\n"
            "N\t\tReview: NOT OUT\n"
            "R\t\tReset review\n"
            "Ctrl + O\t\tOpen video"
        ), parent=self.root)

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _hex(bgr: tuple[int, int, int]) -> str:
        b, g, r = bgr
        return f"#{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def _speed_label(speed: float) -> str:
        return f"{speed:g}x"

    # -------------------------------------------------------------- video
    def choose_video(self) -> None:
        path = filedialog.askopenfilename(title="Open video",
                                          filetypes=self.cfg.video_filetypes)
        if path:
            self.open_video(path)

    def open_video(self, path: str | Path) -> None:
        try:
            new_video = VideoSource(path)
        except VideoError as exc:
            log.error("%s", exc)
            messagebox.showerror("Cannot open video", str(exc), parent=self.root)
            return

        self._pause()
        self.reset_review(render=False)
        if self.video:
            self.video.release()
        self.video = new_video

        self._updating_slider = True
        self.slider.configure(to=max(1, new_video.frame_count - 1))
        self.slider_var.set(0)
        self._updating_slider = False

        self._show_frame(0)
        self.canvas.focus_set()

    def _show_frame(self, index: int) -> bool:
        if not self.video:
            return False
        frame = self.video.read_at(index)
        if frame is None:
            return False
        self._frame = frame
        self._render()
        self._sync_slider()
        self._update_status()
        return True

    # ----------------------------------------------------------- rendering
    def _render(self) -> None:
        width = max(2, self.canvas.winfo_width())
        height = max(2, self.canvas.winfo_height())

        if self._frame is None:
            img = make_splash(width, height, self.cfg)
        else:
            img = letterbox(self._frame, width, height, self.cfg.background)
            apply_review_overlay(img, self.state, self.verdict, self._dots, self.cfg)

        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self._photo = PIL.ImageTk.PhotoImage(PIL.Image.fromarray(rgb))
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self._photo, anchor="nw")

    def _sync_slider(self) -> None:
        if self.video:
            self._updating_slider = True
            self.slider_var.set(self.video.index)
            self._updating_slider = False

    def _update_status(self) -> None:
        if not self.video:
            self.status_var.set("No video loaded - press Ctrl+O to open one.")
            return
        v = self.video
        state = {
            ReviewState.IDLE: "Ready",
            ReviewState.PENDING: "Decision pending...",
            ReviewState.RESULT: f"Decision: {self.verdict.value if self.verdict else ''}",
        }[self.state]
        self.status_var.set(
            f"{v.path.name}   |   Frame {v.index + 1}/{v.frame_count}   |   "
            f"{format_time(v.index / v.fps)} / {format_time(v.frame_count / v.fps)}   |   "
            f"{self._speed_label(self._speed)}   |   {state}")

    # ------------------------------------------------------------ playback
    def toggle_play(self) -> None:
        if self._playing:
            self._pause()
        else:
            self._play()

    def _play(self) -> None:
        if not self.video or self.state is ReviewState.PENDING:
            return
        if self.video.index >= self.video.frame_count - 1:
            self._show_frame(0)       # restart from the beginning
        self.reset_review(render=False)
        self._playing = True
        self.play_btn.configure(text="Pause")
        self._tick()

    def _pause(self) -> None:
        self._playing = False
        self.play_btn.configure(text="Play")
        if self._play_job:
            self.root.after_cancel(self._play_job)
            self._play_job = None

    def _tick(self) -> None:
        if not self._playing or not self.video:
            return
        started = time.perf_counter()
        nxt = self.video.index + 1
        if nxt >= self.video.frame_count or not self._show_frame(nxt):
            self._pause()
            return
        spent_ms = (time.perf_counter() - started) * 1000
        delay = max(1, int(self.video.frame_interval_ms / self._speed - spent_ms))
        self._play_job = self.root.after(delay, self._tick)

    def step(self, delta: int) -> None:
        if not self.video or self.state is ReviewState.PENDING:
            return
        self._pause()
        self.reset_review(render=False)
        self._show_frame(self.video.index + delta)

    def _on_slider(self, value: str) -> None:
        if self._updating_slider or not self.video or self.state is ReviewState.PENDING:
            return
        self._pause()
        self.reset_review(render=False)
        self._show_frame(int(float(value)))

    def _on_speed(self, _event: tk.Event) -> None:
        self._speed = float(self.speed_var.get().rstrip("x"))
        self.canvas.focus_set()
        self._update_status()

    # -------------------------------------------------------------- review
    def start_review(self, verdict: Verdict) -> None:
        if not self.video or self.state is ReviewState.PENDING:
            return
        self._pause()
        self.verdict = verdict
        self.state = ReviewState.PENDING
        self._dots = 0
        self._review_start = time.perf_counter()
        log.info("Review started: %s", verdict.value)
        self._review_tick()

    def _review_tick(self) -> None:
        elapsed_ms = (time.perf_counter() - self._review_start) * 1000
        if elapsed_ms >= self.cfg.pending_ms:
            self.state = ReviewState.RESULT
            self._review_job = None
            log.info("Verdict: %s", self.verdict.value if self.verdict else None)
        else:
            self._dots = int(elapsed_ms // self.cfg.dot_interval_ms)
            self._review_job = self.root.after(self.cfg.dot_interval_ms // 2,
                                               self._review_tick)
        self._render()
        self._update_status()

    def reset_review(self, render: bool = True) -> None:
        if self._review_job:
            self.root.after_cancel(self._review_job)
            self._review_job = None
        self.state = ReviewState.IDLE
        self.verdict = None
        self._dots = 0
        if render:
            self._render()
            self._update_status()

    # ------------------------------------------------------------ shutdown
    def close(self) -> None:
        self._pause()
        self.reset_review(render=False)
        if self.video:
            self.video.release()
        self.root.destroy()