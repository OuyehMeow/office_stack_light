# Host software

Python 3.10+, uses `bleak` (Windows 10+, macOS, Linux/BlueZ).

## Install

```bash
pip install -e host
```

## Use

```bash
stacklight scan
```

```bash
stacklight busy
```

Commands: `available`, `busy`, `meeting`, `custom`, `off`, `color RRGGBB` (sets the custom slot and switches to it), `brightness 0-255|NN%`, `effect solid|breathe|blink`, `status`.

The first successful connect caches the device address in `~/.config/stacklight/config.json`.

## Web UI

Phone-sized control page served by the daemon. Try it without hardware:

```bash
stacklight ui --mock --presence mock
```

This starts the daemon with a simulated light and a scripted Teams presence feed, and opens http://127.0.0.1:8765/ in the browser. Drop `--mock` to drive the real light. Opened without a running daemon (e.g. as a plain file), the page falls back to an in-browser demo.

Layout: light preview on top, status buttons below, split 1.618 : 1. Busy blinks red (1 Hz), available is constant green, meeting breathes blue (4 s), same timing as the firmware.

## Teams presence (preview)

`--presence teams` polls Microsoft Graph `/me/presence` every 30 s and drives the light while "Teams sync" is on. A manual change (UI, CLI, device button) turns sync off; tap "Teams sync" to resume.

Mapping: Available -> available; Busy / DoNotDisturb -> busy; activity InACall / InAConferenceCall / InAMeeting / Presenting -> meeting; Away / BeRightBack / Offline -> off; unknown -> no change.

Setup needs an Entra ID app registration with delegated `Presence.Read`; steps are in `stacklight/presence.py`. Install with `pip install -e 'host[teams]'`. Untested against a live tenant so far.

## Daemon (recommended)

A direct CLI call has to connect over BLE each time (1-5 s). The daemon keeps the connection, reconnects automatically, re-applies the last state after a reconnect, and serves a localhost-only HTTP API:

```bash
stacklight daemon --initial available --off-on-exit
```

While it runs, the CLI routes through it automatically (instant). Anything that can make an HTTP request can drive the light (hotkeys, macOS Shortcuts, Stream Deck, AutoHotkey, Raycast):

```bash
curl -X POST http://127.0.0.1:8765/state/meeting
```

Endpoints (the `/api` prefix is optional): `GET /api/status`, `POST /api/state/<name>`, `POST /api/color/<RRGGBB>`, `POST /api/brightness/<v>`, `POST /api/effect/<name>`, `POST /api/sync/<on|off>`.

## Start at login

macOS (launchd): create `~/Library/LaunchAgents/com.stacklight.daemon.plist` with ProgramArguments `[<path to stacklight>, daemon, --initial, available]`, RunAtLoad true, KeepAlive true, then `launchctl load` it. The first run will prompt for Bluetooth permission for the terminal/Python.

Windows: Task Scheduler, trigger "At log on", action `stacklight.exe daemon --initial available` (use `pythonw -m stacklight daemon ...` to hide the console).

Linux (systemd user unit): `ExecStart=%h/.local/bin/stacklight daemon --initial available`, `Restart=always`, then `systemctl --user enable --now stacklight`.

## Tests

```bash
pip install -e 'host[dev]' && pytest host
```
