#!/usr/bin/env python3
"""
Train SpanCat at several span-length ceilings and report what each one cost.

Needs nothing but a folder of annotated DOCX files and somewhere to write to:
no database, no Django settings, no task queue, no containers. That is the
point — the ceiling is a memory-and-time trade-off that wants measuring on a
machine big enough to reach the interesting end of it, and standing the whole
application up on such a machine to answer one question is a waste of it.

    ./scripts/sweep_spancat.py --docs ~/training_docs --ceilings 20,40,64

Writes <out>/results.json and <out>/summary.md, plus the trained model for
each ceiling at <out>/ceiling_<n>/model, ready to copy back and register.

Each ceiling trains in its own subprocess. Peak memory is the headline cost
of raising the ceiling, and a high-water mark read from a process that has
already trained two other models is not that ceiling's peak — it is the
largest of the three. A fresh process per ceiling also means one that gets
killed for running out of memory takes only its own result down with it.

Use --corpus-only first: it tokenizes the corpus and reports what share of
annotations each candidate ceiling could never predict, which costs seconds
rather than hours and is often enough to rule a ceiling in or out.
"""

import argparse
import json
import os
import platform
import random
import resource
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from training.spancat import (  # noqa: E402  (after sys.path setup)
    BASE_MODEL,
    DEFAULT_MAX_SPAN_TOKENS,
    MAX_EPOCHS,
    build_pipeline,
    ensure_base_model,
    load_annotated_docs,
    prepare_examples,
    run_training_loop,
)

# Candidate ceilings reported by --corpus-only when none are given. 20 is the
# ceiling this model used to have, 40 is the current default.
SURVEY_CEILINGS = (10, 20, 30, 40, 48, 64, 80, 128)


def peak_rss_mb():
    """This process's high-water memory use, in MB.

    ru_maxrss is in kilobytes on Linux and bytes on macOS.
    """
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / 1024 if platform.system() == "Linux" else peak / 1024 / 1024


def find_docs(directories):
    """Every .docx under the given directories, in a stable order.

    Word's lock files (~$name.docx) are not documents and cannot be parsed.
    """
    paths = []
    for directory in directories:
        root = Path(directory).expanduser()
        if not root.is_dir():
            raise SystemExit(f"Not a directory: {root}")
        paths.extend(
            p
            for p in sorted(root.rglob("*.docx"))
            if not p.name.startswith("~$")
        )
    return paths


def split_corpus(train_data, dev_share, seed):
    """Divide documents into train and dev, the same way for every ceiling.

    Seeded and applied to the documents before anything is tokenized, so each
    ceiling is scored on identical held-out material. Comparing ceilings whose
    dev sets differ would mostly measure the luck of the split.
    """
    shuffled = list(train_data)
    random.Random(seed).shuffle(shuffled)
    split_at = int(len(shuffled) * (1 - dev_share))
    return shuffled[:split_at], shuffled[split_at:]


def survey_corpus(train_data, ceilings):
    """Report the corpus's span lengths and what each ceiling cannot reach.

    Tokenizes with the base model but trains nothing.
    """
    import spacy

    nlp = spacy.load(BASE_MODEL)
    _examples, stats = prepare_examples(nlp, train_data, max_tokens=None)

    return {
        "annotations": stats.total,
        "aligned": stats.kept,
        "dropped": stats.dropped,
        "longest_span_tokens": max(stats.token_lengths, default=0),
        "token_lengths": dict(sorted(stats.token_lengths.items())),
        "unreachable": {
            str(c): {
                "annotations": stats.over(c),
                "share": round(stats.unreachable_share(c), 5),
            }
            for c in ceilings
        },
    }


