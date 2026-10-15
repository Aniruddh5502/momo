import json, os, subprocess, tempfile
from typing import TypedDict, Literal, List, Optional, Dict, Any
from pathlib import Path
from langchain_core.tools import tool
from momo.tools.registry import ToolContext

try:
    import fcntl
    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False

# ============================================================================
# CONFIGURATION
# ============================================================================

MAX_REPLAN_HISTORY = 20
MAX_RETRIES = 5  # For Windows file locking retries
RETRY_DELAY = 0.2  # seconds

VALID_STATUSES = {"pending", "in_progress", "done", "failed", "superseded"}
MAX_VERIFY_OUTPUT = 4000  # chars

class Task(TypedDict):
    id              :   str
    name            :   str
    deliverable     :   str
    verify_cmd      :   str
    depends_on      :   list[str]
    status          :   Literal["pending", "in_progress", "done", "failed", "superseded"]
    evidence        :   Optional[str]

class TaskValidationError(ValueError):
    """Raised when task input from the agent fails validation."""
    pass

def normalize_task(t: Dict[str, Any], strict: bool = False) -> Task:
    tid = t.get("id")
    name = t.get("name")
    verify_cmd = t.get("verify_cmd")

    if strict:
        if not tid or not isinstance(tid, str):
            raise TaskValidationError(f"Task missing required 'id': {t!r}")
        if not name or not isinstance(name, str):
            raise TaskValidationError(f"Task '{tid}' missing required 'name'.")
        if not verify_cmd or not isinstance(verify_cmd, str):
            raise TaskValidationError(f"Task '{tid}' missing required 'verify_cmd'.")

    depends_on = t.get("depends_on", [])
    if not isinstance(depends_on, list):
        depends_on = [depends_on] if depends_on else []

    status = t.get("status", "pending")
    if status not in VALID_STATUSES:
        status = "pending"

    return {
        "id": str(tid) if tid else "unknown",
        "name": str(name) if name else "Unnamed Task",
        "deliverable": str(t.get("deliverable", "No deliverable specified")),
        "verify_cmd": str(verify_cmd) if verify_cmd else "true",
        "depends_on": [str(d) for d in depends_on],
        "status": status,
        "evidence": t.get("evidence"),
    }

def _detect_cycle(candidate_state: Dict[str, Task]) -> Optional[List[str]]:
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {tid: WHITE for tid in candidate_state}
    path: List[str] = []

    def visit(tid: str) -> Optional[List[str]]:
        color[tid] = GRAY
        path.append(tid)
        for dep in candidate_state.get(tid, {}).get("depends_on", []):
            if dep not in candidate_state:
                continue
            if color.get(dep) == GRAY:
                return path[path.index(dep):] + [dep]
            if color.get(dep, WHITE) == WHITE:
                cyc = visit(dep)
                if cyc:
                    return cyc
        path.pop()
        color[tid] = BLACK
        return None

    for tid in candidate_state:
        if color[tid] == WHITE:
            cyc = visit(tid)
            if cyc:
                return cyc
    return None

def _missing_dependencies(candidate_state: Dict[str, Task]) -> Dict[str, List[str]]:
    missing = {}
    for tid, t in candidate_state.items():
        gone = [d for d in t.get("depends_on", []) if d not in candidate_state]
        if gone:
            missing[tid] = gone
    return missing

