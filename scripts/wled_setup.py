"""Provision WLED over USB and configure two addressable LED outputs."""

import argparse
import getpass
import json
import time
import urllib.request
import uuid


class Improv:
    def __init__(self, port):
        import serial

        self.serial = serial.Serial(port=None, baudrate=115200, timeout=0.2)
        self.serial.dtr = False
        self.serial.rts = False
        self.serial.port = port
        self.serial.open()
        self.buffer = bytearray()
        time.sleep(3)
        self.serial.reset_input_buffer()

    def send(self, command, strings=()):
        data = b"".join(bytes([len(s.encode())]) + s.encode() for s in strings)
        rpc = bytes([command, len(data)]) + data
        packet = b"IMPROV" + bytes([1, 3, len(rpc)]) + rpc
        self.serial.write(packet + bytes([sum(packet) & 255]))
        self.serial.flush()

    def packets(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.buffer.extend(self.serial.read(4096))
            while True:
                start = self.buffer.find(b"IMPROV")
                if start < 0:
                    self.buffer = self.buffer[-5:]
                    break
                if start:
                    del self.buffer[:start]
                if len(self.buffer) < 9:
                    break
                length = 10 + self.buffer[8]
                if len(self.buffer) < length:
                    break
                packet = bytes(self.buffer[:length])
                del self.buffer[:length]
                if sum(packet[:-1]) & 255 != packet[-1]:
                    continue
                yield packet[7], packet[9:-1]

    @staticmethod
    def strings(payload):
        data, result = payload[2:], []
        while data:
            size = data[0]
            if len(data) < size + 1:
                raise ValueError("Invalid Improv response")
            result.append(data[1 : 1 + size].decode())
            data = data[1 + size :]
        return result


def provision(port, ssid=None):
    device = Improv(port)
    try:
        device.send(3)
        for kind, payload in device.packets(2):
            if kind == 4:
                print("Controller:", device.strings(payload), flush=True)
        if ssid:
            password = getpass.getpass("Wi-Fi password (hidden): ")
            device.send(1, [ssid, password])
            del password
            print("Connecting ESP32 to", ssid, flush=True)
            for kind, payload in device.packets(40):
                if kind == 4 and payload and payload[0] in (1, 2):
                    urls = device.strings(payload)
                    if urls:
                        print("CONNECTED:", urls[0], flush=True)
                        return urls[0]
                elif kind == 2 and payload and payload[0]:
                    print("Provisioning status:", payload[0], flush=True)
            raise SystemExit(
                "Wi-Fi connection not confirmed; check SSID, password and 2.4 GHz availability."
            )
        device.send(2)
        for kind, payload in device.packets(3):
            if kind == 4 and payload and payload[0] == 2:
                urls = device.strings(payload)
                if urls:
                    print("Already connected:", urls[0], flush=True)
                    return urls[0]
        raise SystemExit("Controller is not connected. Pass --ssid to join a 2.4 GHz network.")
    finally:
        device.serial.close()


def request(host, path, payload=None):
    req = urllib.request.Request(host.rstrip("/") + path)
    if payload is not None:
        req.data = json.dumps(payload, ensure_ascii=False).encode()
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response)


def upload_file(host, name, data):
    boundary = "wled-" + uuid.uuid4().hex
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="data"; filename="{name}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode()
    body += data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        host.rstrip("/") + "/upload",
        data=body,
        headers={"Content-Type": "multipart/form-data; boundary=" + boundary},
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        result = response.read().decode()
        if "File Uploaded!" not in result:
            raise ValueError("WLED upload failed: " + result)


