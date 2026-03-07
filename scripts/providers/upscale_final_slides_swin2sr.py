#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import cv2
import numpy as np
import torch


DEFAULT_MODEL_ID = "caidas/swin2SR-classical-sr-x4-64"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upscale final slide ROI images locally with Swin2SR."
    )
    parser.add_argument("--input-dir", required=True, help="Directory with input slide PNG files.")
    parser.add_argument("--output-dir", required=True, help="Directory for upscaled slide PNG files.")
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID, help="Hugging Face model id.")
    parser.add_argument(
        "--device",
        default="auto",
        choices=("auto", "cuda", "cpu"),
        help="Inference device. auto prefers CUDA when available.",
    )
    parser.add_argument(
        "--tile-size",
        type=int,
        default=256,
        help="Core tile size in input pixels. Use 0 to process the whole image at once.",
    )
    parser.add_argument(
        "--tile-overlap",
        type=int,
        default=24,
        help="Extra context pixels around each tile core.",
    )
    parser.add_argument("--out-manifest-json", default="", help="Output JSON manifest path for per-slide status.")
    parser.add_argument("--resume", action="store_true", default=False, help="Resume: skip slides already upscaled in a previous run.")
    return parser.parse_args()


def ensure_model():
    try:
        from transformers import AutoImageProcessor, Swin2SRForImageSuperResolution
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "transformers with Swin2SR support is not installed. "
            "Run: source .venv/bin/activate && pip install transformers safetensors"
        ) from exc
    return AutoImageProcessor, Swin2SRForImageSuperResolution


