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

## Daemon (recommended)

A direct CLI call has to connect over BLE each time (1-5 s). The daemon keeps the connection, reconnects automatically, re-applies the last state after a reconnect, and serves a localhost-only HTTP API:

```bash
stacklight daemon --initial available --off-on-exit
```

While it runs, the CLI routes through it automatically (instant). Anything that can make an HTTP request can drive the light (hotkeys, macOS Shortcuts, Stream Deck, AutoHotkey, Raycast):

```bash
curl -X POST http://127.0.0.1:8765/state/meeting
```

Endpoints: `GET /status`, `POST /state/<name>`, `POST /color/<RRGGBB>`, `POST /brightness/<v>`, `POST /effect/<name>`.

## Start at login

macOS (launchd): create `~/Library/LaunchAgents/com.stacklight.daemon.plist` with ProgramArguments `[<path to stacklight>, daemon, --initial, available]`, RunAtLoad true, KeepAlive true, then `launchctl load` it. The first run will prompt for Bluetooth permission for the terminal/Python.

Windows: Task Scheduler, trigger "At log on", action `stacklight.exe daemon --initial available` (use `pythonw -m stacklight daemon ...` to hide the console).

Linux (systemd user unit): `ExecStart=%h/.local/bin/stacklight daemon --initial available`, `Restart=always`, then `systemctl --user enable --now stacklight`.

## Tests

```bash
pip install -e 'host[dev]' && pytest host
```
