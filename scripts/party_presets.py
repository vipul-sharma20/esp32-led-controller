"""Add six party scenes and a playlist without changing the running effect."""

import argparse
import json
from pathlib import Path

from wled_setup import request, upload_file


def configure(host, output=None):
    presets = request(host, "/presets.json")
    effects = request(host, "/json/eff")
    palettes = request(host, "/json/pal")
    outputs = request(host, "/json/cfg")["hw"]["led"]["ins"]
    if len(outputs) != 2 or any(bus["len"] < 1 for bus in outputs):
        raise ValueError("Expected two LED outputs; run wled_setup.py first")

    party = [
        (13, "Running lights", "Running", [[0, 200, 255], [40, 0, 80], [255, 0, 100]], 0, 120, 150),
        (
            14,
            "Rainbow runner",
            "Rainbow Runner",
            [[255, 0, 100], [0, 0, 0], [0, 180, 255]],
            0,
            140,
            150,
        ),
        (
            15,
            "Party color waves",
            "Colorwaves",
            [[255, 0, 100], [0, 0, 0], [0, 180, 255]],
            palettes.index("Party"),
            115,
            170,
        ),
        (
            16,
            "Party beat",
            "Bpm",
            [[255, 0, 100], [0, 0, 0], [0, 180, 255]],
            palettes.index("Party"),
            100,
            180,
        ),
        (
            17,
            "Rainbow chase",
            "Chase Rainbow",
            [[255, 0, 100], [0, 0, 0], [0, 180, 255]],
            0,
            145,
            150,
        ),
        (
            18,
            "Disco glitter",
            "Glitter",
            [[255, 0, 100], [0, 0, 0], [0, 180, 255]],
            palettes.index("Party"),
            110,
            160,
        ),
    ]
    for ident, name, fx, colors, palette, speed, intensity in party:
        presets[str(ident)] = {
            "n": name,
            "mainseg": 0,
            "transition": 10,
            "seg": [
                {
                    "id": i,
                    "n": f"Strip {i + 1} - GPIO {bus['pin'][0]}",
                    "start": bus["start"],
                    "stop": bus["start"] + bus["len"],
                    "on": True,
                    "bri": 255,
                    "sel": True,
                    "fx": effects.index(fx),
                    "col": colors,
                    "pal": palette,
                    "sx": speed,
                    "ix": intensity,
                    "grp": 1,
                    "spc": 0,
                    "rev": False,
                    "mi": False,
                }
                for i, bus in enumerate(outputs)
            ],
        }
    presets["19"] = {
        "n": "Party mix",
        "on": True,
        "playlist": {
            "ps": [13, 14, 15, 16, 17, 18],
            "dur": [120] * 6,
            "transition": [15] * 6,
            "repeat": 0,
            "end": 1,
        },
    }
    # Leave existing presets, including WLED's stop:0 segment deletions, untouched.
    data = json.dumps(presets, ensure_ascii=False, separators=(",", ":")).encode()
    upload_file(host, "presets.json", data)
    result = request(host, "/presets.json")
    if any(result.get(str(i)) != presets[str(i)] for i in range(13, 20)):
        raise RuntimeError("Controller did not retain the uploaded party presets")
    if output is not None:
        Path(output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("Verified six party scenes and Party mix; existing presets preserved.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="WLED URL, including http://")
    parser.add_argument("--output", type=Path, help="Optionally save the resulting presets JSON")
    args = parser.parse_args()
    configure(args.host, args.output)
