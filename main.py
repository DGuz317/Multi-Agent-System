import os
import sys
import time
import socket
import threading
import subprocess
from enum import Enum, auto
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed


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
    live: bool = field(default=False, init=False, repr=False)
    _error_log: list[str] = field(default_factory=list, init=False, repr=False)


HOST = "127.0.0.1"

# Add / remove services here.
# Layout: first entry = MCP gateway,
#         middle entries = sub-agents,
#         last entry = root agent.
SERVICES: list[ServiceConfig] = [
    # MCP Server
    ServiceConfig("MCP", "mcp_server/my_mcp_server.py", 8001, StartMode.SCRIPT),
    # Sub-agents
    ServiceConfig("Exchange Agent", "root_agent.sub_agent.agent:app", 8002, StartMode.UVICORN),
    # Root agent
    ServiceConfig("Root", "root_agent.agent:app", 10000, StartMode.UVICORN),
]


def _pipe_to_stdout(pipe, svc: ServiceConfig) -> None:
    """Stream lines to stdout — suppressed until the service is confirmed live."""
    try:
        with pipe:
            for raw in iter(pipe.readline, b""):
                line = raw.decode().rstrip()
                svc._error_log.append(line)
                if svc.live:
                    print(f"[{svc.name}] {line}", flush=True)
    except Exception:
        pass


def _print_error_log(svc: ServiceConfig) -> None:
    """Dump captured output for a failed service (last 30 lines)."""
    if not svc._error_log:
        print(f"  (no output captured for {svc.name})")
        return
    print(f"\n{'─' * 50}")
    print(f"📋 Last output from [{svc.name}]:")
    print(f"{'─' * 50}")
    for line in svc._error_log[-30:]:
        print(f"  {line}")
    print(f"{'─' * 50}\n")


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex((HOST, port)) == 0


def _wait_for_service(svc: ServiceConfig) -> bool:
    """Block until *svc* is reachable on its port or its timeout expires."""
    deadline = time.monotonic() + svc.startup_timeout
    while time.monotonic() < deadline:
        if _port_open(svc.port):
            svc.live = True   # open the log stream
            return True
        time.sleep(0.5)
    return False


def _build_cmd(svc: ServiceConfig) -> list[str]:
    if svc.mode is StartMode.SCRIPT:
        return [sys.executable, svc.target]
    return [
        sys.executable, "-m", "uvicorn", svc.target,
        "--host", HOST,
        "--port", str(svc.port),
    ]


def _build_env(svc: ServiceConfig) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd() + os.pathsep + env.get("PYTHONPATH", "")
    if svc.mode is StartMode.SCRIPT:
        env["PORT"] = str(svc.port)
    return env


def _launch(svc: ServiceConfig) -> subprocess.Popen:
    """Spawn *svc* and wire its combined stdout/stderr to a daemon logger thread."""
    proc = subprocess.Popen(
        _build_cmd(svc),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=_build_env(svc),
    )
    threading.Thread(
        target=_pipe_to_stdout,
        args=(proc.stdout, svc),
        daemon=True,
    ).start()
    print(f"🚀 Launched [{svc.name}] — PID {proc.pid}, port {svc.port}")
    return proc


def _terminate_all(procs: list[subprocess.Popen]) -> None:
    for p in procs:
        try:
            p.terminate()
        except OSError:
            pass


def _start_mcp(svc: ServiceConfig, procs: list) -> bool:
    print(f"\n{'═' * 50}")
    print("==MCP Server==")
    procs.append(_launch(svc))
    print(f"⏳ Waiting for [{svc.name}] on port {svc.port}…")
    if _wait_for_service(svc):
        print(f"✅ [{svc.name}] is ONLINE → http://{HOST}:{svc.port}\n")
        return True
    _print_error_log(svc)
    print(f"💥 [{svc.name}] failed to start — aborting.")
    return False


def _start_sub_agents(sub_agents: list[ServiceConfig], procs: list) -> bool:
    if not sub_agents:
        return True

    print(f"{'═' * 50}")
    print("==Sub-agents==")
    for svc in sub_agents:
        procs.append(_launch(svc))

    results: dict[str, bool] = {}
    with ThreadPoolExecutor(max_workers=len(sub_agents)) as pool:
        future_to_svc = {pool.submit(_wait_for_service, svc): svc for svc in sub_agents}
        for future in as_completed(future_to_svc):
            svc = future_to_svc[future]
            results[svc.name] = future.result()

    any_failed = False
    for svc in sub_agents:
        if results[svc.name]:
            print(f"✅ [{svc.name}] is ONLINE → http://{HOST}:{svc.port}")
        else:
            any_failed = True
            print(f"⚠️  [{svc.name}] FAILED to start.")
            _print_error_log(svc)

    if not any(results.values()):
        print("\n💥 All sub-agents failed — aborting (root has nothing to coordinate).")
        return False
    if any_failed:
        print("\n⚠️  System will continue in DEGRADED mode (some sub-agents offline).")
    print()
    return True


def _start_root(svc: ServiceConfig, procs: list) -> bool:
    print(f"{'═' * 50}")
    print("==Root Agent==")
    procs.append(_launch(svc))
    print(f"⏳ Waiting for [{svc.name}] on port {svc.port}…")
    if _wait_for_service(svc):
        print(f"✅ [{svc.name}] is ONLINE → http://{HOST}:{svc.port}\n")
        return True
    _print_error_log(svc)
    print(f"💥 [{svc.name}] failed to start — aborting.")
    return False


def main() -> None:
    mcp_svc, *sub_agents, root_svc = SERVICES

    procs: list[subprocess.Popen] = []
    print("🛠️  Initializing Multi-Agent System…")

    try:
        if not _start_mcp(mcp_svc, procs):
            return
        if not _start_sub_agents(sub_agents, procs):
            return
        if not _start_root(root_svc, procs):
            return

        print("✨ ALL SYSTEMS ONLINE — streaming combined logs:\n" + "─" * 50)
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Shutdown signal received — terminating all agents…")
    finally:
        _terminate_all(procs)
        print("✅ Cleanup complete.")


if __name__ == "__main__":
    main()