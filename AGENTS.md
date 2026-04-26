# Repository Guidelines

## Project Structure & Module Organization

This is a PlatformIO firmware reference for an ESP32 hardware buddy. Core firmware lives in `src/`: `main.cpp` owns the event loop and UI, `ble_bridge.cpp` handles Nordic UART BLE transport, `data.h` defines JSON payloads, `character.cpp` and `xfer.h` handle GIF character loading, and `stats.h` stores NVS-backed settings. ASCII buddy renderers are one species per file in `src/buddies/`. Example GIF packs live in `characters/`, docs in `README.md`, `REFERENCE.md`, and `docs/`, and utility scripts in `tools/`.

## Build, Test, and Development Commands

- `pio run` builds the default PlatformIO environment.
- `pio run -e m5stickc-plus` builds for the original M5StickC Plus.
- `pio run -e m5sticks3` builds for M5 StickS3.
- `pio run -t upload` flashes the selected environment to a connected device.
- `pio run -t erase && pio run -t upload` wipes and reflashes a device.
- `pio run -t uploadfs` uploads LittleFS character assets.
- `python3 tools/flash_character.py characters/bufo` stages the example pack and uploads it over USB.
- `python3 tools/test_serial.py` and `python3 tools/test_xfer.py` smoke-test serial JSON state updates and folder transfer.

## Coding Style & Naming Conventions

Follow the existing Arduino C++ style: two-space indentation, same-line braces, `static` file-local helpers, `const` globals for pins and colors, and compact enum names such as `P_SLEEP` or `DISP_NORMAL`. Keep board-specific behavior behind compile flags like `BUDDY_BOARD_S3`. Use descriptive lowercase filenames, with one buddy species per `src/buddies/<name>.cpp`.

## Testing Guidelines

There is no standalone unit test framework. Run `pio run` before submitting firmware changes. For BLE, serial parsing, file transfer, LittleFS, display rendering, buttons, or IMU state, verify on hardware with the relevant `tools/test_*.py` script or manual pairing through Claude Desktop developer mode. Keep new smoke tests as executable Python 3 files under `tools/` named `test_<feature>.py`.

## Commit & Pull Request Guidelines

History currently uses Conventional Commits, for example `feat: initial-commit`; keep subjects short and imperative, such as `fix: handle empty character manifest`. This repository accepts narrow fixes to the reference implementation and protocol docs. Pull requests should explain the bug or doc issue, list tested boards and commands, link related issues, and include photos or screenshots for visible UI/rendering changes. Avoid unrelated refactors, dependency bumps, new pets, or board ports.

## Security & Configuration Tips

Do not commit generated `data/` contents, local serial ports, credentials, or private desktop logs. Treat `REFERENCE.md` as the stable protocol contract when changing BLE payloads or transport behavior.
