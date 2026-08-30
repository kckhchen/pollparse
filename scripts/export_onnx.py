import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForTokenClassification

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pollparse.model.encoding import build_tokenizer

ONNX_NAME = "model.onnx"
QUANTIZED_NAME = "model.int8.onnx"
REPORT_NAME = "train_report.json"


def _record_export(model_dir: Path, entry: dict) -> None:
    import onnxruntime as ort

    report_path = model_dir / REPORT_NAME
    if not report_path.exists():
        print(f"  ! {REPORT_NAME} not found — skipping export record")
        return
    report = json.loads(report_path.read_text(encoding="utf-8"))
    entry["exported_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entry["onnxruntime_version"] = ort.__version__
    report["onnx"] = entry
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _size_mb(path: Path) -> float:
    total = path.stat().st_size
    external = path.with_suffix(path.suffix + ".data")
    if external.exists():
        total += external.stat().st_size
    return total / 1e6


def export(model_dir: Path) -> Path:
    model = AutoModelForTokenClassification.from_pretrained(model_dir)
    model.eval()

    tokenizer = build_tokenizer(str(model_dir))
    sample = tokenizer("晚餐吃什麼？披薩 牛肉麵 九點截止", return_tensors="pt")
    dummy = (sample["input_ids"], sample["attention_mask"])

    out_path = model_dir / ONNX_NAME
    torch.onnx.export(
        model,
        dummy,
        str(out_path),
        input_names=["input_ids", "attention_mask"],
        output_names=["logits"],
        dynamic_axes={
            "input_ids": {0: "batch", 1: "sequence"},
            "attention_mask": {0: "batch", 1: "sequence"},
            "logits": {0: "batch", 1: "sequence"},
        },
        opset_version=17,
        do_constant_folding=True,
    )
    return out_path


def _bundle_weights(onnx_path: Path) -> None:
    import onnx

    model = onnx.load(str(onnx_path))  # 這裡會把外部權重讀進記憶體
    onnx.save(model, str(onnx_path), save_as_external_data=False)
    external = onnx_path.with_suffix(onnx_path.suffix + ".data")
    external.unlink(missing_ok=True)


def quantize(onnx_path: Path) -> Path:
    from onnxruntime.quantization import QuantType, quantize_dynamic

    out_path = onnx_path.parent / QUANTIZED_NAME
    quantize_dynamic(
        model_input=str(onnx_path),
        model_output=str(out_path),
        weight_type=QuantType.QInt8,
    )
    return out_path


def verify(model_dir: Path, onnx_path: Path, tolerance: float) -> dict:
    import onnxruntime as ort

    torch_model = AutoModelForTokenClassification.from_pretrained(model_dir).eval()
    tokenizer = build_tokenizer(str(model_dir))
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])

    texts = [
        "晚餐吃什麼？披薩 牛肉麵 水餃 九點截止可複選匿名",
        "幾點開會？八點 九點 十點 十點截止",
        "看哪部？Top Gun、Iron Man 限時30分鐘",
        "投票方式？匿名 記名 單選",
        "要不要辦？要 不要",
    ]
    worst_diff, label_mismatch = 0.0, 0
    for text in texts:
        encoded = tokenizer(text, return_tensors="pt")
        with torch.no_grad():
            torch_logits: np.ndarray = torch_model(**encoded).logits.numpy()
        onnx_logits = np.asarray(
            session.run(
                None,
                {
                    "input_ids": encoded["input_ids"].numpy(),
                    "attention_mask": encoded["attention_mask"].numpy(),
                },
            )[0]
        )
        worst_diff = max(worst_diff, float(np.abs(torch_logits - onnx_logits).max()))
        label_mismatch += int((torch_logits.argmax(-1) != onnx_logits.argmax(-1)).sum())
    return {
        "max_abs_diff": worst_diff,
        "label_mismatch": label_mismatch,
        "within_tolerance": worst_diff < tolerance,
    }


def benchmark(model_dir: Path, onnx_path: Path) -> None:
    import onnxruntime as ort

    tokenizer = build_tokenizer(str(model_dir))
    encoded = tokenizer(
        "晚餐吃什麼？披薩 牛肉麵 水餃 九點截止可複選", return_tensors="pt"
    )
    torch_model = AutoModelForTokenClassification.from_pretrained(model_dir).eval()
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    onnx_inputs = {
        "input_ids": encoded["input_ids"].numpy(),
        "attention_mask": encoded["attention_mask"].numpy(),
    }

    def timed(run, label: str) -> None:
        for _ in range(20):
            run()
        samples = []
        for _ in range(200):
            started = time.perf_counter()
            run()
            samples.append((time.perf_counter() - started) * 1000)
        samples.sort()
        print(f"    {label:<10} p50={samples[100]:>6.2f}ms  p95={samples[190]:>6.2f}ms")

    with torch.no_grad():
        timed(lambda: torch_model(**encoded), "PyTorch")
    timed(lambda: session.run(None, onnx_inputs), "ONNX")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model_dir")
    parser.add_argument("--quantize", action="store_true", help="Generate int8 version")
    parser.add_argument("--tolerance", type=float, default=1e-4)
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    if not model_dir.exists():
        sys.exit(f"{model_dir} not found")

    print(f"Exporting {model_dir}")
    onnx_path = export(model_dir)
    _bundle_weights(onnx_path)
    print(f"  {ONNX_NAME}  {_size_mb(onnx_path):.1f} MB")

    result = verify(model_dir, onnx_path, args.tolerance)
    status = "✓" if result["within_tolerance"] else "✗"
    print(
        f"  {status} Max diff from PyTorch {result['max_abs_diff']:.2e}"
        f", descrepencies: {result['label_mismatch']}"
    )
    if not result["within_tolerance"]:
        sys.exit("Tolerance exceeded")

    _record_export(
        model_dir,
        {
            "file": ONNX_NAME,
            "size_mb": round(_size_mb(onnx_path), 1),
            "opset": 17,
            "max_abs_diff": result["max_abs_diff"],
            "label_mismatch": result["label_mismatch"],
        },
    )

    if args.quantize:
        quantized = quantize(onnx_path)
        print(f"  {QUANTIZED_NAME}  {_size_mb(quantized):.1f} MB")
        quantized_result = verify(model_dir, quantized, tolerance=float("inf"))
        print(
            f"    Max diff after quantization {quantized_result['max_abs_diff']:.2e}"
            f", discrepencies {quantized_result['label_mismatch']}"
        )

    print("\n  Speed:（CPU, batch=1）")
    benchmark(model_dir, onnx_path)


if __name__ == "__main__":
    main()
