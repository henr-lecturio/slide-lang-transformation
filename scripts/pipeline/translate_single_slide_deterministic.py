#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic slide translation for a single Image Lab image.")
    parser.add_argument("--input-dir", required=True, help="Directory containing exactly one slide image.")
    parser.add_argument("--event-id", required=True, type=int, help="Event id of the selected image.")
    parser.add_argument("--target-language", required=True, help="Target language label.")
    parser.add_argument("--output-dir", required=True, help="Output directory for the translated image.")
    parser.add_argument("--artifacts-dir", required=True, help="Directory for glossary and apply artifacts.")
    parser.add_argument("--termbase-file", required=True, help="Global termbase CSV path.")
    parser.add_argument("--vision-project-id", required=True, help="Google Cloud Vision project id.")
    parser.add_argument("--vision-feature", default="DOCUMENT_TEXT_DETECTION", help="Google Vision OCR feature.")
    parser.add_argument("--translate-project-id", required=True, help="Google Cloud Translation project id.")
    parser.add_argument("--translate-location", default="us-central1", help="Google Cloud Translation location.")
    parser.add_argument("--translate-model", default="general/translation-llm", help="Google Cloud Translation model.")
    parser.add_argument("--source-language-code", default="", help="Optional source language code.")
    parser.add_argument("--font-path", required=True, help="Font file used for deterministic rendering.")
    parser.add_argument("--style-config-json", required=True, help="Role/slot style config JSON.")
    parser.add_argument(
        "--needs-review-policy",
        default="mark_only",
        choices=["mark_only", "allow_partial"],
        help="How unresolved fragments should be handled.",
    )
    return parser.parse_args()


def write_single_slide_map(path: Path, *, event_id: int, image_name: str) -> None:
    payload = {
        "events": [
            {
                "slide_index": 1,
                "event_id": int(event_id),
                "bucket_id": f"event_{int(event_id):03d}",
                "slide_start": 0.0,
                "slide_end": 0.0,
                "image_name": image_name,
                "text": "",
            }
        ]
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_checked(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=str(ROOT_DIR), check=True)


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    artifacts_dir = Path(args.artifacts_dir).resolve()
    termbase_file = Path(args.termbase_file).resolve()
    font_path = Path(args.font_path).resolve()
    style_config_json = Path(args.style_config_json).resolve()

    if not input_dir.exists():
        raise FileNotFoundError(input_dir)
    if not termbase_file.exists():
        raise FileNotFoundError(termbase_file)
    if not font_path.exists():
        raise FileNotFoundError(font_path)
    if not style_config_json.exists():
        raise FileNotFoundError(style_config_json)

    slide_images = sorted(p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".png")
    if len(slide_images) != 1:
        raise RuntimeError(f"Expected exactly one PNG in {input_dir}, found {len(slide_images)}.")

    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    slide_map_json = artifacts_dir / "single_slide_map.json"
    write_single_slide_map(slide_map_json, event_id=args.event_id, image_name=slide_images[0].name)

    build_cmd = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "pipeline" / "build_slide_translate_glossary.py"),
        "--input-dir",
        str(input_dir),
        "--slide-map-json",
        str(slide_map_json),
        "--out-dir",
        str(artifacts_dir),
        "--target-language",
        str(args.target_language),
        "--termbase-file",
        str(termbase_file),
        "--vision-project-id",
        str(args.vision_project_id),
        "--vision-feature",
        str(args.vision_feature),
        "--translate-project-id",
        str(args.translate_project_id),
        "--translate-location",
        str(args.translate_location),
        "--translate-model",
        str(args.translate_model),
    ]
    if str(args.source_language_code or "").strip():
        build_cmd.extend(["--source-language-code", str(args.source_language_code).strip()])
    run_checked(build_cmd)

    apply_cmd = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "pipeline" / "apply_slide_translate_glossary.py"),
        "--input-dir",
        str(input_dir),
        "--slide-map-json",
        str(slide_map_json),
        "--glossary-json",
        str(artifacts_dir / "glossary.json"),
        "--output-dir",
        str(output_dir),
        "--manifest-json",
        str(artifacts_dir / "apply_manifest.json"),
        "--manifest-csv",
        str(artifacts_dir / "apply_manifest.csv"),
        "--needs-review-json",
        str(artifacts_dir / "needs_review.json"),
        "--font-path",
        str(font_path),
        "--style-config-json",
        str(style_config_json),
        "--vision-project-id",
        str(args.vision_project_id),
        "--vision-feature",
        str(args.vision_feature),
        "--style-manifest-json",
        str(artifacts_dir / "style_manifest.json"),
        "--needs-review-policy",
        str(args.needs_review_policy),
        "--debug-dir",
        str(artifacts_dir / "debug"),
    ]
    run_checked(apply_cmd)

    print(f"[LabTranslate] Deterministic single-slide translation finished for event {args.event_id}")
    print(f"[LabTranslate] Artifacts dir: {artifacts_dir}")
    print(f"[LabTranslate] Output dir: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
