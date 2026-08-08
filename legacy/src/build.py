"""Inline a session's data.json into the dashboard template -> dashboard.html.

The dashboard is a single self-contained HTML file (no external requests, so it
works as an offline artifact). ``build.py`` takes the template, which contains a
``__DATA__`` placeholder inside a ``<script type="application/json">`` block, and
substitutes the exported session payload.
"""

from __future__ import annotations

import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build(data_path: Path, template_path: Path, out_path: Path) -> None:
    data = data_path.read_text(encoding="utf-8")
    template = template_path.read_text(encoding="utf-8")
    if "__DATA__" not in template:
        raise ValueError(f"{template_path} has no __DATA__ placeholder")
    # guard against the payload prematurely closing the script element
    safe = data.replace("</script", "<\\/script")
    out_path.write_text(template.replace("__DATA__", safe), encoding="utf-8")
    print(f"wrote {out_path} ({out_path.stat().st_size // 1024} KB)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, default=Path("data.json"))
    ap.add_argument("--template", type=Path, default=HERE / "template.html")
    ap.add_argument("--out", type=Path, default=Path("dashboard.html"))
    args = ap.parse_args()
    build(args.data, args.template, args.out)


if __name__ == "__main__":
    main()
