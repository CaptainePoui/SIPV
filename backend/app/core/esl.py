"""
FreeSWITCH ESL (Event Socket Library) — async inbound client.

Protocol: TCP text-based.
  1. FreeSWITCH sends "Content-Type: auth/request\n\n"
  2. Client sends "auth <password>\n\n"
  3. FreeSWITCH confirms "+OK accepted"
  4. Client sends commands; FreeSWITCH replies with headers + body.

Each packet = headers block (terminated by \n\n) + optional body (Content-Length bytes).
"""
import asyncio
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_CONNECT_TIMEOUT = 5.0
_READ_TIMEOUT = 15.0


class ESLClient:
    """Async FreeSWITCH ESL inbound client. One connection, one lock."""

    def __init__(self, host: str, port: int, password: str):
        self.host = host
        self.port = port
        self.password = password
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False
        self._lock = asyncio.Lock()

    # ── Connection ─────────────────────────────────────────────────────────────

    async def connect(self) -> bool:
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=_CONNECT_TIMEOUT,
            )
            # Read auth challenge
            await self._read_packet()
            # Authenticate
            self._writer.write(f"auth {self.password}\n\n".encode())
            await self._writer.drain()
            _, body = await self._read_packet()
            if "+OK accepted" in body or "+OK" in body:
                self._connected = True
                logger.info("ESL connected to FreeSWITCH at %s:%d", self.host, self.port)
                return True
            logger.error("ESL auth rejected: %s", body)
            return False
        except Exception as exc:
            logger.error("ESL connection failed: %s", exc)
            self._connected = False
            return False

    async def disconnect(self):
        self._connected = False
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── Low-level packet reader ────────────────────────────────────────────────

    async def _read_packet(self) -> tuple[dict, str]:
        """Read one ESL packet. Returns (headers dict, body string)."""
        # Headers end at \n\n
        raw_headers = await asyncio.wait_for(
            self._reader.readuntil(b"\n\n"),
            timeout=_READ_TIMEOUT,
        )
        headers: dict[str, str] = {}
        for line in raw_headers.decode(errors="replace").strip().split("\n"):
            if ": " in line:
                k, v = line.split(": ", 1)
                headers[k.strip()] = v.strip()

        # Body only if Content-Length present
        body = ""
        if "Content-Length" in headers:
            n = int(headers["Content-Length"])
            body_bytes = await asyncio.wait_for(
                self._reader.readexactly(n),
                timeout=_READ_TIMEOUT,
            )
            body = body_bytes.decode("utf-8", errors="replace")
        else:
            # Reply-Text carries the result inline in headers
            body = headers.get("Reply-Text", "")

        return headers, body

    # ── Commands ───────────────────────────────────────────────────────────────

    async def _send(self, command: str) -> tuple[dict, str]:
        """Send a raw ESL command and return the reply packet."""
        async with self._lock:
            if not self._connected:
                raise RuntimeError("ESL not connected")
            self._writer.write(f"{command}\n\n".encode())
            await self._writer.drain()
            return await self._read_packet()

    async def api(self, command: str) -> str:
        """
        Blocking API call — waits for result.
        Example: await esl.api("sofia status")
        """
        _, body = await self._send(f"api {command}")
        return body.strip()

    async def bgapi(self, command: str) -> str:
        """
        Background API call — returns Job-UUID immediately.
        Example: await esl.bgapi("reloadxml")
        """
        headers, _ = await self._send(f"bgapi {command}")
        return headers.get("Job-UUID", "").strip()

    async def reload_xml(self) -> str:
        """Reload FreeSWITCH XML configuration (mod_xml_curl cache invalidated)."""
        return await self.api("reloadxml")

    async def sofia_status(self) -> str:
        """Return sofia SIP status (profiles, gateways, registrations)."""
        return await self.api("sofia status")

    async def sofia_contact(self, profile: str, user_at_domain: str) -> str:
        """Check if a SIP endpoint is registered. Returns contact URI or empty."""
        return await self.api(f"sofia_contact {profile}/{user_at_domain}")

    async def show_registrations(self) -> str:
        """List all current SIP registrations."""
        return await self.api("show registrations as json")

    async def sofia_status_profile_reg(self, profile: str) -> str:
        """
        Detail text (PAS JSON -- 'show registrations as json' n'a pas ces champs) avec
        Ping-Status/Ping-Time/EXPSECS par registration. TASK-S020.2.
        """
        return await self.api(f"sofia status profile {profile} reg")

    async def show_channels(self) -> str:
        """Liste des appels actifs (channels), format JSON. TASK-S020.2."""
        return await self.api("show channels as json")

    async def uuid_getvar(self, call_uuid: str, var: str) -> str:
        """Lit une variable de canal sur un appel actif (ex: stats RTP). TASK-S020.2."""
        return await self.api(f"uuid_getvar {call_uuid} {var}")

    async def uuid_kill(self, uuid: str) -> str:
        """Hang up an active call by UUID."""
        return await self.api(f"uuid_kill {uuid}")

    async def originate(self, endpoint: str, extension: str, context: str, caller_id_name: str = "", caller_id_number: str = "") -> str:
        """Originate an outbound call."""
        vars_parts = []
        if caller_id_name:
            vars_parts.append(f"origination_caller_id_name={caller_id_name}")
        if caller_id_number:
            vars_parts.append(f"origination_caller_id_number={caller_id_number}")
        vars_str = "{" + ",".join(vars_parts) + "}" if vars_parts else ""
        cmd = f"originate {vars_str}{endpoint} {extension} XML {context}"
        return await self.bgapi(cmd)


# ── Singleton ──────────────────────────────────────────────────────────────────

_client: Optional[ESLClient] = None


async def esl_startup():
    """Call at FastAPI startup. Connects ESL; logs warning if FreeSWITCH not reachable yet."""
    global _client
    _client = ESLClient(
        host=settings.FREESWITCH_HOST,
        port=settings.FREESWITCH_ESL_PORT,
        password=settings.FREESWITCH_ESL_PASSWORD,
    )
    ok = await _client.connect()
    if not ok:
        logger.warning(
            "ESL: FreeSWITCH not reachable at startup (%s:%d). "
            "Will reconnect on first API call.",
            settings.FREESWITCH_HOST,
            settings.FREESWITCH_ESL_PORT,
        )


async def esl_shutdown():
    """Call at FastAPI shutdown."""
    global _client
    if _client:
        await _client.disconnect()
        _client = None


async def get_esl() -> ESLClient:
    """
    FastAPI dependency — returns connected ESL client.
    Reconnects automatically if connection was lost.
    """
    global _client
    if _client is None:
        _client = ESLClient(
            host=settings.FREESWITCH_HOST,
            port=settings.FREESWITCH_ESL_PORT,
            password=settings.FREESWITCH_ESL_PASSWORD,
        )
    if not _client.is_connected:
        await _client.connect()
    return _client