def configure(host, milliamps, pins=(18, 19), leds_per_strip=300):
    effects = request(host, "/json/eff")
    palettes = request(host, "/json/pal")
    config = {
        "hw": {
            "led": {
                "total": leds_per_strip * 2,
                "maxpwr": milliamps,
                "fps": 40,
                "ins": [
                    {
                        "pin": [pin],
                        "start": i * leds_per_strip,
                        "len": leds_per_strip,
                        "type": 22,
                        "order": 0,
                        "ledma": 55,
                        "maxpwr": milliamps // 2,
                    }
                    for i, pin in enumerate(pins)
                ],
            }
        },
        "sv": True,
    }

    def effect(name):
        return effects.index(name)

    def palette(name):
        return palettes.index(name)

    def segments(fx, colors, pal=0, speed=100, intensity=128):
        return [
            {
                "id": i,
                "n": f"Strip {i + 1} - GPIO {pin}",
                "start": i * leds_per_strip,
                "stop": (i + 1) * leds_per_strip,
                "on": True,
                "bri": 255,
                "sel": True,
                "fx": fx,
                "sx": speed,
                "ix": intensity,
                "pal": pal,
                "col": colors,
                "rev": False,
                "mi": False,
                "grp": 1,
                "spc": 0,
            }
            for i, pin in enumerate(pins)
        ]

    warm = [[255, 160, 70], [0, 0, 0], [255, 80, 10]]
    presets = [
        ("Rainbow flow", "Rainbow", warm, 0, 100, 128),
        ("Solid color", "Solid", [[255, 100, 20], [0, 0, 0], [0, 0, 0]], 0, 128, 128),
        ("Warm evening", "Solid", warm, 0, 128, 128),
        ("Slow color fade", "Fade", [[255, 50, 0], [40, 0, 255], [0, 200, 140]], 0, 50, 128),
        ("Gentle breathe", "Breathe", [[0, 140, 255], [0, 0, 0], [0, 0, 0]], 0, 65, 128),
        ("Comet", "Meteor", [[0, 200, 255], [0, 0, 0], [0, 0, 0]], 0, 115, 150),
        ("Twinkling stars", "Twinklefox", warm, palette("Fairy Reaf"), 65, 150),
        ("Cozy fire", "Fire 2012", warm, palette("Fire"), 95, 130),
        ("Aurora", "Aurora", warm, palette("Aurora"), 65, 120),
        ("Color wipe", "Wipe", [[255, 0, 110], [0, 150, 255], [0, 0, 0]], 0, 80, 128),
        ("Theater chase", "Theater", [[255, 140, 30], [0, 0, 0], [0, 0, 0]], 0, 95, 128),
    ]
    for _, fx, *_ in presets:
        if fx not in effects:
            raise ValueError(f"Missing effect: {fx}")
    print(
        f"Configuring two {leds_per_strip}-LED outputs; current limit: {milliamps} mA", flush=True
    )
    request(host, "/json/cfg", config)
    time.sleep(3)
    for ident, (name, fx, colors, pal, speed, intensity) in enumerate(presets, 1):
        state = {
            "on": True,
            "transition": 10,
            "mainseg": 0,
            "seg": segments(effect(fx), colors, pal, speed, intensity),
        }
        request(host, "/json/state", state)
        time.sleep(0.15)
        # Preserve the user's brightness when changing scenes.
        request(host, "/json/state", {"psave": ident, "n": name, "ib": False, "sb": True})
        time.sleep(0.3)
        print("Saved preset", ident, name, flush=True)
    request(
        host,
        "/json/state",
        {
            "psave": 12,
            "n": "Demo loop",
            "o": True,
            "playlist": {
                "ps": [1, 4, 5, 6, 7, 8, 9, 10, 11],
                "dur": [150],
                "transition": [20],
                "repeat": 0,
                "end": 1,
            },
        },
    )
    time.sleep(0.5)
    print("Saved preset 12 Demo loop (15 seconds per scene)", flush=True)
    # Saving a playlist starts it; explicitly stop it before selecting the boot scene.
    request(host, "/json/state", {"seg": [{"id": 0, "fx": effect("Rainbow")}]})
    request(host, "/json/state", {"on": True, "bri": 255, "ps": 1})
    request(host, "/json/cfg", {"def": {"ps": 1, "on": True, "bri": 255}, "sv": True})
    state = request(host, "/json/state")
    info = request(host, "/json/info")
    if info["leds"]["count"] != leds_per_strip * 2 or len(state["seg"]) != 2 or state["bri"] != 255:
        raise RuntimeError("Controller state does not match the requested configuration")
    print("Verified:", info["ver"], f"{leds_per_strip * 2} LEDs, 2 segments; UI:", host, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", help="Skip provisioning and configure this WLED URL")
    parser.add_argument(
        "--ssid", help="Join this 2.4 GHz network; prompt for password without echo"
    )
    parser.add_argument("--port", help="Serial port for USB provisioning")
    parser.add_argument(
        "--milliamps",
        type=int,
        required=True,
        help="Total current budget in mA; choose for your supply and wiring",
    )
    parser.add_argument("--pins", type=int, nargs=2, default=[18, 19], metavar=("STRIP1", "STRIP2"))
    parser.add_argument("--leds-per-strip", type=int, default=300)
    args = parser.parse_args()
    if not args.host and not args.port:
        parser.error("Pass --host for network setup or --port for USB provisioning")
    if args.host and (args.port or args.ssid):
        parser.error("Use --host alone, or --port with optional --ssid")
    if args.leds_per_strip < 1 or args.milliamps < args.leds_per_strip * 2:
        parser.error("LED count must be positive and current budget at least 1 mA per LED")
    if len(set(args.pins)) != 2 or any(
        pin not in {2, 4, 5, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33}
        for pin in args.pins
    ):
        parser.error("Choose two distinct ESP32 output GPIOs; see the board pinout")
    host = args.host or provision(args.port, args.ssid)
    configure(host, args.milliamps, args.pins, args.leds_per_strip)
