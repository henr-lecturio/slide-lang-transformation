#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests


ROOT_DIR = Path(__file__).resolve().parents[2]
LOCAL_ENV_PATH = ROOT_DIR / ".env.local"
DEFAULT_NIGHTMARE_REALESRGAN_MODEL_REF = "nightmareai/real-esrgan"
DEFAULT_NIGHTMARE_REALESRGAN_VERSION_ID = "f121d640bd286e1fdc67f9799164c1d5be36ff74576ee11c803ae5b665dd46aa"
DEFAULT_NIGHTMARE_REALESRGAN_SCALE = 4
DEFAULT_NIGHTMARE_REALESRGAN_FACE_ENHANCE = False
# Replicate T4 public rate from pricing docs, used as a cost estimate.
DEFAULT_NIGHTMARE_REALESRGAN_PRICE_PER_SECOND = 0.000225


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upscale final slides with Replicate-hosted non-diffusion SR models."
    )
    parser.add_argument("--input-dir", required=True, help="Directory with input slide PNG files.")
    parser.add_argument("--output-dir", required=True, help="Directory for upscaled slide PNG files.")
    parser.add_argument(
        "--provider",
        required=True,
        choices=("nightmare_realesrgan",),
        help="Replicate model family to run.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=2,
        help="Number of images to process in parallel.",
    )
    parser.add_argument(
        "--manifest-path",
        default="",
        help="Optional JSON manifest path for per-image provider results.",
    )
    parser.add_argument(
        "--nightmare-realesrgan-model-ref",
        default=DEFAULT_NIGHTMARE_REALESRGAN_MODEL_REF,
        help="Replicate model ref for nightmareai/real-esrgan.",
    )
    parser.add_argument(
        "--nightmare-realesrgan-version-id",
        default=DEFAULT_NIGHTMARE_REALESRGAN_VERSION_ID,
        help="Replicate model version id for nightmareai/real-esrgan.",
    )
    parser.add_argument(
        "--nightmare-realesrgan-scale",
        type=int,
        default=DEFAULT_NIGHTMARE_REALESRGAN_SCALE,
        help="Replicate nightmareai/real-esrgan scale value.",
    )
    parser.add_argument(
        "--nightmare-realesrgan-face-enhance",
        default="false",
        help="Replicate nightmareai/real-esrgan face_enhance value (true/false).",
    )
    parser.add_argument(
        "--nightmare-realesrgan-price-per-second",
        type=float,
        default=DEFAULT_NIGHTMARE_REALESRGAN_PRICE_PER_SECOND,
        help="Estimated USD per second for Replicate nightmareai/real-esrgan prediction time.",
    )
    return parser.parse_args()


def load_local_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def ensure_client():
    try:
        import replicate
    except ImportError as exc:  # pragma: no cover - depends on env
        raise RuntimeError(
            "replicate is not installed in this environment. "
            "Run: source .venv/bin/activate && pip install replicate"
        ) from exc

    api_token = (os.environ.get("REPLICATE_API_TOKEN") or "").strip()
    if not api_token:
        raise RuntimeError("REPLICATE_API_TOKEN is not set in the environment.")
    return replicate.Client(api_token=api_token)


