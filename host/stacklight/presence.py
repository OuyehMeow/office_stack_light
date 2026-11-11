"""Presence providers: derive the light state from an external status source.

v0.2 prep for Microsoft Teams. The daemon polls a provider and, while "sync" is on,
drives the light from it. A manual change (UI button, CLI, device button) turns sync off.

Teams setup (one-time, needs an Entra ID / Azure AD app registration):
  1. Entra admin center -> App registrations -> New registration.
     Supported account types: your org (or "any org"). No redirect URI needed.
  2. Authentication -> "Allow public client flows" = Yes (device code flow).
  3. API permissions -> Microsoft Graph -> Delegated -> Presence.Read. Some tenants
     require admin consent.
  4. Copy the Application (client) ID and Directory (tenant) ID into
     ~/.config/stacklight/config.json:
        {"teams": {"client_id": "...", "tenant_id": "..."}}
  5. pip install 'stacklight[teams]'   (adds msal)
     stacklight daemon --presence teams   -> prints a device-login code on first run.

Graph endpoint: GET https://graph.microsoft.com/v1.0/me/presence
Response fields used: availability, activity.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import logging
import urllib.request
from dataclasses import dataclass
from typing import Optional, Protocol

from . import protocol as p

log = logging.getLogger("stacklight.presence")

# Activities that mean "in a meeting / call", regardless of availability.
MEETING_ACTIVITIES = {
    "InACall", "InAConferenceCall", "InAMeeting", "Presenting",
}
AVAILABLE = {"Available", "AvailableIdle"}
BUSY = {"Busy", "BusyIdle", "DoNotDisturb"}
AWAY = {"Away", "BeRightBack", "Offline"}


@dataclass(frozen=True)
class Presence:
    availability: str
    activity: str = ""

    def label(self) -> str:
        return self.availability if not self.activity or self.activity == self.availability \
            else f"{self.availability} / {self.activity}"


def map_teams(pr: Presence) -> Optional[p.State]:
    """Teams presence -> light state. None = unknown, leave the light alone."""
    if pr.activity in MEETING_ACTIVITIES:
        return p.State.MEETING
    if pr.availability in AVAILABLE:
        return p.State.AVAILABLE
    if pr.availability in BUSY:
        return p.State.BUSY
    if pr.availability in AWAY:
        return p.State.OFF
    return None  # PresenceUnknown or anything new


class PresenceProvider(Protocol):
    name: str
    interval: float  # seconds between polls

    async def get(self) -> Optional[Presence]: ...


class MockPresenceProvider:
    """Cycles through a scripted sequence. For UI / daemon testing without Teams."""

    name = "mock-teams"

    def __init__(self, interval: float = 15.0, script: Optional[list[Presence]] = None):
        self.interval = interval
        self._it = itertools.cycle(script or [
            Presence("Available", "Available"),
            Presence("Busy", "InACall"),
            Presence("Busy", "Busy"),
            Presence("DoNotDisturb", "Presenting"),
            Presence("Away", "Away"),
        ])

    async def get(self) -> Optional[Presence]:
        return next(self._it)


class TeamsGraphProvider:
    """Reads the signed-in user's Teams presence from Microsoft Graph (delegated, Presence.Read)."""

    name = "teams"
    SCOPES = ["Presence.Read"]
    URL = "https://graph.microsoft.com/v1.0/me/presence"

    def __init__(self, client_id: str, tenant_id: str = "organizations",
                 cache_path=None, interval: float = 30.0):
        try:
            import msal  # optional dependency
        except ImportError as e:
            raise RuntimeError("Teams presence needs msal: pip install 'stacklight[teams]'") from e
        self.interval = interval
        self._cache_path = cache_path
        self._cache = msal.SerializableTokenCache()
        if cache_path and cache_path.exists():
            self._cache.deserialize(cache_path.read_text())
        self._app = msal.PublicClientApplication(
            client_id, authority=f"https://login.microsoftonline.com/{tenant_id}",
            token_cache=self._cache)

    def _save_cache(self) -> None:
        if self._cache_path and self._cache.has_state_changed:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(self._cache.serialize())

    def _token(self) -> str:
        accounts = self._app.get_accounts()
        result = self._app.acquire_token_silent(self.SCOPES, account=accounts[0]) if accounts else None
        if not result:
            flow = self._app.initiate_device_flow(scopes=self.SCOPES)
            if "user_code" not in flow:
                raise RuntimeError(f"device flow failed: {flow.get('error_description', flow)}")
            print(flow["message"], flush=True)  # "To sign in, use a web browser to open ... enter code ..."
            result = self._app.acquire_token_by_device_flow(flow)
        self._save_cache()
        if "access_token" not in result:
            raise RuntimeError(f"auth failed: {result.get('error_description', result)}")
        return result["access_token"]

    def _fetch(self) -> Presence:
        req = urllib.request.Request(self.URL, headers={"Authorization": f"Bearer {self._token()}"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        return Presence(data.get("availability", ""), data.get("activity", ""))

    async def get(self) -> Optional[Presence]:
        # msal + urllib are blocking; keep the event loop (BLE, HTTP API) responsive.
        return await asyncio.to_thread(self._fetch)


def build_provider(kind: Optional[str], config: dict) -> Optional[PresenceProvider]:
    if not kind:
        return None
    if kind == "mock":
        return MockPresenceProvider()
    if kind == "teams":
        t = config.get("teams", {})
        if not t.get("client_id"):
            raise RuntimeError('Teams not configured: add {"teams": {"client_id": ..., "tenant_id": ...}} '
                               "to ~/.config/stacklight/config.json (see stacklight/presence.py)")
        from .device import CONFIG_DIR
        return TeamsGraphProvider(t["client_id"], t.get("tenant_id", "organizations"),
                                  CONFIG_DIR / "msal_cache.json", float(t.get("interval", 30)))
    raise ValueError(f"unknown presence provider {kind!r} (use teams or mock)")
