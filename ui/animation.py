import sys
import time
import threading
import random
from typing import Optional

# Global reference to the active animation to allow control from other modules
active_animation: Optional["ThinkingAnimation"] = None

class ThinkingAnimation:
    """A simple spinner animation that runs in a separate thread with synchronization lock"""
    
    def __init__(self, message:str="Thinking", color_code:str = "\033[38;2;227;114;94m", speed:float=5):
        self.message = message
        self.color_code = color_code
        self.reset_code = "\033[0m"
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.lock = threading.Lock() # Lock for synchronized stdout access
        
        self.speed = 1/speed
        self.frames =  ["·", "✢", "✶", "✻", "✽", "✻", "✶", "✢"]
        self.actions = [
            "Doodling",
            "Thinking",
            "Unfolding",
            "Finding",
            "Reconstructing",
            "Doomscrolling",
            "Killing braincell"
        ]
        self.action = random.choice(self.actions)
        
    def _animate(self):
        idx = 0
        while not self._stop_event.is_set():
            frame = self.frames[idx % len(self.frames)]
            with self.lock:
                sys.stdout.write(f"\r{self.color_code}{frame} {self.action} {self.reset_code}")
                sys.stdout.flush()
            time.sleep(self.speed)
            idx += 1
            
    def start(self):
        """Start the spinner animation"""
        global active_animation
        active_animation = self
        self.action = random.choice(self.actions)
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()
    
    def stop(self):
        """Stop the spinner and clear its line. No-op if not running."""
        if not self._thread:
            return                      # <- key fix: don't clear lines you didn't draw
        self._stop_event.set()
        self._thread.join()
        self._thread = None
        with self.lock:
            sys.stdout.write("\r\033[2K")   # erase whole line, any terminal width
            sys.stdout.flush()
        global active_animation
        active_animation = None