class _StateLock:
    def __init__(self, lock_file: Path):
        self.lock_file = lock_file

    def __enter__(self):
        if _HAS_FCNTL:
            self._fh = open(self.lock_file, "w")
            fcntl.flock(self._fh, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        if _HAS_FCNTL:
            fcntl.flock(self._fh, fcntl.LOCK_UN)
            self._fh.close()

def load(state_file: Path) -> Dict[str, Task]:
    if state_file.exists():
        try:
            raw_data = json.loads(state_file.read_text())
            if isinstance(raw_data, dict):
                return {tid: normalize_task(tval) for tid, tval in raw_data.items()}
            else:
                return {}
        except Exception:
            backup = state_file.with_suffix(".json.bak")
            if backup.exists():
                try:
                    raw_data = json.loads(backup.read_text())
                    return {tid: normalize_task(tval) for tid, tval in raw_data.items()}
                except Exception:
                    return {}
            else:
                return {}
    else:
        return {}

def save(state: Dict[str, Task], state_file: Path, lock_file: Path):
    with _StateLock(lock_file):
        if state_file.exists():
            try:
                state_file.replace(state_file.with_suffix(".json.bak"))
            except Exception:
                pass
        fd, tmp_path = tempfile.mkstemp(dir=str(state_file.parent), prefix=".state_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(state, f, indent=4)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, state_file)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

def can_start(state: Dict[str, Task], task_id: str) -> tuple[bool, str]:
    if task_id not in state:
        return False, "Task ID not found."

    task = state[task_id]
    if task.get("status") != "pending":
        return False, f"Task is already {task.get('status')}."

    for dep_id in task.get("depends_on", []):
        dep = state.get(dep_id)
        if not dep or dep.get("status") != "done":
            return False, f"Dependency {dep_id} is not done."

    for t_id, t_val in state.items():
        if t_val.get("status") == "in_progress":
            return False, f"Task {t_id} is currently in progress."

    return True, "Ready to start."

def _run_verify(cmd: str, workspace_dir: Path) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=str(workspace_dir),
            capture_output=True,
            text=True,
            timeout=30
        )
        output = result.stdout + result.stderr
        if len(output) > MAX_VERIFY_OUTPUT:
            output = output[:MAX_VERIFY_OUTPUT] + f"\n...[truncated, {len(output)} chars total]"
        return (result.returncode == 0), output
    except subprocess.TimeoutExpired:
        return False, "Verification command timed out after 30s."
    except Exception as e:
        return False, str(e)

def create_task_state_tools(ctx: ToolContext):
    # State paths derived from context
    state_dir = ctx.project_root / ".momo" / "state"
    state_file = state_dir / "state.json"
    lock_file = state_dir / "state.lock"
    workspace_dir = ctx.project_root

    @tool
    def task_init(tasks: List[Dict[str, Any]]) -> str:
        """
        Initializes the project plan. Replaces any existing plan.
        Args:
            tasks: List of task objects. Required per task: id, name, verify_cmd.
                   Optional: deliverable, depends_on.
        """
        if not tasks:
            return "Error: tasks list is empty."

        try:
            new_state: Dict[str, Task] = {}
            for t in tasks:
                norm_t = normalize_task(t, strict=True)
                if norm_t["id"] in new_state:
                    raise TaskValidationError(f"Duplicate task id in plan: '{norm_t['id']}'")
                norm_t["status"] = "pending"
                new_state[norm_t["id"]] = norm_t
        except TaskValidationError as e:
            return f"Error: {str(e)}"

        missing = _missing_dependencies(new_state)
        if missing:
            return f"Error: Tasks reference unknown dependencies: {missing}"

        cycle = _detect_cycle(new_state)
        if cycle:
            return f"Error: Dependency cycle detected: {' -> '.join(cycle)}"

        try:
            save(new_state, state_file, lock_file)
        except Exception as e:
            return f"Error saving state: {str(e)}"

        return f"Successfully initialized {len(new_state)} task(s): {', '.join(new_state.keys())}"

    @tool
    def task_update(id: str, action: Literal["start", "submit"], evidence: Optional[str] = None) -> str:
        """
        Updates the state of a task.
        - 'start': Moves pending -> in_progress.
        - 'submit': Runs verify_cmd. Success -> done, Fail -> failed. Optional
          `evidence` (e.g. a summary of what was done) is stored on the task.
        """
        state = load(state_file)

        if id not in state:
            return f"Error: Task {id} not found."

        if action not in ("start", "submit"):
            return f"Error: Unknown action '{action}'."

        try:
            if action == "start":
                allowed, reason = can_start(state, id)
                if not allowed:
                    return f"Error: {reason}"

                state[id]["status"] = "in_progress"
                save(state, state_file, lock_file)
                return f"Task {id} started."

            # action == "submit"
            if state[id].get("status") != "in_progress":
                return "Error: Task must be in_progress to submit."

            verify_cmd = state[id].get("verify_cmd", "true")
            success, output = _run_verify(verify_cmd, workspace_dir)

            if evidence:
                state[id]["evidence"] = evidence

            if success:
                state[id]["status"] = "done"
                save(state, state_file, lock_file)
                return f"Task {id} verified and completed."
            else:
                state[id]["status"] = "failed"
                save(state, state_file, lock_file)
                return f"Error: Verification failed for task {id}.\nCommand: {verify_cmd}\nOutput: {output}"
        except Exception as e:
            return f"Error updating task: {str(e)}"

    @tool
    def task_replan(failed_task_id: str, reason: str, new_tasks: List[Dict[str, Any]]) -> str:
        """
        Retires a failed task and inserts replacement tasks.
        """
        state = load(state_file)

        if failed_task_id not in state or state[failed_task_id].get("status") != "failed":
            return "Error: Task must be 'failed' to replan."

        if not new_tasks:
            return "Error: new_tasks is empty."

        try:
            candidate = dict(state)
            candidate[failed_task_id] = {**candidate[failed_task_id], "status": "superseded"}

            added_ids = []
            for t in new_tasks:
                norm_t = normalize_task(t, strict=True)
                existing = state.get(norm_t["id"])
                if existing and existing.get("status") not in ("failed", "superseded"):
                    raise TaskValidationError(f"Replacement task id '{norm_t['id']}' collides with an existing active task.")
                norm_t["status"] = "pending"
                candidate[norm_t["id"]] = norm_t
                added_ids.append(norm_t["id"])
        except TaskValidationError as e:
            return f"Error: {str(e)}"

        missing = _missing_dependencies(candidate)
        if missing:
            return f"Error: Tasks reference unknown dependencies: {missing}"

        cycle = _detect_cycle(candidate)
        if cycle:
            return f"Error: Dependency cycle detected: {' -> '.join(cycle)}"

        for aid in added_ids:
            if failed_task_id in candidate[aid].get("depends_on", []):
                return f"Error: New task '{aid}' depends on superseded task '{failed_task_id}'."

        try:
            save(candidate, state_file, lock_file)
        except Exception as e:
            return f"Error saving replan: {str(e)}"

        log_entry = f"Replan: Task {failed_task_id} failed. Reason: {reason}. Added {len(new_tasks)} new tasks: {added_ids}.\n"
        try:
            with open(state_dir / "progress.log", "a") as f:
                f.write(log_entry)
        except Exception:
            pass

        return f"Successfully replanned {failed_task_id} into {len(added_ids)} new task(s): {', '.join(added_ids)}"

    @tool
    def task_clear() -> str:
        """Resets the entire task state."""
        try:
            if state_file.exists():
                state_file.unlink()
            backup = state_file.with_suffix(".json.bak")
            if backup.exists():
                backup.unlink()
        except Exception as e:
            return f"Error clearing state: {str(e)}"

        return "Task state cleared successfully."

    return [task_init, task_update, task_replan, task_clear]
