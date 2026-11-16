"""Exercise setup against a local WLED API fixture; no controller is needed."""

import copy
import json
import subprocess
import sys
import threading
import unittest
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import party_presets
import wled_setup

EFFECTS = [
    "Solid",
    "Glitter",
    "Rainbow",
    "Bpm",
    "Fade",
    "Breathe",
    "Meteor",
    "Twinklefox",
    "Fire 2012",
    "Aurora",
    "Wipe",
    "Theater",
    "Running",
    "Rainbow Runner",
    "Colorwaves",
    "Chase Rainbow",
]
PALETTES = ["Default", "Aurora", "Party", "Fairy Reaf", "Fire"]


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "id": {"name": "Existing controller"},
            "hw": {
                "led": {
                    "ins": [
                        {"pin": [23], "start": 0, "len": 37},
                        {"pin": [25], "start": 37, "len": 19},
                    ]
                }
            },
        }
        self.state = {"bri": 77, "seg": [{"id": 0}, {"id": 1}]}
        self.presets = {
            "1": {
                "n": "Existing scene",
                "seg": [
                    {"id": 0, "start": 0, "stop": 37},
                    {"id": 2, "stop": 0},
                ],
            },
            "42": {"n": "Custom scene", "on": False},
        }
        self.effects = EFFECTS.copy()
        self.reject_upload = False
        self.writes = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, data):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())

            def do_GET(self):
                self.reply(
                    {
                        "/json/cfg": owner.config,
                        "/json/state": owner.state,
                        "/json/info": {
                            "ver": "fixture",
                            "leds": {"count": owner.config["hw"]["led"].get("total", 56)},
                        },
                        "/json/eff": owner.effects,
                        "/json/pal": PALETTES,
                        "/presets.json": owner.presets,
                    }[self.path]
                )

            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                owner.writes.append(self.path)
                if self.path == "/upload":
                    message = BytesParser(policy=default).parsebytes(
                        b"Content-Type: "
                        + self.headers["Content-Type"].encode()
                        + b"\r\nMIME-Version: 1.0\r\n\r\n"
                        + body
                    )
                    part = next(message.iter_parts())
                    if part.get_filename() != "presets.json":
                        self.send_error(400)
                        return
                    if not owner.reject_upload:
                        owner.presets = json.loads(part.get_payload(decode=True))
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"File Uploaded!")
                    return
                data = json.loads(body)
                if self.path == "/json/cfg":
                    owner.config.update(data)
                elif "psave" in data:
                    ident = str(data["psave"])
                    owner.presets[ident] = (
                        {"playlist": data["playlist"]}
                        if "playlist" in data
                        else copy.deepcopy(owner.state)
                    )
                    owner.presets[ident]["n"] = data["n"]
                else:
                    if "seg" in data:
                        for segment in data.pop("seg"):
                            existing = next(
                                s for s in owner.state["seg"] if s["id"] == segment["id"]
                            )
                            existing.update(segment)
                    owner.state.update(data)
                self.reply({"success": True})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_setup_uses_requested_hardware_and_resolves_effect_names(self):
        with patch.object(wled_setup.time, "sleep"):
            wled_setup.configure(self.host, 2346, pins=(23, 25), leds_per_strip=37)
        led = self.config["hw"]["led"]
        self.assertEqual(led["total"], 74)
        self.assertEqual(led["maxpwr"], 2346)
        self.assertEqual(
            [(b["pin"], b["start"], b["len"], b["maxpwr"]) for b in led["ins"]],
            [([23], 0, 37, 1173), ([25], 37, 37, 1173)],
        )
        self.assertEqual(self.config["id"]["name"], "Existing controller")
        first = self.presets["1"]["seg"]
        self.assertEqual(
            [(s["start"], s["stop"], s["fx"]) for s in first], [(0, 37, 2), (37, 74, 2)]
        )
        self.assertEqual(self.presets["7"]["seg"][1]["pal"], 3)
        self.assertEqual(self.presets["12"]["playlist"]["dur"], [150])
        self.assertEqual(self.config["def"], {"ps": 1, "on": True, "bri": 255})
        self.assertEqual(self.presets["42"], {"n": "Custom scene", "on": False})

    def test_missing_effect_fails_before_modifying_controller(self):
        self.effects.remove("Aurora")
        with self.assertRaisesRegex(ValueError, "Missing effect: Aurora"):
            wled_setup.configure(self.host, 2000)
        self.assertEqual(self.writes, [])

    def test_party_cli_preserves_existing_scenes_and_uses_actual_bus_ranges(self):
        original = copy.deepcopy(self.presets)
        state = copy.deepcopy(self.state)
        with TemporaryDirectory() as directory:
            output = Path(directory) / "presets.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/party_presets.py"),
                    "--host",
                    self.host,
                    "--output",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text()), self.presets)
        for key, value in original.items():
            self.assertEqual(self.presets[key], value)
        self.assertEqual(self.state, state)
        segments = self.presets["13"]["seg"]
        self.assertEqual(
            [(s["start"], s["stop"], s["n"]) for s in segments],
            [(0, 37, "Strip 1 - GPIO 23"), (37, 56, "Strip 2 - GPIO 25")],
        )
        self.assertEqual(self.presets["18"]["seg"][0]["fx"], 1)
        self.assertEqual(self.presets["18"]["seg"][0]["pal"], 2)
        self.assertEqual(self.presets["19"]["playlist"]["ps"], [13, 14, 15, 16, 17, 18])

    def test_party_detects_upload_that_was_not_saved(self):
        self.reject_upload = True
        with self.assertRaisesRegex(RuntimeError, "did not retain"):
            party_presets.configure(self.host)

    def test_cli_rejects_invalid_hardware_before_network_access(self):
        for args in (
            ["--milliamps", "2000", "--pins", "18", "18"],
            ["--milliamps", "2000", "--pins", "34", "19"],
            ["--milliamps", "0"],
            ["--milliamps", "2000", "--leds-per-strip", "0"],
            [],
        ):
            with self.subTest(args=args):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "scripts/wled_setup.py"),
                        "--host",
                        self.host,
                        *args,
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 2)
        self.assertEqual(self.writes, [])


if __name__ == "__main__":
    unittest.main()
