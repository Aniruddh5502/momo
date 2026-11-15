# ollama_server.py
import os
import signal
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional


class OllamaServer:
    """
    Lifecycle manager for a local `ollama serve` subprocess.

    Always injects LLAMA_ARG_SWA_FULL=1 so SWA-based models
    (LFM3, Qwen-hybrid, DeepSeek-V4, etc.) get a full-size SWA KV
    cache. Without it, llama.cpp uses a tiny (n_swa * n_ctx_slot)
    cache and invalidates context checkpoints at the sliding-window
    boundary, forcing the agent to reprocess ~1K tokens per turn.

    Usage
    -----
        server = OllamaServer(log_file="logs/ollama.log")
        server.start()
        try:
            ...  # agent calls hit http://127.0.0.1:11434
        finally:
            server.stop()

    Or as a context manager:

        with OllamaServer():
            ...

    Or registered at import time:

        atexit.register(server.stop)
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 11434,
        log_file: Optional[str] = "logs/ollama_server.log",
        startup_timeout: float = 60.0,
        extra_env: Optional[dict] = None,
    ):
        self.host = host
        self.port = port
        self.log_file = Path(__file__).parent / "logs" / f"ollama_server_{str(time.ctime()).replace(":","_")}.log"
        self.startup_timeout = startup_timeout
        self.extra_env = extra_env or {}
        self._process: Optional[subprocess.Popen] = None
        self._log_handle = None
        self._lock = threading.Lock()
        self._started = False

        
    # -------------------------------------------------------------- env
    def _build_env(self) -> dict:
        env = os.environ.copy()

        # THE FIX: full-size SWA cache. llama.cpp reads this directly
        # from the environment; no CLI flag needs to appear.
        env["LLAMA_ARG_SWA_FULL"] = "1"

        # Keep model resident so the KV cache survives between turns.
        env.setdefault("OLLAMA_KEEP_ALIVE", "-1")

        # One agent = one slot; avoids slot thrashing.
        env.setdefault("OLLAMA_NUM_PARALLEL", "1")

        # Must match the base_url your ChatOllama uses.
        env["OLLAMA_HOST"] = f"{self.host}:{self.port}"

        env.update(self.extra_env)
        return env

    # ------------------------------------------------------------- util
    def _port_open(self) -> bool:
        try:
            with socket.create_connection((self.host, self.port), timeout=0.5):
                return True
        except OSError:
            return False

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._started

    # ------------------------------------------------------------ start
    def start(self) -> None:
        with self._lock:
            if self._started:
                return

            if self._port_open():
                self._started = True
                return

            env = self._build_env()

            if self.log_file:
                Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)
                self._log_handle = open(self.log_file, "w", encoding="utf-8", buffering=1)
                stdout = self._log_handle
                stderr = subprocess.STDOUT
            else:
                stdout = subprocess.DEVNULL
                stderr = subprocess.DEVNULL

            kwargs = dict(
                args=["ollama", "serve"],
                env=env,
                stdout=stdout,
                stderr=stderr,
            )
            if os.name == "nt":
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                kwargs["start_new_session"] = True

            try:
                self._process = subprocess.Popen(**kwargs)
            except FileNotFoundError as e:
                raise RuntimeError(
                    "`ollama` not found on PATH. Install Ollama or fix PATH."
                ) from e

            deadline = time.time() + self.startup_timeout
            while time.time() < deadline:
                if self._process.poll() is not None:
                    self._cleanup_after_failed_start()
                    raise RuntimeError(
                        f"`ollama serve` exited early (code {self._process.returncode}). "
                        f"See {self.log_file}"
                    )
                if self._port_open():
                    self._started = True
                    return
                time.sleep(0.2)

            self._cleanup_after_failed_start()
            raise TimeoutError(
                f"`ollama serve` not ready within {self.startup_timeout}s"
            )

    def _cleanup_after_failed_start(self) -> None:
        proc = self._process
        self._process = None
        if proc is not None and proc.poll() is None:
            try:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                proc.wait(timeout=5)
            except Exception:
                pass
        if self._log_handle:
            try:
                self._log_handle.close()
            except Exception:
                pass
            self._log_handle = None
        self._started = False

    # ------------------------------------------------------------- stop
    def stop(self) -> None:
        with self._lock:
            proc = self._process
            self._process = None

            try:
                if proc is not None and proc.poll() is None:
                    if os.name == "nt":
                        # /T kills the whole tree (ollama serve + llama-server.exe).
                        # TerminateProcess alone leaves llama-server orphaned.
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    elif os.name == "linux":
                        try:
                            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                        except ProcessLookupError:
                            pass

                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        try:
                            proc.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            pass
            finally:
                if self._log_handle:
                    try:
                        self._log_handle.close()
                    except Exception:
                        pass
                    self._log_handle = None
                if self._started:
                    pass
                self._started = False

    # ---------------------------------------------------- context manager
    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stop()
        return False

if __name__=="__main__":
    ollama = OllamaServer(
        host="127.0.0.1",
        port=11434
    )
    
    print("starting ollama server")
    ollama.start()
    time.sleep(10)
    ollama.stop()
    print("stopped ollama server")