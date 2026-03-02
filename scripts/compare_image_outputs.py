#!/usr/bin/env python3
from __future__ import annotations

import argparse
import struct
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare dimensions and file sizes of two image files."
    )
    parser.add_argument("--original", required=True, help="Path to the original image.")
    parser.add_argument("--candidate", required=True, help="Path to the comparison image.")
    return parser.parse_args()


def read_image_shape(path: Path) -> tuple[int, int]:
    with path.open("rb") as f:
        header = f.read(24)
    png_sig = b"\x89PNG\r\n\x1a\n"
    if len(header) < 24 or header[:8] != png_sig:
        raise RuntimeError(f"Unsupported or unreadable PNG image: {path}")
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def fmt_kib(num_bytes: int) -> str:
    return f"{num_bytes / 1024:.1f} KiB"


def main() -> int:
    args = parse_args()
    original = Path(args.original).resolve()
    candidate = Path(args.candidate).resolve()

    if not original.exists():
        raise FileNotFoundError(original)
    if not candidate.exists():
        raise FileNotFoundError(candidate)

    orig_w, orig_h = read_image_shape(original)
    cand_w, cand_h = read_image_shape(candidate)
    orig_bytes = original.stat().st_size
    cand_bytes = candidate.stat().st_size

    width_ratio = cand_w / orig_w if orig_w else 0.0
    height_ratio = cand_h / orig_h if orig_h else 0.0
    size_ratio = cand_bytes / orig_bytes if orig_bytes else 0.0

    print(f"original_path: {original}")
    print(f"candidate_path: {candidate}")
    print(f"original_dimensions: {orig_w} x {orig_h}")
    print(f"candidate_dimensions: {cand_w} x {cand_h}")
    print(f"dimension_ratio: {width_ratio:.2f}x width, {height_ratio:.2f}x height")
    print(f"original_size: {orig_bytes} bytes ({fmt_kib(orig_bytes)})")
    print(f"candidate_size: {cand_bytes} bytes ({fmt_kib(cand_bytes)})")
    print(f"file_size_ratio: {size_ratio:.2f}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
