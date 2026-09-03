import argparse
import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import torch
import transformers
from torch.utils.data import DataLoader
from transformers import (
    AutoModelForTokenClassification,
    get_linear_schedule_with_warmup,
    set_seed,
)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pollparse.model.dataset import TaggingDataset, collate
from pollparse.model.encoding import (
    DEFAULT_MAX_LENGTH,
    IGNORE_LABEL,
    build_tokenizer,
)
from pollparse.schema import ID2TAG, TAGS, decode_bio

DIST = ROOT / "dist"
REPORT_NAME = "train_report.json"


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()[:16]


def _dataset_facts(train_path: Path) -> dict:
    stats_path = DIST / "stats.json"
    facts: dict = {"source": str(stats_path.relative_to(ROOT))}
    facts["train_file"] = str(train_path)
    if train_path.exists():
        facts["train_sha256"] = _digest(train_path)
        facts["dataset_built_at"] = (
            datetime.fromtimestamp(stats_path.stat().st_mtime, timezone.utc).isoformat()
            if stats_path.exists()
            else None
        )
    if not stats_path.exists():
        return facts
    stats = json.loads(stats_path.read_text(encoding="utf-8"))
    facts["vocab_train"] = stats.get("vocab_train")
    facts["vocab_heldout"] = stats.get("vocab_heldout")
    for split in stats.get("splits", []):
        facts[split["name"]] = {
            "n": split.get("n"),
            "labels": split.get("labels"),
            "avg_options": split.get("avg_options"),
            "len_p95": split.get("len_p95"),
        }
        if split["name"] == "train":
            facts[split["name"]]["hard_flags"] = split.get("hard_flags")
    return facts


def _pick_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    return "cuda" if torch.cuda.is_available() else "cpu"


