import argparse
import sys
import time
from pathlib import Path

import torch
from torch.utils.data import DataLoader
from transformers import (
    AutoModelForTokenClassification,
    get_linear_schedule_with_warmup,
)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pollparse.model.dataset import TaggingDataset, collate
from pollparse.model.encoding import IGNORE_LABEL, build_tokenizer
from pollparse.schema import ID2TAG, TAGS, decode_bio

DIST = ROOT / "dist"


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
            f"tagger-{model_slug}-e{args.epochs}-b{args.batch_size}-lr{args.lr:g}"
        )
    if out_dir.exists():
        sys.exit(f"{out_dir} already exists — remove it or pass --out")
    out_dir.mkdir(parents=True)
    print(f"will save to {out_dir}")

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

    def loader_for(split: str, shuffle: bool) -> DataLoader:
        return DataLoader(
            TaggingDataset(DIST / f"{split}.jsonl", tokenizer),
            batch_size=args.batch_size,
            shuffle=shuffle,
            collate_fn=lambda batch: collate(batch, pad_token_id),
        )

    train_loader = loader_for("train", shuffle=True)
    dev_loader = loader_for("dev_oov", shuffle=False)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    total_steps = len(train_loader) * args.epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer, int(total_steps * 0.1), total_steps
    )

    print(
        f"device={device}  params={sum(p.numel() for p in model.parameters()) / 1e6:.1f}M"
        f"  steps={total_steps}"
    )

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
        print(
            f"epoch {epoch}  loss={running_loss / len(train_loader):.4f}  "
            f"dev_oov span P/R/F1={scores['precision']:.3f}/{scores['recall']:.3f}/{scores['f1']:.3f}"
            f"  ({time.time() - started:.0f}s)"
        )

    model.save_pretrained(out_dir)
    tokenizer.save_pretrained(out_dir)
    print(f"Model saved to {out_dir}")


if __name__ == "__main__":
    main()