def clear_pngs(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for p in path.glob("*.png"):
        p.unlink()


def resolve_device(requested: str) -> torch.device:
    if requested == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if requested == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("--device cuda requested, but torch.cuda.is_available() is False.")
        return torch.device("cuda")
    return torch.device("cpu")


def load_model(model_id: str, device: torch.device):
    AutoImageProcessor, Swin2SRForImageSuperResolution = ensure_model()
    processor = AutoImageProcessor.from_pretrained(model_id)
    model = Swin2SRForImageSuperResolution.from_pretrained(model_id)
    model.eval()
    model.to(device)
    return processor, model


def infer_patch(
    image_rgb: np.ndarray,
    processor,
    model,
    device: torch.device,
    scale: int,
) -> np.ndarray:
    orig_h, orig_w = image_rgb.shape[:2]
    inputs = processor(image_rgb, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.inference_mode():
        reconstruction = model(**inputs).reconstruction
    patch = reconstruction.squeeze(0).float().cpu().clamp(0, 1).numpy()
    patch = np.moveaxis(patch, 0, -1)
    patch = (patch * 255.0).round().astype(np.uint8)
    expected_h = orig_h * scale
    expected_w = orig_w * scale
    return patch[:expected_h, :expected_w]


def upscale_tiled(
    image_rgb: np.ndarray,
    processor,
    model,
    device: torch.device,
    scale: int,
    tile_size: int,
    tile_overlap: int,
) -> np.ndarray:
    h, w = image_rgb.shape[:2]
    if tile_size <= 0 or (h <= tile_size and w <= tile_size):
        return infer_patch(image_rgb, processor, model, device, scale)

    out = np.zeros((h * scale, w * scale, 3), dtype=np.uint8)
    for y0 in range(0, h, tile_size):
        y1 = min(y0 + tile_size, h)
        src_y0 = max(0, y0 - tile_overlap)
        src_y1 = min(h, y1 + tile_overlap)
        for x0 in range(0, w, tile_size):
            x1 = min(x0 + tile_size, w)
            src_x0 = max(0, x0 - tile_overlap)
            src_x1 = min(w, x1 + tile_overlap)

            patch_rgb = image_rgb[src_y0:src_y1, src_x0:src_x1]
            patch_up = infer_patch(patch_rgb, processor, model, device, scale)

            crop_y0 = (y0 - src_y0) * scale
            crop_y1 = crop_y0 + (y1 - y0) * scale
            crop_x0 = (x0 - src_x0) * scale
            crop_x1 = crop_x0 + (x1 - x0) * scale

            out[y0 * scale : y1 * scale, x0 * scale : x1 * scale] = patch_up[
                crop_y0:crop_y1,
                crop_x0:crop_x1,
            ]
    return out


def upscale_directory(
    input_dir: Path,
    output_dir: Path,
    processor,
    model,
    device: torch.device,
    scale: int,
    tile_size: int,
    tile_overlap: int,
    existing_status: dict[str, str] | None = None,
    manifest_items: list[dict[str, str]] | None = None,
) -> tuple[int, int]:
    slide_paths = sorted(p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".png")
    processed = 0
    fallback = 0
    if existing_status is None:
        existing_status = {}
    if manifest_items is None:
        manifest_items = []

    for slide_path in slide_paths:
        dst_path = output_dir / slide_path.name
        print(f"@@STEP DETAIL upscale {slide_path.name}")

        # Resume: skip already upscaled slides
        if slide_path.name in existing_status:
            processed += 1
            manifest_items.append({"name": slide_path.name, "status": "upscaled", "reason": "resume"})
            print(f"[Upscale] Reused {slide_path.name} (resume)")
            continue

        image_bgr = cv2.imread(str(slide_path), cv2.IMREAD_COLOR)
        if image_bgr is None or image_bgr.size == 0:
            shutil.copy2(slide_path, dst_path)
            fallback += 1
            manifest_items.append({"name": slide_path.name, "status": "fallback", "reason": "read_failed"})
            print(f"[Upscale] Fallback {slide_path.name}: failed to read image.")
            continue

        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        try:
            upscaled_rgb = upscale_tiled(
                image_rgb,
                processor,
                model,
                device,
                scale,
                tile_size,
                tile_overlap,
            )
        except Exception as exc:  # noqa: BLE001
            shutil.copy2(slide_path, dst_path)
            fallback += 1
            manifest_items.append({"name": slide_path.name, "status": "fallback", "reason": str(exc)})
            print(f"[Upscale] Fallback {slide_path.name}: {exc}")
            continue

        upscaled_bgr = cv2.cvtColor(upscaled_rgb, cv2.COLOR_RGB2BGR)
        if not cv2.imwrite(str(dst_path), upscaled_bgr):
            shutil.copy2(slide_path, dst_path)
            fallback += 1
            manifest_items.append({"name": slide_path.name, "status": "fallback", "reason": "write_failed"})
            print(f"[Upscale] Fallback {slide_path.name}: failed to write image.")
            continue
        processed += 1
        manifest_items.append({"name": slide_path.name, "status": "upscaled"})
        print(f"[Upscale] Upscaled {slide_path.name}")

    return processed, fallback


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    if not input_dir.exists():
        raise FileNotFoundError(input_dir)
    if args.tile_size < 0:
        raise RuntimeError("--tile-size must be >= 0.")
    if args.tile_overlap < 0:
        raise RuntimeError("--tile-overlap must be >= 0.")
    if args.tile_size > 0 and args.tile_overlap >= args.tile_size:
        raise RuntimeError("--tile-overlap must be smaller than --tile-size.")

    device = resolve_device(str(args.device))
    processor, model = load_model(str(args.model_id), device)
    scale = int(getattr(model.config, "upscale", 4) or 4)

    out_manifest_path = Path(args.out_manifest_json).resolve() if args.out_manifest_json else None

    # Resume support: load existing manifest to skip completed slides
    existing_status: dict[str, str] = {}
    if args.resume and out_manifest_path and out_manifest_path.exists():
        try:
            prev = json.loads(out_manifest_path.read_text(encoding="utf-8"))
            for item in prev.get("items", []):
                if item.get("status") == "upscaled" and (output_dir / item["name"]).exists():
                    existing_status[item["name"]] = "upscaled"
            if existing_status:
                print(f"[Upscale] Resume: {len(existing_status)} slides already upscaled, skipping.", flush=True)
        except Exception:
            pass

    if not args.resume:
        clear_pngs(output_dir)

    manifest_items: list[dict[str, str]] = []
    processed, fallback = upscale_directory(
        input_dir,
        output_dir,
        processor,
        model,
        device,
        scale,
        int(args.tile_size),
        int(args.tile_overlap),
        existing_status=existing_status,
        manifest_items=manifest_items,
    )

    if out_manifest_path:
        manifest = {"items": manifest_items, "upscaled_count": processed, "fallback_count": fallback}
        out_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        out_manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[Upscale] Slides processed: {processed + fallback}")
    print(f"[Upscale] Upscaled: {processed}")
    print(f"[Upscale] Fallback: {fallback}")
    print(f"[Upscale] Output dir: {output_dir}")
    print(f"[Upscale] Model: {args.model_id}")
    print(f"[Upscale] Device: {device.type}")
    print(f"[Upscale] Scale: x{scale}")
    print(f"[Upscale] Tile size: {args.tile_size}")
    print(f"[Upscale] Tile overlap: {args.tile_overlap}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