def train_one(ceiling, train_docs, dev_docs, out_dir, seed):
    """Train at a single ceiling and return everything measured about the run."""
    model_dir = out_dir / "model"
    model_dir.mkdir(parents=True, exist_ok=True)

    # Same starting point for every ceiling, so a difference in the results is
    # the ceiling's doing and not a different shuffle.
    random.seed(seed)

    started = time.monotonic()
    nlp = build_pipeline(ceiling)

    nlp.initialize(lambda: prepare_examples(nlp, train_docs[:10], ceiling)[0])

    train_examples, train_stats = prepare_examples(nlp, train_docs, ceiling)
    dev_examples, dev_stats = prepare_examples(nlp, dev_docs, ceiling)
    prepared_at = time.monotonic()

    best_scores, history = run_training_loop(
        nlp, train_examples, dev_examples, model_dir, on_epoch=print
    )

    return {
        "ceiling": ceiling,
        "status": "ok",
        "documents": {"train": len(train_docs), "dev": len(dev_docs)},
        "corpus": {
            "annotations": train_stats.total + dev_stats.total,
            "dropped": train_stats.dropped + dev_stats.dropped,
            "over_ceiling": train_stats.over(ceiling)
            + dev_stats.over(ceiling),
            "unreachable_share_if_not_split": round(
                train_stats.unreachable_share(ceiling), 5
            ),
            "split": train_stats.split + dev_stats.split,
            "pieces_from_splitting": train_stats.pieces + dev_stats.pieces,
        },
        "best": {
            "precision": best_scores.get("spans_sc_p"),
            "recall": best_scores.get("spans_sc_r"),
            "f1": best_scores.get("spans_sc_f"),
            "epoch": max(
                (r.epoch for r in history if r.improved), default=None
            ),
        },
        "epochs": [
            {
                "epoch": r.epoch,
                "loss": round(r.loss, 4),
                "precision": round(r.precision, 5),
                "recall": round(r.recall, 5),
                "f1": round(r.f1, 5),
                "seconds": round(r.seconds, 1),
            }
            for r in history
        ],
        "early_stopped": len(history) < MAX_EPOCHS,
        "timing": {
            "prepare_seconds": round(prepared_at - started, 1),
            "train_seconds": round(time.monotonic() - prepared_at, 1),
            "total_seconds": round(time.monotonic() - started, 1),
        },
        "peak_rss_mb": round(peak_rss_mb(), 1),
        "model_dir": str(model_dir),
    }


