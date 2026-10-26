"""ThinkingAnimation: a spinner with a live token counter, shown while the model works.

Your original spinner, extended:
  * a thread-safe token counter  (`add_tokens`, `reset`, `tokens`)
  * idempotent start/stop, and it only clears a line it actually drew
  * a short delay before the first frame, so back-to-back start/stop (the harness
    stops it around every emitted event) never flickers
  * disabled automatically when stdout is not a terminal (pipes, tests, logs)
  * falls back to plain ASCII frames when the terminal cannot show the unicode ones

Typical use (see Harness._emit): stop() before printing anything, start() after.
"""
from __future__ import annotations

import random
import sys
import threading
from typing import Optional, TextIO

UNICODE_FRAMES = ["✢", "✳", "✵","✼", "✻", "✶", "✼", "✽"]
ASCII_FRAMES = ["|", "/", "-", "\\"]

DIM = "\033[2m"
CLEAR_LINE = "\r\033[2K"


def format_tokens(n: int) -> str:
    """1234 -> '1.2k'; small numbers are shown exactly."""
    return str(n) if n < 1000 else f"{n / 1000:.1f}k"


class ThinkingAnimation:
    """A simple spinner that runs in a separate thread with a synchronized stdout lock."""

    def __init__(
        self,
        message: Optional[str] = None,           # fixed label; None = pick a random action per start()
        color_code: str = "\033[38;2;227;114;94m",
        speed: float = 5,                        # frames per second
        *,
        stream: Optional[TextIO] = None,         # defaults to sys.stdout at write time
        enabled: Optional[bool] = None,          # None = only when the stream is a TTY
        ascii_only: Optional[bool] = None,       # None = auto-detect from the stream encoding
        first_frame_delay: float = 0.15,
    ):
        self.message = message
        self.color_code = color_code
        self.reset_code = "\033[0m"
        self.speed = 1 / speed
        self.first_frame_delay = first_frame_delay
        self._stream = stream

        out = self._out()
        self.enabled = out.isatty() if enabled is None else enabled
        if ascii_only is None:
            encoding = (getattr(out, "encoding", None) or "").lower().replace("-", "")
            ascii_only = encoding not in ("utf8", "utf8sig")
        self.ascii_only = ascii_only
        self.frames = ASCII_FRAMES if ascii_only else UNICODE_FRAMES

        self.actions = [
            "Doodling",
            "Thinking",
            "Unfolding",
            "Discombulating",
            "Reconstructing",
            "Doomscrolling",
            "Killing it",
            "Pondering",
            "Brewing",
            "Digging"
        ]
        self.action = message or random.choice(self.actions)

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._drawn = False
        self.lock = threading.Lock()              # synchronizes stdout access
        self._count_lock = threading.Lock()
        self._tokens = 0

    # ------------------------------------------------------------------ token counter
    @property
    def tokens(self) -> int:
        return self._tokens

    def add_tokens(self, n: int = 1) -> None:
        """Called from the model-streaming thread. Negative n corrects an over-count."""
        with self._count_lock:
            self._tokens = max(0, self._tokens + n)

    def reset(self) -> None:
        """Zero the counter (call at the start of each turn)."""
        with self._count_lock:
            self._tokens = 0

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        """Start the spinner. No-op if it is already running or disabled."""
        if not self.enabled or (self._thread and self._thread.is_alive()):
            return
        self.action = self.message or random.choice(self.actions)
        self._stop_event.clear()
        self._drawn = False
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the spinner and clear its line. No-op if not running."""
        if not self._thread:
            return
        self._stop_event.set()
        self._thread.join()
        self._thread = None
        with self.lock:
            if self._drawn:                       # don't clear lines we didn't draw
                out = self._out()
                out.write(CLEAR_LINE)
                out.flush()
            self._drawn = False

    # ------------------------------------------------------------------ internals
    def _out(self) -> TextIO:
        return self._stream if self._stream is not None else sys.stdout

    def _label(self, frame: str) -> str:
        text = f"{self.color_code}{frame} {self.action}…{self.reset_code}"
        n = self._tokens
        if n > 0:
            arrow = "" if self.ascii_only else "↓ "
            text += f" {DIM}({arrow}{format_tokens(n)} tokens){self.reset_code}"
        return text

    def _animate(self) -> None:
        if self._stop_event.wait(self.first_frame_delay):
            return
        idx = 0
        while not self._stop_event.is_set():
            frame = self.frames[idx % len(self.frames)]
            with self.lock:
                out = self._out()
                out.write(f"{CLEAR_LINE}{self._label(frame)}")
                out.flush()
                self._drawn = True
            self._stop_event.wait(self.speed)
            idx += 1
