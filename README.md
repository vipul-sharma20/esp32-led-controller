# ESP32 LED controller

Configure two WS2812B LED strips on an ESP32 using [WLED](https://kno.wled.ge/).
Includes USB Wi-Fi provisioning, 17 lighting scenes, two playlists, and an
optional serial wiring diagnostic. Uses WLED's standard web interface.

> [!NOTE]
> My room’s lights stopped working, and I had spare LED strips and an ESP32 lying around. So I put them to use.
> See the [microblog post](https://vipul.xyz/micro/2026/11/16/2142/).

## Hardware

- ESP32-WROOM-32 development board with USB.
- Two 5V WS2812B strips; defaults are 300 LEDs per strip on GPIO18 and GPIO19.
- Regulated 5V supply sized for the LEDs, wiring, connectors, and fuses.
- A 74AHCT125 level shifter and a 330Ω series resistor per data input are recommended.

| Connection | Strip 1 | Strip 2 |
| --- | --- | --- |
| Data input (DIN) | GPIO18 through shifter and resistor | GPIO19 through shifter and resistor |
| +5V | External supply V+ | External supply V+ |
| GND | Supply V− and ESP32 GND | Supply V− and ESP32 GND |

Power the ESP32 development board by USB and the strips directly from the supply.
Connect every ground together. Never connect 5V to a GPIO or 3V3 pin. Wire with
power off; follow the strip labels rather than assuming wire colors. Long strips
may need fused power injection to prevent voltage drop.

WLED's current limiter is an estimate, not electrical protection. Setup enables
full software brightness within the specified current budget. Start with a low
budget and increase only after checking the supply and wiring.

## Setup

1. Install compatible ESP32 firmware using the [official WLED installer](https://install.wled.me/).
2. Join a 2.4GHz Wi-Fi network using WLED's setup interface, or use USB provisioning below.
3. Back up existing WLED configuration and presets before running the scripts.

Use Python 3.10 or newer. Network setup needs only Python's standard library;
USB provisioning also needs `pyserial`:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows, activate with `.venv\Scripts\activate` instead.

### Configure over the network

Replace `http://wled.local` with your controller's URL. The 2000mA budget below
is an example, not a recommendation for every installation.

```sh
python scripts/wled_setup.py --host http://wled.local --milliamps 2000
python scripts/party_presets.py --host http://wled.local
```

The first command configures two outputs, replaces preset slots 1–12, and selects
Rainbow flow as the startup scene. It cycles through scenes while saving them.
Wi-Fi settings and controller identity are left unchanged.
The second replaces slots 13–19 without changing the running scene or other presets.
Both commands write to the controller; neither flashes firmware.

Override the output pins and equal-length strip size when needed:

```sh
python scripts/wled_setup.py --host http://wled.local --milliamps 2000 \
  --pins 18 19 --leds-per-strip 60
```

Choose available output-capable GPIOs using your board's pinout. Some GPIOs affect
boot mode or are reserved by board peripherals. The party script reads lengths
and pins from the controller rather than assuming the defaults.

### Provision Wi-Fi over USB

Use the serial port listed by `python -m serial.tools.list_ports`, for example
`/dev/ttyUSB0` on Linux or `COM3` on Windows:

```sh
python scripts/wled_setup.py --port /dev/ttyUSB0 --ssid "YOUR_WIFI_NAME" --milliamps 2000
```

The password prompt is hidden. Credentials are sent to the controller through
WLED's Improv serial protocol; the script does not save them to project files or
read saved system credentials. Omit `--ssid` if the controller is already connected.
Close other serial monitors first. If serial provisioning is unavailable in your
firmware, use WLED's setup interface and `--host` instead.

## Scenes and examples

Slots 1–11: Rainbow flow, Solid color, Warm evening, Slow color fade, Gentle
breathe, Comet, Twinkling stars, Cozy fire, Aurora, Color wipe, and Theater chase.
Slot 12: Demo loop, 15 seconds per scene.

Slots 13–18: Running lights, Rainbow runner, Party color waves, Party beat,
Rainbow chase, and Disco glitter. Slot 19: Party mix, 12 seconds per scene.
These scenes do not require a microphone. Scenes preserve the master brightness.

`config/leds.example.json` shows the two-output configuration with an example
2000mA budget. `config/presets.example.json` contains the scene export for two
300-LED strips. It uses firmware-specific effect and palette IDs; prefer the
scripts, which resolve IDs by name and check availability before writing.
Firmware versions may rename or omit effects. Examples contain no Wi-Fi settings
and are not full device backups.

To save the updated presets locally, append
`--output config/presets.local.json` to the party command. Local exports and
backups are ignored by Git; review any files before publishing them.

## Optional wiring diagnostic

`src/main.cpp` is a standalone Arduino sketch, **not the WLED firmware**.
It identifies GPIO18 in green and GPIO19 in blue at brightness 32/255.
Edit `LEDS_PER_STRIP` and the pins to match your hardware.

With [PlatformIO](https://platformio.org/) installed:

```sh
pio run
# WARNING: replaces WLED on the connected board.
pio run --target upload
pio device monitor --baud 115200
```

Serial commands: `i` identify, `r` red, `g` green, `b` blue, `w` white, `o` off.
This sketch has no current limiter or Wi-Fi. Reinstall WLED to restore its UI.

## Development

```sh
python -m unittest discover -s tests -v
pio run
```

Tests exercise the scripts against a local HTTP fixture, not physical LEDs.
Do not expose WLED's control API to the public internet.

References: [WLED JSON API](https://kno.wled.ge/interfaces/json-api/),
[serial provisioning](https://kno.wled.ge/interfaces/serial/),
[LED wiring practices](https://learn.adafruit.com/adafruit-neopixel-uberguide/best-practices).

## License

[MIT](LICENSE) for this toolkit. WLED and Adafruit NeoPixel are separate projects
with their own licenses; their source and firmware are not bundled here.