@torch.no_grad()
def span_f1(model, loader, device) -> dict:
    model.eval()
    hits = 0
    predicted_total = 0
    gold_total = 0

    for batch in loader:
        batch = {key: value.to(device) for key, value in batch.items()}
        predictions = model(
            input_ids=batch["input_ids"], attention_mask=batch["attention_mask"]
        ).logits.argmax(-1)

        for predicted_row, gold_row in zip(predictions, batch["labels"]):
            keep = gold_row != IGNORE_LABEL
            gold_tags = [ID2TAG[i] for i in gold_row[keep].tolist()]
            predicted_tags = [ID2TAG[i] for i in predicted_row[keep].tolist()]

            gold_spans = set(decode_bio(gold_tags))
            predicted_spans = set(decode_bio(predicted_tags))

            hits += len(gold_spans & predicted_spans)
            gold_total += len(gold_spans)
            predicted_total += len(predicted_spans)

    precision = hits / predicted_total if predicted_total else 0.0
    recall = hits / gold_total if gold_total else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="ckiplab/albert-tiny-chinese")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=5e-5)
    parser.add_argument("--out", default=None)
    parser.add_argument(
        "--train",
        default=str(DIST / "train.jsonl"),
        help="Labelled training corpus (JSONL).",
    )
    parser.add_argument(
        "--dev",
        default=str(DIST / "dev.jsonl"),
        help=("Held-out corpus scored after every epoch. Required."),
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=DEFAULT_MAX_LENGTH,
        help="Max token length. Same length should be used during inference.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260827,
    )
    parser.add_argument(
        "--device",
        default=None,
        choices=["cpu", "mps", "cuda"],
        help="Auto detect if not specified.",
    )
    args = parser.parse_args()

    if args.out:
        out_dir = Path(args.out)
    else:
        model_slug = args.model.replace("/", "-")
        out_dir = DIST / (
            f"tagger-{model_slug}-e{args.epochs}-b{args.batch_size}"
            f"-lr{args.lr:g}-len{args.max_length}-s{args.seed}"
        )
    if out_dir.exists():
        sys.exit(f"{out_dir} already exists — remove it or pass --out")

    for flag, path in (("--train", args.train), ("--dev", args.dev)):
        if not Path(path).is_file():
            sys.exit(f"{path} not found (pass {flag} to point elsewhere).\n")

    out_dir.mkdir(parents=True)
    print(f"will save to {out_dir}")

    set_seed(args.seed)
    device = args.device or _pick_device()
    tokenizer = build_tokenizer(args.model)
    model = AutoModelForTokenClassification.from_pretrained(
        args.model,
        num_labels=len(TAGS),
        id2label=ID2TAG,
        label2id={tag: index for index, tag in ID2TAG.items()},
    )
    model.resize_token_embeddings(len(tokenizer))
    model.to(device)

    pad_token_id = tokenizer.pad_token_id
    assert isinstance(pad_token_id, int), "tokenizer doesn't have pad token"

    def loader_for(path: str, shuffle: bool) -> DataLoader:
        return DataLoader(
            TaggingDataset(Path(path), tokenizer, args.max_length),
            batch_size=args.batch_size,
            shuffle=shuffle,
            collate_fn=lambda batch: collate(batch, pad_token_id),
        )

    train_loader = loader_for(args.train, shuffle=True)
    dev_loader = loader_for(args.dev, shuffle=False)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    total_steps = len(train_loader) * args.epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer, int(total_steps * 0.1), total_steps
    )

    print(
        f"device={device}  params={sum(p.numel() for p in model.parameters()) / 1e6:.1f}M"
        f"  steps={total_steps}"
    )

    epoch_reports = []
    training_started = time.time()
    for epoch in range(1, args.epochs + 1):
        model.train()
        running_loss, started = 0.0, time.time()
        for step, batch in enumerate(train_loader, start=1):
            batch = {key: value.to(device) for key, value in batch.items()}
            loss = model(**batch).loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad()
            running_loss += loss.item()
            if step % 100 == 0:
                print(
                    f"  epoch {epoch} step {step}/{len(train_loader)} "
                    f"loss={running_loss / step:.4f}",
                    flush=True,
                )
        scores = span_f1(model, dev_loader, device)
        epoch_reports.append(
            {
                "epoch": epoch,
                "train_loss": round(running_loss / len(train_loader), 4),
                "dev_oov_precision": round(scores["precision"], 4),
                "dev_oov_recall": round(scores["recall"], 4),
                "dev_oov_span_f1": round(scores["f1"], 4),
                "seconds": round(time.time() - started, 1),
            }
        )
        print(
            f"epoch {epoch}  loss={running_loss / len(train_loader):.4f}  "
            f"dev_oov span P/R/F1={scores['precision']:.3f}/{scores['recall']:.3f}/{scores['f1']:.3f}"
            f"  ({time.time() - started:.0f}s)"
        )

    model.save_pretrained(out_dir)
    tokenizer.save_pretrained(out_dir)

    report = {
        "version": out_dir.name,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "training_seconds": round(time.time() - training_started, 1),
        "config": {
            "base_model": args.model,
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "lr": args.lr,
            "max_length": args.max_length,
            "seed": args.seed,
            "device": device,
            "warmup_ratio": 0.1,
            "optimizer": "AdamW",
            "grad_clip": 1.0,
            "torch_version": torch.__version__,
            "transformers_version": transformers.__version__,
            "python_version": platform.python_version(),
        },
        "model_info": {
            "kind": "token-classification",
            "scheme": "char-level BIO",
            "num_labels": len(TAGS),
            "labels": list(TAGS),
            "params": sum(p.numel() for p in model.parameters()),
        },
        "data": _dataset_facts(Path(args.train)),
        "metrics": {
            "dev_span_f1": epoch_reports[-1]["dev_span_f1"] if epoch_reports else None,
            "per_epoch": epoch_reports,
        },
    }
    (out_dir / REPORT_NAME).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Model saved to {out_dir}")
    print(f"Report written to {out_dir / REPORT_NAME}")


if __name__ == "__main__":
    main()
