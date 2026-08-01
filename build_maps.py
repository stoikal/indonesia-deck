#!/usr/bin/env python3
"""Generate per-province highlighted SVG maps of Indonesia.

Source : indonesiaLow.json  (GeoJSON, 38 provinces, WGS84 lon/lat)
Output : Indonesia__Provinces/media/<slug>.svg  (38 files)

Projection: Plate Carree, viewBox 954.058622 x 345.6 (matches the
matplotlib original). Highlight colour is a softer red; non-target
provinces stay white; ocean stays the same dark navy as the original.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
SRC = REPO / "indonesiaLow.json"
DECK_DIR = REPO / "Indonesia__Provinces"
MEDIA_DIR = DECK_DIR / "media"
DECK_JSON = DECK_DIR / "deck.json"

# Plate Carree projection, viewBox matches indonesiaLow.svg
LON_MIN, LON_MAX = 95.1957, 141.0195
LAT_MIN, LAT_MAX = -10.9452, 5.6541
W, H = 954.058622, 345.6
SCALE = W / (LON_MAX - LON_MIN)  # == H / (LAT_MAX - LAT_MIN) == 20.8205

OCEAN = "#212830"
LAND = "#ffffff"
HIGHLIGHT = "#e74c3c"  # softer red, no stroke

# Deck name -> GeoJSON name (only 2 mismatches)
NAME_ALIAS = {
    "DKI Jakarta": "Jakarta Raya",
    "DI Yogyakarta": "Yogyakarta",
}


def project(lon: float, lat: float) -> tuple[float, float]:
    x = (lon - LON_MIN) * SCALE
    y = (LAT_MAX - lat) * SCALE
    return x, y


def polygon_to_d(polygon: list[list[list[float]]]) -> str:
    """Polygon = list of rings (first = exterior, rest = holes)."""
    parts: list[str] = []
    for i, ring in enumerate(polygon):
        cmds: list[str] = []
        for j, (lon, lat) in enumerate(ring):
            x, y = project(lon, lat)
            cmds.append(f"{'M' if j == 0 else 'L'}{x:.2f},{y:.2f}")
        cmds.append("Z")
        ring_d = "".join(cmds)
        parts.append(ring_d if i == 0 else " " + ring_d)
    return "".join(parts)


def feature_to_paths(feature: dict, fill: str) -> list[str]:
    geom = feature["geometry"]
    gtype = geom["type"]
    polygons = [geom["coordinates"]] if gtype == "Polygon" else (
        geom["coordinates"] if gtype == "MultiPolygon" else []
    )
    out: list[str] = []
    for poly in polygons:
        d = polygon_to_d(poly)
        fr = ' fill-rule="evenodd"' if len(poly) > 1 else ""
        out.append(f'  <path d="{d}" style="fill:{fill}"{fr}/>')
    return out


def slugify(name: str) -> str:
    return name.lower().replace(" ", "_").replace("/", "_")


def main() -> int:
    with SRC.open() as f:
        gj = json.load(f)
    with DECK_JSON.open() as f:
        deck = json.load(f)

    feat_by_name = {f["properties"]["name"]: f for f in gj["features"]}

    items: list[tuple[str, str, str, dict]] = []
    for note in deck["notes"]:
        deck_name = note["fields"][0]
        gj_name = NAME_ALIAS.get(deck_name, deck_name)
        feat = feat_by_name.get(gj_name)
        if feat is None:
            print(f"WARN: {deck_name!r} (geojson {gj_name!r}) not found",
                  file=sys.stderr)
            continue
        items.append((deck_name, gj_name, slugify(deck_name), feat))

    if len(items) != 38:
        print(f"ERROR: expected 38 provinces, got {len(items)}", file=sys.stderr)
        return 1

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    svg_open = (
        '<?xml version="1.0" encoding="utf-8" standalone="no"?>\n'
        '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" '
        '"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
        f'width="{W}" height="{H}" viewBox="0 0 {W} {H}">\n'
        f' <rect width="{W}" height="{H}" style="fill:{OCEAN}"/>\n'
    )
    svg_close = "</svg>\n"

    media_files_added: list[str] = []

    for tgt_deck, tgt_gj, tgt_slug, _ in items:
        parts: list[str] = [svg_open]
        for src_deck, src_gj, src_slug, src_feat in items:
            fill = HIGHLIGHT if src_gj == tgt_gj else LAND
            parts.append(
                f' <g id="prov-{src_slug}" data-name="{src_deck}">\n'
            )
            parts.extend(feature_to_paths(src_feat, fill))
            parts.append(" </g>\n")
        parts.append(svg_close)

        out = MEDIA_DIR / f"{tgt_slug}.svg"
        out.write_text("".join(parts))
        media_files_added.append(f"{tgt_slug}.svg")

        note = next(n for n in deck["notes"] if n["fields"][0] == tgt_deck)
        note["fields"][2] = f'<img src="{tgt_slug}.svg">'
        print(f"  {tgt_deck:<32} -> {tgt_slug}.svg")

    existing = set(deck.get("media_files", []))
    for fn in media_files_added:
        existing.add(fn)
    deck["media_files"] = sorted(existing)

    with DECK_JSON.open("w") as f:
        json.dump(deck, f, indent=4, ensure_ascii=False)

    print(f"\nGenerated {len(media_files_added)} SVGs in {MEDIA_DIR}")
    print(f"Updated {DECK_JSON}  (media_files: {len(deck['media_files'])} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
