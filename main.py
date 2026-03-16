import os
import sys
import time
import socket
import threading
import subprocess
from enum import Enum, auto
from typing import Optional
from dataclasses import dataclass, field


class StartMode(Enum):
    SCRIPT = auto()
    UVICORN = auto()

@dataclass
class ServiceConfig:
    name: str
    target: str
    port: int
    mode: StartMode
    startup_timeout: int = 15
    _error_log: list[str] = field(default_factory=list, init=False, repr=False)

# Add / remove services here.
SERVICES: list[ServiceConfig] = [
    # MCP server
    ServiceConfig("MCP", "mcp_server/my_mcp_server.py", 8001, StartMode.SCRIPT),
    # Sub Agent
    ServiceConfig("Exchange-Agent", "root_agent.sub_agent.agent:app", 8002, StartMode.UVICORN),
    # Root Agent
    ServiceConfig("Root", "root_agent.agent:app", 10000, StartMode.UVICORN),
]

# all others whose mode == UVICORN and port < ROOT port are sub-agents.

_UVICORN_KEEP = (
    "Application startup complete.",
    "Uvicorn running on",
)

def _pipe_to_stdout(pipe, prefix: str, mode: StartMode, error_log: list[str]) -> None:
    """
    Forward lines from *pipe* to stdout, tagged with *prefix*.
    All lines are also buffered into *error_log* for post-mortem reporting.
    """
    try:
        with pipe:
            for raw in iter(pipe.readline, b""):
                line = raw.decode().rstrip()
                error_log.append(line)
                if mode is StartMode.UVICORN:
                    if not any(marker in line for marker in _UVICORN_KEEP):
                        continue
                print(f"[{prefix}] {line}")
    except Exception:
        pass

def _print_error_log(svc: ServiceConfig) -> None:
    """
    Dump the captured log for a failed service.
        """
    if not svc._error_log:
        print(f"  (no output captured for {svc.name})")
        return
    print(f"\n{'─' * 50}")
    print(f"📋 Last output from {svc.name}:")
    print(f"{'─' * 50}")
    for line in svc._error_log[-30:]:   # cap at last 30 lines
        print(f"  {line}")
    print(f"{'─' * 50}\n")

def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0

def _wait_for_service(svc: ServiceConfig, silent: bool = False) -> bool:
    """
    Block until *svc* is reachable or its timeout expires. Returns success.
    """
    if not silent:
        print(f"⏳ Waiting for {svc.name} on port {svc.port}…")
    deadline = time.monotonic() + svc.startup_timeout
    while time.monotonic() < deadline:
        if _port_open(svc.port):
            if not silent:
                print(f"✅ {svc.name} is LIVE.")
            return True
        time.sleep(0.5)
    if not silent:
        print(f"🛑 {svc.name} did not respond within {svc.startup_timeout}s.")
    return False

def _build_cmd(svc: ServiceConfig) -> list[str]:
    if svc.mode is StartMode.SCRIPT:
        return [sys.executable, svc.target]
    return [sys.executable, "-m", "uvicorn", svc.target,
            "--host", "127.0.0.1", "--port", str(svc.port)]

def _build_env(svc: ServiceConfig) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd() + os.pathsep + env.get("PYTHONPATH", "")
    if svc.mode is StartMode.SCRIPT:
        env["PORT"] = str(svc.port)
    return env

def launch(svc: ServiceConfig) -> subprocess.Popen:
    """
    Spawn *svc* and wire its stdout/stderr to a daemon logger thread.
    """
    proc = subprocess.Popen(
        _build_cmd(svc),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=_build_env(svc),
    )
    threading.Thread(
        target=_pipe_to_stdout, args=(proc.stdout, svc.name, svc.mode, svc._error_log), daemon=True
    ).start()
    print(f"🚀 Launched {svc.name} (PID {proc.pid}) on port {svc.port}")
    return proc


def main() -> None:
    gateway, *sub_agents, root = SERVICES
    procs: list[subprocess.Popen] = []

    print("🛠️  Initializing Multi-Agent System…")

    try:
        procs.append(launch(gateway))
        if not _wait_for_service(gateway):
            _print_error_log(gateway)
            print("💥 Gateway failed. Aborting startup.")
            return

        for svc in sub_agents:
            procs.append(launch(svc))
        results = {svc.name: _wait_for_service(svc, silent=True) for svc in sub_agents}

        any_sub_failed = False
        for svc in sub_agents:
            if not results[svc.name]:
                any_sub_failed = True
                print(f"⚠️  {svc.name} failed to start.")
                _print_error_log(svc)

        procs.append(launch(root))
        results[root.name] = _wait_for_service(root, silent=True)

        print()
        for svc in [*sub_agents, root]:
            if results[svc.name]:
                print(f"✅ {svc.name} is LIVE.")
            else:
                print(f"🛑 {svc.name} is OFFLINE.")

        if not results[root.name]:
            _print_error_log(root)
            print("💥 Root agent failed. Aborting startup.")
            return

        if any_sub_failed:
            print("⚠️  System started with degraded sub-agents (see above).")

        print("\n✨ ALL SYSTEMS ONLINE — combined log stream:\n" + "─" * 50)
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Shutdown signal received. Terminating all agents…")
    finally:
        for p in procs:
            p.terminate()
        print("✅ Cleanup complete.")

if __name__ == "__main__":
    main()