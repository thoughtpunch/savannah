"""WebSocket server for real-time simulation visualization."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import websockets
from websockets.datastructures import Headers
from websockets.http11 import Response

logger = logging.getLogger(__name__)

LIVE_HTML = Path(__file__).parent.parent / "viz" / "live.html"


class LiveServer:
    """Serves live.html and broadcasts simulation state over WebSocket."""

    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.clients: set = set()
        self._command_queue: asyncio.Queue = asyncio.Queue()
        self._server = None
        self.paused = False
        self.step_requested = False
        self.tick_delay_ms = 200

    async def start(self) -> None:
        """Start the WebSocket server."""
        self._server = await websockets.serve(
            self._handler,
            self.host,
            self.port,
            process_request=self._serve_http,
        )
        logger.info("Live server running at http://%s:%d", self.host, self.port)

    def _serve_http(self, connection, request):
        """Serve live.html for regular HTTP requests (non-WebSocket)."""
        # Only intercept non-upgrade requests (regular HTTP GET)
        if request.headers.get("Upgrade", "").lower() == "websocket":
            return None  # Let WebSocket handler take over

        path = request.path
        if path in ("/", "/index.html", "/live.html"):
            if LIVE_HTML.exists():
                body = LIVE_HTML.read_bytes()
                headers = Headers([
                    ("Content-Type", "text/html; charset=utf-8"),
                    ("Content-Length", str(len(body))),
                ])
                return Response(200, "OK", headers, body)
            headers = Headers([("Content-Type", "text/plain")])
            return Response(404, "Not Found", headers, b"live.html not found")

        # API endpoints for history
        if path == "/api/runs":
            return self._api_list_runs()
        if path.startswith("/api/runs/") and "/tick/" in path:
            return self._api_get_tick(path)
        if path.startswith("/api/runs/") and path.endswith("/config"):
            return self._api_get_config(path)

        # Return 404 for unknown paths to prevent WebSocket handler rejection
        headers = Headers([("Content-Type", "text/plain")])
        return Response(404, "Not Found", headers, b"Not Found")

    def _json_response(self, data: dict | list) -> Response:
        """Return a JSON HTTP response."""
        body = json.dumps(data).encode()
        headers = Headers([
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(body))),
            ("Access-Control-Allow-Origin", "*"),
        ])
        return Response(200, "OK", headers, body)

    def _api_list_runs(self) -> Response:
        """List past experiment runs from data/ directory."""
        import yaml
        data_dir = Path("data")
        runs = []
        if data_dir.exists():
            for d in sorted(data_dir.iterdir(), reverse=True):
                if d.is_dir() and d.name.startswith("exp_"):
                    run = {"name": d.name, "path": str(d)}
                    config_path = d / "config.yaml"
                    if config_path.exists():
                        try:
                            cfg = yaml.safe_load(config_path.read_text())
                            run["ticks"] = cfg.get("simulation", {}).get("ticks", 0)
                            run["agents"] = cfg.get("agents", {}).get("count", 0)
                            run["perturbation"] = cfg.get("perturbation", {}).get("enabled", False)
                        except Exception:
                            pass
                    # Find actual tick count by checking tick files
                    ticks_dir = d / "logs" / "ticks"
                    if ticks_dir.exists():
                        tick_files = list(ticks_dir.glob("*.json"))
                        run["actual_ticks"] = len(tick_files)
                        if tick_files:
                            run["last_tick"] = max(int(f.stem) for f in tick_files)
                    runs.append(run)
        return self._json_response(runs)

    def _api_get_tick(self, path: str) -> Response:
        """Get a specific tick snapshot: /api/runs/<name>/tick/<n>."""
        parts = path.split("/")
        # /api/runs/<name>/tick/<n>
        if len(parts) >= 6:
            run_name = parts[3]
            tick_num = int(parts[5])
            tick_path = Path("data") / run_name / "logs" / "ticks" / f"{tick_num:06d}.json"
            if tick_path.exists():
                data = json.loads(tick_path.read_text())
                return self._json_response(data)
        headers = Headers([("Content-Type", "application/json")])
        return Response(404, "Not Found", headers, b'{"error":"not found"}')

    def _api_get_config(self, path: str) -> Response:
        """Get run config: /api/runs/<name>/config."""
        parts = path.split("/")
        if len(parts) >= 5:
            run_name = parts[3]
            config_path = Path("data") / run_name / "config.yaml"
            if config_path.exists():
                import yaml
                data = yaml.safe_load(config_path.read_text())
                return self._json_response(data)
        headers = Headers([("Content-Type", "application/json")])
        return Response(404, "Not Found", headers, b'{"error":"not found"}')

    async def _handler(self, ws) -> None:
        """Handle a single WebSocket client connection."""
        self.clients.add(ws)
        logger.info("Client connected (%d total)", len(self.clients))
        try:
            async for message in ws:
                try:
                    cmd = json.loads(message)
                    await self._command_queue.put(cmd)
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON from client: %s", message[:100])
        except websockets.ConnectionClosed:
            pass
        finally:
            self.clients.discard(ws)
            logger.info("Client disconnected (%d remaining)", len(self.clients))

    async def broadcast(self, data: dict) -> None:
        """Send data to all connected clients."""
        if not self.clients:
            return
        msg = json.dumps(data)
        # Send to all, ignore individual failures
        await asyncio.gather(
            *[client.send(msg) for client in self.clients],
            return_exceptions=True,
        )

    async def get_command(self) -> dict | None:
        """Non-blocking check for a client command."""
        try:
            return self._command_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def drain_commands(self) -> list[dict]:
        """Get all pending commands."""
        commands = []
        while True:
            try:
                commands.append(self._command_queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return commands

    async def wait_for_command(self, timeout: float = 0.1) -> dict | None:
        """Blocking wait for a command with timeout."""
        try:
            return await asyncio.wait_for(self._command_queue.get(), timeout)
        except TimeoutError:
            return None

    async def handle_pause_loop(self) -> None:
        """Block until resume or step command received."""
        while self.paused and not self.step_requested:
            cmd = await self.wait_for_command(timeout=0.1)
            if cmd:
                action = cmd.get("action")
                if action == "resume":
                    self.paused = False
                    await self.broadcast({"type": "status", "state": "running"})
                    return
                elif action == "step":
                    self.step_requested = True
                    return
                elif action == "stop":
                    raise asyncio.CancelledError("Stop requested")
                elif action == "speed":
                    self.tick_delay_ms = cmd.get("delay_ms", 200)

    async def process_commands(self) -> None:
        """Process any pending commands. Call each tick."""
        for cmd in await self.drain_commands():
            action = cmd.get("action")
            if action == "pause":
                self.paused = True
                await self.broadcast({"type": "status", "state": "paused"})
            elif action == "resume":
                self.paused = False
                await self.broadcast({"type": "status", "state": "running"})
            elif action == "speed":
                self.tick_delay_ms = cmd.get("delay_ms", 200)
            elif action == "stop":
                raise asyncio.CancelledError("Stop requested")

    async def stop(self) -> None:
        """Shut down the server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("Live server stopped")
