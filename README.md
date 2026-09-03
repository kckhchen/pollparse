# Pollparse

Turns your sentence into a poll.

Pollparse is a self-contained NLP parser for Traditional Chinese poll text, written for how people in Taiwan actually type. It turns a raw string describing a poll with a mix of title, some options, and whatever settings the writer happened to mention into a well-formed Python dict (`.json` over the wire) that an API service can turn into a real poll. You can see the parser at work on [Sootow 俗投](https://sootow.com), a web app I designed to create a quick poll in seconds.

Pollparse 是一個基於預訓練微調 transformer 設計的 NLP 投票自然語言處理解析工具和訓練框架，針對台灣繁體中文使用者語用習慣，可將原始投票描述字串，如「等等要幹嘛？玩桌遊 打電動 睡覺 半小時後截止複選」解析為兼容於 `.json` 的 python `dict`，可以串接 API 建立投票。目前營運中的投票網頁服務 [Sootow 俗投](https://sootow.com)便是基於此架構設計。

The repository is a training framework in three parts: a markup toolchain that turns hand-labelled text into a validated training corpus, a transformer fine-tuning and ONNX-export pipeline that produces a model for span boundary and label prediction, and a rule layer that turns the labelled time and setting spans into values via simple lexicon lookup and regex-driven grammar rules.

Example input:

```text
晚餐吃什麼？滷肉飯 牛肉麵 水餃 明天中午截止可複選匿名
```

The output:

```json
{
  "title": "晚餐吃什麼",
  "options": ["滷肉飯", "牛肉麵", "水餃"],
  "settings": {
    "deadline": {
      "kind": "absolute",
      "day_offset": 1,
      "hour": null,
      "part": "中午",
      ...
    },
    "multichoice": true,
    "anonymous": true,
    "max_choices": null,
    "host_can_vote": null,
    "live_results": null,
    "allow_other": null
  }
}
```

## Step-By-Step Guide

### 0. Install the dependencies

Python 3.10 or newer.

```bash
pip install torch transformers onnx onnxruntime pytest
```

### 1. Label your own data

You will need two datasets: a training dataset and a dev dataset. The dev dataset should ideally only contain words that have never appeared in the training set (oov) in order to test the generalizability of the model.

Write one poll per line, wrapping each span in its tag. Everything outside a tag is `O` (not any part of a poll), `\n` means a newline, and `#` starts a comment.

```text
<t>晚餐吃什麼</t>？<o>披薩</o> <o>牛肉麵</o> <time>九點截止</time><multi>可複選</multi>
<t>要不要辦</t>？<o>要</o> <o>不要</o>（<anon>匿名</anon>）
```

Available tags:

| Tag        | Marks                                    | Examples                             |
| ---------- | ---------------------------------------- | ------------------------------------ |
| `<t>`      | the question                             | `晚餐吃什麼`, `要不要延期`           |
| `<o>`      | one option, one tag each                 | `披薩`, `不要`, `都可以`             |
| `<time>`   | when voting closes                       | `九點截止`, `明天中午前`, `30分鐘後` |
| `<multi>`  | single or multiple choice, and any cap   | `可複選`, `單選`, `最多選三個`       |
| `<anon>`   | whether voters are named                 | `匿名`, `記名`                       |
| `<host>`   | whether the host votes too               | `房主不投`, `我也投`                 |
| `<live>`   | tallies live, or only once voting closes | `即時開票`, `投完才公布`             |
| `<addopt>` | whether voters may add options           | `可以新增`, `不能新增`               |

Only wrap the words themselves. The `？` and the brackets in the example above stay outside.

The lines will later be converted to BIO tags by the script so you don't have to. If you do not have data at hand but wish to test the framework, `examples/train.txt` and `examples/dev.txt` provide a tiny dataset for each for demonstration purposes.

### 2. Build the corpus

```bash
python scripts/build_from_markup.py -i examples/train.txt -o dist/train.jsonl
python scripts/build_from_markup.py -i examples/dev.txt   -o dist/dev.jsonl
# or use your own labelled datasets
```

This will output 2 validated `.jsonl` files ready for training. If the validation fails, the entire process aborts to make sure no malformed data enters the training loop.

To take a peek at the formatted data, use the `peek.py` script. It prints beautifully-colored rows for your inspection.

```bash
python scripts/peek.py dist/train.jsonl -n 5
```

### 3. Train your model

```bash
python scripts/train_model.py --seed 1
```

`train_model.py` writes the checkpoint plus a `train_report.json` recording the training time, the training corpus hash, and the per-epoch scores (both training loss and dev loss). The default directory for the model and reports will be under `dist/tagger-<model>-e<epochs>-b<batch-size>-lr<learning-rate>-len<max-length>-s<seed>/`.

All available CLI flags are listed below:

| Flag           | Default                       | What it does                                                          |
| -------------- | ----------------------------- | --------------------------------------------------------------------- |
| `--train`      | `dist/train.jsonl`            | Labelled training corpus.                                             |
| `--dev`        | `dist/dev.jsonl`              | Held-out corpus, scored after every epoch. Required.                  |
| `--model`      | `ckiplab/albert-tiny-chinese` | The pretrained encoder to fine-tune.                                  |
| `--epochs`     | `3`                           |                                                                       |
| `--batch-size` | `64`                          |                                                                       |
| `--lr`         | `5e-5`                        | Learning rate with a linear schedule and 10% warmup.                  |
| `--max-length` | `128`                         | Maximum tokens per example. Must use the same value during inference. |
| `--seed`       | `20260827`                    |                                                                       |
| `--out`        | derived from the flags        | Output path for the model directory.                                  |
| `--device`     | auto                          | `cpu`, `mps` or `cuda`. Detected if not given.                        |

### 4. Evaluation

```bash
python scripts/eval_parser.py --model dist/<checkpoint>
```

All available flags are listed below:

| Flag           | Default | What it does                                                           |
| -------------- | ------- | ---------------------------------------------------------------------- |
| `--model`      | —       | Directory for the tagger.                                              |
| `--baseline`   | —       | Evaluate the rule parser instead.                                      |
| `--splits`     | `dev`   | Which files under `dist/` to score, by stem. Missing ones are skipped. |
| `--slice`      | off     | Also break the exact-match rate down by difficulty flag (see below).   |
| `--max-length` | `128`   | Must match the value the model was trained with.                       |

This script will print, for each split: per-label precision, recall and F1 over spans, counted on exact boundaries. A span is a hit only when its start, end and label all agree. Below that come four rates over whole examples: how often the title, the options, the settings and _all three at once_ came out right.

The final line is TIME resolvability. The share of `TIME` spans that the grammar can actually turn into a deadline, reported for both the gold spans and the predicted ones. A gap between the two numbers means the model is labelling time expressions the grammar does not cover.

With `--slice`, the exact-match rate is also broken down by the difficulty flags each example carries (`no_space`, `meta_options`, `typo`, `explicit_sep`, etc) worst first.

To see how far rules alone get you on the same data:

```bash
python scripts/eval_parser.py --baseline
```

This evaluates the performance against the same testing dataset, but tests on a baseline model that draws boundaries based on simple regex rules. This serves as a benchmark for the model.

### 5. Export to ONNX (Optional)

This codespace also comes with an ONNX export pipeline that produces a lightweight inference model that doesn't require torch nor transformers. If you just want to play with the model and not deploy it, you can skip this section.

```bash
python scripts/export_onnx.py dist/<checkpoint>
```

| Flag          | Default | What it does                                                                  |
| ------------- | ------- | ----------------------------------------------------------------------------- |
| `model_dir`   | —       | The checkpoint directory to convert. Positional and required.                 |
| `--quantize`  | off     | Also write an int8 build alongside the float one.                             |
| `--tolerance` | `1e-4`  | Upper bound on the raw logit difference from PyTorch that triggers a warning. |

The export writes `model.onnx` into the same checkpoint directory, then runs both models over real sentences and compares them. Two criteria are tested: label agreement and logit distance. If two models disagree on a single token tag, the onnx export has unpredictable behaviors so the process is aborted. If the logit difference exceeds the stipulated threshold a warning is raised but this is not an export stopper.

Its results are appended to the same `train_report.json` the training run wrote, under an `onnx` key, including size, opset, the largest difference seen, the label mismatch count, the export timestamp and the ONNX Runtime version.

### 6. Use the model

This is the other half of the parsing pipeline. Internally the transformer, the ONNX export and the baseline each do one job: decide where the spans are. Each then hands the same `[(start, end, label)]` to the same rule layer, which looks the settings up in the lexicon and runs the time grammar. That is why all three `parse` calls return the same dict: `text`, `tags`, `spans` and `target`, plus `confidence` from the two model paths and `truncated` from ONNX. Anything reading `target` works against all three unchanged, so the three blocks below are interchangeable:

```python
from datetime import datetime, timedelta, timezone
from pollparse.resolve import resolve

text = "晚餐吃什麼？滷肉飯 牛肉麵 明天中午截止可複選"

# if you use ONNX export
from pollparse.model.onnx_tagger import OnnxTagger
tagger = OnnxTagger("dist/<checkpoint>")
parsed = tagger.parse(text)

# if you use the torch transformer
from pollparse.model.predict import Tagger
tagger = Tagger("dist/<checkpoint>") # device="cuda" / "mps" if you want
parsed = tagger.parse(text)

# if you want to test the baseline
from pollparse.baseline.parser import parse
parsed = parse(text)


parsed["target"]["title"]                      # '晚餐吃什麼'
parsed["target"]["options"]                    # ['滷肉飯', '牛肉麵']
parsed["target"]["settings"]["multichoice"]    # True

now = datetime.now(timezone(timedelta(hours=8))) # timezone is required to produce meaningful deadline
deadline = parsed["target"]["settings"]["deadline"]
when = resolve(deadline, now)["at"] if deadline else None
```

`resolve` is a separate call because it needs the caller's `now`. What comes back from `parse` records what the writer said (`{"kind": "absolute", "day_offset": 1, "part": "中午"}`), and `resolve`'s job is to decide on the most reasonable deadline according to current time.

## Data Journey and Lifecycle

Labelled text becomes weights:

```text
your markup (.txt)
   │
   │  markup.load_file()          <t>…</t> → spans, settings looked up in the lexicon
   ▼
   │  validate.check_all()        tags/spans must decode into each other, options must
   │                              not contain blanks, no option before the title …
   │                              one bad example aborts the write
   ▼
dist/{train,dev}.jsonl
   │
   │  train_model.py              fine-tune, score dev after every epoch
   ▼
dist/<checkpoint>/                weights + tokenizer + train_report.json
   │
   │  export_onnx.py              convert, verify against PyTorch, append to the report
   ▼
model.onnx
```

And a raw string becomes a poll:

```text
                                  raw text
                                     │
  ╭─────────────────────────────── parse(text) ────────────────────────────────╮
  │                                  │                                         │
  │   ┌── spans_from_rules(text) ────┤  normalize, then regex + lexicon        │
  │   └── tagger.spans(text) ────────┘  Tagger or OnnxTagger                   │
  │                  │                                                         │
  │                  ▼                                                         │
  │        [(start, end, label), ...]                                          │
  │                  │                                                         │
  │                  ▼                                                         │
  │        build_result(text, spans)    normalize, then the time grammar       │
  │                  │                  and the lexicon turn each span         │
  │                  │                  into a value                           │
  ╰──────────────────┼─────────────────────────────────────────────────────────╯
                     ▼
    { title, options, settings, spans, confidence }
                     │
                     ▼
            resolve(deadline, now)
                     │
                     ▼
             a concrete datetime
```

## Running the tests

```bash
pytest
```

## Licence

MIT — see [LICENSE](LICENSE).

The pretrained encoder this fine-tunes by default, `ckiplab/albert-tiny-chinese`, is distributed under GPL-3.0.
