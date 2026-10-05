"""Compare shared painting against explicit real LIBERO marked RGB images."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import random

from PIL import Image, ImageDraw, __version__ as pillow_version
import v6_pixel_marks


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sha(args.manifest) != args.expected_sha256:
        raise ValueError("registered real-image manifest changed")
    files = json.loads(args.manifest.read_text())["image_files"]
    sample = random.Random(450).sample(files, 50)
    rows = []
    for record in sample:
        raw, marked = Path(record["original_image"]), Path(record["path"])
        if sha(raw) != record["image_sha256"] or sha(marked) != record["sha256"]:
            raise ValueError("registered real RGB changed")
        image = Image.open(raw).convert("RGB")
        draw = ImageDraw.Draw(image)
        for mark in record["marks"]:
            if str(mark["src"]).startswith("sim"):
                raise ValueError("simulator-truth mark in LIBERO input")
            v6_pixel_marks.draw_pixel_mark(draw, mark["box_xyxy"], mark["id"])
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        rendered = buffer.getvalue()
        rows.append({"source": record, "shared_png_sha256": hashlib.sha256(rendered).hexdigest(),
                     "byte_identical": rendered == marked.read_bytes()})
    report = {"purpose": "shared pixel function adoption on real saved RGB, not physics replay or behavior freeze",
              "manifest": {"path": str(args.manifest), "sha256": sha(args.manifest)},
              "shared_pixel_source": {"path": v6_pixel_marks.__file__, "sha256": sha(Path(v6_pixel_marks.__file__))},
              "pillow_version": pillow_version, "images": len(rows),
              "byte_identical_images": sum(row["byte_identical"] for row in rows),
              "passed": all(row["byte_identical"] for row in rows),
              "rows": rows, "new_physical_states": 0, "new_training_rows": 0}
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"images": len(rows), "byte_identical_images": report["byte_identical_images"],
                      "passed": report["passed"], "pillow": pillow_version,
                      "sha256": sha(args.output / "report.json")}))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