def clear_pngs(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for p in path.glob("*.png"):
        p.unlink()


def download_output_bytes(output) -> bytes:
    if output is None:
        raise RuntimeError("Replicate did not return an output.")
    if isinstance(output, (list, tuple)):
        if not output:
            raise RuntimeError("Replicate returned an empty output list.")
        return download_output_bytes(output[0])
    if isinstance(output, dict):
        for value in output.values():
            try:
                return download_output_bytes(value)
            except Exception:
                continue
        raise RuntimeError("Replicate returned an unsupported output object.")
    if hasattr(output, "read") and callable(output.read):
        data = output.read()
        if isinstance(data, bytes):
            return data
        if isinstance(data, str):
            response = requests.get(data, timeout=300)
            response.raise_for_status()
            return response.content
    maybe_url = getattr(output, "url", None)
    if isinstance(maybe_url, str) and maybe_url:
        response = requests.get(maybe_url, timeout=300)
        response.raise_for_status()
        return response.content
    if isinstance(output, str):
        response = requests.get(output, timeout=300)
        response.raise_for_status()
        return response.content
    raise RuntimeError(f"Unsupported Replicate output type: {type(output)!r}")


def _prediction_urls_web(prediction) -> str:
    urls = getattr(prediction, "urls", None)
    if isinstance(urls, dict):
        return str(urls.get("web", "") or "")
    web = getattr(urls, "web", None)
    return str(web or "")


def str_to_bool(text: str | bool) -> bool:
    if isinstance(text, bool):
        return text
    value = str(text).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {text}")


def run_provider(client, args: argparse.Namespace, slide_path: Path) -> tuple[object, dict]:
    with slide_path.open("rb") as f:
        if args.provider == "nightmare_realesrgan":
            version = str(args.nightmare_realesrgan_version_id).strip()
            model_ref = str(args.nightmare_realesrgan_model_ref).strip()
            input_payload = {
                "image": f,
                "scale": int(args.nightmare_realesrgan_scale),
                "face_enhance": str_to_bool(args.nightmare_realesrgan_face_enhance),
            }
            price_per_second = max(float(args.nightmare_realesrgan_price_per_second), 0.0)
        else:  # pragma: no cover - guarded by argparse choices
            raise RuntimeError(f"Unsupported provider: {args.provider}")

        prediction = client.predictions.create(
            version=version,
            input=input_payload,
        )
    prediction.wait()
    prediction.reload()
    if str(getattr(prediction, "status", "")) != "succeeded":
        error = getattr(prediction, "error", None) or f"Replicate prediction failed with status={prediction.status}"
        raise RuntimeError(str(error))
    metrics = getattr(prediction, "metrics", None) or {}
    predict_time_sec = 0.0
    if isinstance(metrics, dict):
        try:
            predict_time_sec = float(metrics.get("predict_time", 0.0) or 0.0)
        except Exception:
            predict_time_sec = 0.0
    estimated_cost_usd = round(max(predict_time_sec, 0.0) * price_per_second, 6)
    meta = {
        "model_ref": model_ref,
        "prediction_id": str(getattr(prediction, "id", "") or ""),
        "prediction_status": str(getattr(prediction, "status", "") or ""),
        "predict_time_sec": round(predict_time_sec, 3),
        "estimated_cost_usd": estimated_cost_usd,
        "web_url": _prediction_urls_web(prediction),
    }
    return prediction.output, meta


def process_one(slide_path: Path, output_dir: Path, args: argparse.Namespace, log_lock: threading.Lock) -> dict:
    dst_path = output_dir / slide_path.name
    started = time.time()
    with log_lock:
        print(f"@@STEP DETAIL upscale {args.provider}:{slide_path.name}", flush=True)
    try:
        client = ensure_client()
        output, provider_meta = run_provider(client, args, slide_path)
        data = download_output_bytes(output)
        dst_path.write_bytes(data)
        runtime_sec = time.time() - started
        with log_lock:
            print(
                f"[Upscale] Upscaled {slide_path.name} via {args.provider} in {runtime_sec:.2f}s"
                f" | predict={provider_meta['predict_time_sec']:.3f}s | est_cost=${provider_meta['estimated_cost_usd']:.6f}",
                flush=True,
            )
        return {
            "name": slide_path.name,
            "provider": args.provider,
            "status": "upscaled",
            "runtime_sec": round(runtime_sec, 3),
            "output": dst_path.name,
            **provider_meta,
        }
    except Exception as exc:  # noqa: BLE001
        shutil.copy2(slide_path, dst_path)
        runtime_sec = time.time() - started
        with log_lock:
            print(f"[Upscale] Fallback {slide_path.name} via {args.provider}: {exc}", flush=True)
        return {
            "name": slide_path.name,
            "provider": args.provider,
            "status": "fallback",
            "runtime_sec": round(runtime_sec, 3),
            "error": str(exc),
            "output": dst_path.name,
            "prediction_id": "",
            "predict_time_sec": 0.0,
            "estimated_cost_usd": 0.0,
            "web_url": "",
            "model_ref": str(args.nightmare_realesrgan_model_ref).strip(),
        }


def summarize_results(items: list[dict]) -> dict:
    total_runtime = round(sum(float(item.get("runtime_sec", 0.0) or 0.0) for item in items), 3)
    total_predict = round(sum(float(item.get("predict_time_sec", 0.0) or 0.0) for item in items), 3)
    total_cost = round(sum(float(item.get("estimated_cost_usd", 0.0) or 0.0) for item in items), 6)
    upscaled = sum(1 for item in items if item.get("status") == "upscaled")
    fallback = len(items) - upscaled
    return {
        "items_processed": len(items),
        "upscaled": upscaled,
        "fallback": fallback,
        "total_runtime_sec": total_runtime,
        "total_predict_time_sec": total_predict,
        "total_estimated_cost_usd": total_cost,
    }


def write_manifest(path: Path, items: list[dict], provider: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "provider": provider,
        "generated_at": int(time.time()),
        "summary": summarize_results(items),
        "items": items,
    }
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    load_local_env(LOCAL_ENV_PATH)

    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    if not input_dir.exists():
        raise FileNotFoundError(input_dir)
    if args.concurrency < 1:
        raise RuntimeError("--concurrency must be >= 1.")

    slide_paths = sorted(p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".png")
    clear_pngs(output_dir)

    log_lock = threading.Lock()
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=int(args.concurrency)) as executor:
        futures = {
            executor.submit(process_one, slide_path, output_dir, args, log_lock): slide_path
            for slide_path in slide_paths
        }
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda item: item["name"])
    summary = summarize_results(results)
    if args.manifest_path:
        write_manifest(Path(args.manifest_path).resolve(), results, args.provider)

    print(f"[Upscale] Slides processed: {len(results)}")
    print(f"[Upscale] Upscaled: {summary['upscaled']}")
    print(f"[Upscale] Fallback: {summary['fallback']}")
    print(f"[Upscale] Output dir: {output_dir}")
    print(f"[Upscale] Provider: {args.provider}")
    print(f"[Upscale] Concurrency: {args.concurrency}")
    print(f"[Upscale] Model ref: {args.nightmare_realesrgan_model_ref}")
    print(f"[Upscale] Version id: {args.nightmare_realesrgan_version_id}")
    print(f"[Upscale] Scale: x{args.nightmare_realesrgan_scale}")
    print(f"[Upscale] Face enhance: {str_to_bool(args.nightmare_realesrgan_face_enhance)}")
    print(f"[Upscale] Total predict time: {summary['total_predict_time_sec']:.3f}s")
    print(f"[Upscale] Estimated total cost (USD): {summary['total_estimated_cost_usd']:.6f}")
    if args.manifest_path:
        print(f"[Upscale] Manifest: {Path(args.manifest_path).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