def write_summary(path, report):
    """A markdown table of the runs, for pasting somewhere a human will read."""
    lines = [
        "# SpanCat ceiling sweep",
        "",
        f"- Documents: {report['documents']}"
        f" ({report['skipped_documents']} skipped)",
        f"- Generated: {report['generated_at']}",
        f"- Host: {report['host']['platform']}, {report['host']['cpus']} CPUs",
        "",
    ]

    survey = report.get("survey")
    if survey:
        lines += [
            "## Corpus coverage by ceiling",
            "",
            f"{survey['annotations']} annotations, "
            f"longest {survey['longest_span_tokens']} tokens.",
            "",
            "| Ceiling | Unreachable annotations | Share |",
            "| --- | --- | --- |",
        ]
        for ceiling, counts in survey["unreachable"].items():
            lines.append(
                f"| {ceiling} | {counts['annotations']} | "
                f"{counts['share']:.2%} |"
            )
        lines.append("")

    runs = [r for r in report["runs"] if r.get("status") == "ok"]
    if runs:
        lines += [
            "## Runs",
            "",
            "| Ceiling | P | R | F1 | Best epoch | Epochs | Train (min) | Peak RSS (GB) | Split spans |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for run in runs:
            best = run["best"]
            cell = lambda v: f"{v:.4f}" if isinstance(v, float) else "-"  # noqa: E731
            lines.append(
                f"| {run['ceiling']} "
                f"| {cell(best['precision'])} "
                f"| {cell(best['recall'])} "
                f"| {cell(best['f1'])} "
                f"| {best['epoch'] or '-'} "
                f"| {len(run['epochs'])} "
                f"| {run['timing']['train_seconds'] / 60:.1f} "
                f"| {run['peak_rss_mb'] / 1024:.1f} "
                f"| {run['corpus']['split']} |"
            )
        lines.append("")

    failed = [r for r in report["runs"] if r.get("status") != "ok"]
    if failed:
        lines += ["## Failed", ""]
        lines += [
            f"- ceiling {r['ceiling']}: {r.get('error', 'unknown error')}"
            for r in failed
        ]
        lines.append("")

    path.write_text("\n".join(lines))


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--docs",
        nargs="+",
        required=True,
        metavar="DIR",
        help="Directories of highlighted DOCX training documents.",
    )
    parser.add_argument(
        "--ceilings",
        default=str(DEFAULT_MAX_SPAN_TOKENS),
        help="Comma-separated span-token ceilings to train at, e.g. 20,40,64.",
    )
    parser.add_argument(
        "--out",
        default="sweep",
        help="Directory for the models and the report (default: sweep).",
    )
    parser.add_argument(
        "--dev-share",
        type=float,
        default=0.2,
        help="Fraction of documents held back for evaluation (default: 0.2).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Seed for the train/dev split and batch order (default: 0).",
    )
    parser.add_argument(
        "--corpus-only",
        action="store_true",
        help="Report span lengths and ceiling coverage, then stop.",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Fail rather than fetch the base model if it is missing.",
    )
    parser.add_argument(
        "--train-one",
        type=int,
        help=argparse.SUPPRESS,  # internal: train one ceiling in this process
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    ceilings = [int(c) for c in args.ceilings.split(",") if c.strip()]
    out_root = Path(args.out).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    ensure_base_model(download=not args.no_download, log=print)

    paths = find_docs(args.docs)
    if not paths:
        raise SystemExit(f"No .docx files found under {', '.join(args.docs)}")

    train_data, skipped = load_annotated_docs(paths)
    for path, why in skipped:
        print(f"Skipped {path}: {why}")
    if not train_data:
        raise SystemExit("No annotated spans found in any document.")
    print(f"{len(train_data)} annotated documents loaded.")

    train_docs, dev_docs = split_corpus(train_data, args.dev_share, args.seed)

    # A child process training the single ceiling it was asked for.
    if args.train_one is not None:
        out_dir = out_root / f"ceiling_{args.train_one}"
        result = train_one(
            args.train_one, train_docs, dev_docs, out_dir, args.seed
        )
        (out_dir / "result.json").write_text(json.dumps(result, indent=2))
        f1 = result["best"]["f1"]
        print(
            f"Ceiling {args.train_one}: F1 {f1 if f1 is None else round(f1, 4)}, "
            f"peak {result['peak_rss_mb'] / 1024:.1f}GB, "
            f"{result['timing']['total_seconds'] / 60:.1f} min"
        )
        return 0

    report = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "host": {
            "platform": platform.platform(),
            "cpus": os.cpu_count(),
        },
        "documents": len(train_data),
        "skipped_documents": len(skipped),
        "seed": args.seed,
        "dev_share": args.dev_share,
        "runs": [],
    }

    survey_at = ceilings if not args.corpus_only else SURVEY_CEILINGS
    print("Surveying span lengths...")
    report["survey"] = survey_corpus(train_data, survey_at)
    for ceiling, counts in report["survey"]["unreachable"].items():
        print(
            f"  ceiling {ceiling:>4}: {counts['share']:.2%} of annotations "
            f"unreachable ({counts['annotations']})"
        )

    if not args.corpus_only:
        for ceiling in ceilings:
            print(f"\n=== ceiling {ceiling} ===", flush=True)
            out_dir = out_root / f"ceiling_{ceiling}"
            out_dir.mkdir(parents=True, exist_ok=True)

            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--train-one",
                    str(ceiling),
                    "--docs",
                    *args.docs,
                    "--out",
                    str(out_root),
                    "--dev-share",
                    str(args.dev_share),
                    "--seed",
                    str(args.seed),
                    "--no-download",
                ],
                check=False,
            )

            result_file = out_dir / "result.json"
            if completed.returncode == 0 and result_file.exists():
                report["runs"].append(json.loads(result_file.read_text()))
            else:
                # Out of memory is the expected failure at a high ceiling, and
                # it kills the child rather than raising anything catchable.
                report["runs"].append(
                    {
                        "ceiling": ceiling,
                        "status": "failed",
                        "error": f"subprocess exited {completed.returncode} "
                        f"(negative means killed by that signal; -9 is "
                        f"usually the OOM killer)",
                    }
                )
                print(f"Ceiling {ceiling} failed; continuing.")

    (out_root / "results.json").write_text(json.dumps(report, indent=2))
    write_summary(out_root / "summary.md", report)
    print(f"\nWrote {out_root / 'results.json'} and {out_root / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
