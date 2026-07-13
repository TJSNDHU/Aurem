# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "polars>=1.31.0",
#     "huggingface-hub",
#     "datasets",
#     "ascii-graph",
# ]
# ///
"""
Analyze educational quality trends across CommonCrawl dumps using Polars streaming.

Answers: "Is the web getting more educational over time?"

Demonstrates Polars HF Hub integration - process 50M+ docs without downloading 300GB+.

Example usage:
    # Analyze English PDFs (default)
    uv run finepdfs-stats.py

    # Analyze all 70+ languages
    uv run finepdfs-stats.py --all-languages

    # Quick test
    uv run finepdfs-stats.py --limit 10000 --show-plan

    # Save results to HF Hub
    uv run finepdfs-stats.py --output-repo username/finepdfs-temporal-stats

    # Run on HF Jobs
    hf jobs uv run \\
        -s HF_TOKEN \\
        -e HF_XET_HIGH_PERFORMANCE=1 \\
        https://huggingface.co/datasets/uv-scripts/dataset-stats/raw/main/finepdfs-stats.py \\
        -- --output-repo username/stats
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

import polars as pl
from ascii_graph import Pyasciigraph
from datasets import Dataset
from huggingface_hub import HfApi, create_repo, list_repo_tree, login

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Common language+script codes for finepdfs-edu
COMMON_LANGUAGES = {
    "eng_Latn": "English (Latin script)",
    "fra_Latn": "French (Latin script)",
    "deu_Latn": "German (Latin script)",
    "spa_Latn": "Spanish (Latin script)",
    "por_Latn": "Portuguese (Latin script)",
    "ita_Latn": "Italian (Latin script)",
    "nld_Latn": "Dutch (Latin script)",
    "pol_Latn": "Polish (Latin script)",
    "rus_Cyrl": "Russian (Cyrillic script)",
    "zho_Hans": "Chinese (Simplified)",
    "zho_Hant": "Chinese (Traditional)",
    "jpn_Jpan": "Japanese",
    "kor_Hang": "Korean",
    "ara_Arab": "Arabic",
    "hin_Deva": "Hindi (Devanagari)",
}


def list_available_languages(dataset_id: str) -> list[str]:
    """List available language subsets in the dataset."""
    try:
        tree = list_repo_tree(dataset_id, path_in_repo="data", repo_type="dataset")
        languages = [
            item.path.replace("data/", "")
            for item in tree
            if item.path.startswith("data/")
            and "/" not in item.path.replace("data/", "")
        ]
        return sorted(languages)
    except Exception as e:
        logger.warning(f"Could not list languages: {e}")
        return list(COMMON_LANGUAGES.keys())


def compute_temporal_stats(df: pl.LazyFrame, output_path: Path) -> pl.DataFrame:
    """Single scan: compute stats grouped by dump for temporal analysis."""
    query = df.group_by("dump").agg(
        pl.len().alias("doc_count"),
        pl.col("token_count").sum().alias("total_tokens"),
        pl.col("fw_edu_scores").list.mean().mean().alias("avg_edu_score"),
        (pl.col("fw_edu_scores").list.mean() >= 3).sum().alias("high_edu_count"),
    )
    query.sink_parquet(output_path, engine="streaming")
    return pl.read_parquet(output_path)


def compute_global_stats(temporal: pl.DataFrame) -> pl.DataFrame:
    """Compute global stats from temporal breakdown."""
    total = temporal["doc_count"].sum()
    return pl.DataFrame(
        {
            "total_docs": [total],
            "total_tokens": [temporal["total_tokens"].sum()],
            "avg_edu_score": [
                (temporal["avg_edu_score"] * temporal["doc_count"]).sum() / total
            ],
            "high_edu_rate": [temporal["high_edu_count"].sum() / total],
            "num_dumps": [len(temporal)],
        }
    )


def format_temporal_stats(temporal: pl.DataFrame) -> pl.DataFrame:
    """Format temporal stats with high_edu_rate, sorted chronologically."""
    return (
        temporal.with_columns(
            (pl.col("high_edu_count") / pl.col("doc_count")).alias("high_edu_rate")
        )
        .select(["dump", "doc_count", "avg_edu_score", "high_edu_rate"])
        .sort(
            "dump"
        )  # Chronological order (CC-MAIN-2017-xx comes before CC-MAIN-2024-xx)
    )


def create_ascii_charts(temporal_stats: pl.DataFrame) -> str:
    """Create ASCII bar charts showing temporal trends."""
    # Extract year from dump name (CC-MAIN-2024-42 -> 2024)
    # Group by year and average the values for cleaner display
    yearly = (
        temporal_stats.with_columns(
            pl.col("dump").str.extract(r"CC-MAIN-(\d{4})", 1).alias("year")
        )
        .group_by("year")
        .agg(
            pl.col("doc_count").sum(),
            pl.col("avg_edu_score").mean(),
            pl.col("high_edu_rate").mean(),
        )
        .sort("year")
    )

    lines = []

    # High edu rate chart (more dramatic differences)
    data_rate = [
        (row["year"], row["high_edu_rate"] * 100)
        for row in yearly.iter_rows(named=True)
    ]
    graph = Pyasciigraph(line_length=60, float_format="{0:.1f}%")
    lines.extend(graph.graph("High Educational Content (edu >= 3)", data_rate))

    lines.append("")

    # Avg edu score chart
    data_score = [
        (row["year"], row["avg_edu_score"]) for row in yearly.iter_rows(named=True)
    ]
    graph2 = Pyasciigraph(line_length=60, float_format="{0:.2f}")
    lines.extend(graph2.graph("Average Educational Score", data_score))

    return "\n".join(lines)


def _build_readme_header(args, stats: dict, scope: str) -> str:
    """Build README header section."""
    return f"""---
tags:
  - uv-script
  - statistics
  - polars
  - finepdfs-edu
  - temporal-analysis
license: odc-by
configs:
  - config_name: global_stats
    data_files: global_stats/train-*.parquet
  - config_name: temporal_stats
    data_files: temporal_stats/train-*.parquet
default_viewer_config: temporal_stats
---

# Is the Web Getting More Educational?

Temporal analysis of educational quality in **{scope}** across {stats.get("num_dumps", 0)} CommonCrawl dumps.
"""


def _build_readme_trend_section(ascii_charts: str, temporal_stats: pl.DataFrame) -> str:
    """Build README trend section with charts and key findings."""
    yearly = (
        temporal_stats.with_columns(
            pl.col("dump").str.extract(r"CC-MAIN-(\d{4})", 1).alias("year")
        )
        .group_by("year")
        .agg(
            pl.col("doc_count").sum(),
            pl.col("avg_edu_score").mean(),
            pl.col("high_edu_rate").mean(),
        )
        .sort("year")
    )
    first_year = yearly.head(1).to_dicts()[0]
    last_year = yearly.tail(1).to_dicts()[0]

    return f"""
## Trend

```
{ascii_charts}
```

## Key Finding

| Year | Avg Edu Score | High Edu Rate |
|------|---------------|---------------|
| {first_year["year"]} | {first_year["avg_edu_score"]:.2f} | {first_year["high_edu_rate"] * 100:.1f}% |
| {last_year["year"]} | {last_year["avg_edu_score"]:.2f} | {last_year["high_edu_rate"] * 100:.1f}% |
"""


def _build_readme_summary(stats: dict, scope: str, scan_time: float, total_docs: int) -> str:
    """Build README summary and performance sections."""
    docs_per_sec = total_docs / scan_time if scan_time > 0 else 0
    
    return f"""
## Performance

- **{total_docs:,} documents** processed in **{scan_time:.0f} seconds**
- **{docs_per_sec:,.0f} docs/sec** using Polars streaming
- Single scan, no full dataset download required

## Summary

| Metric | Value |
|--------|-------|
| Scope | {scope} |
| Total Documents | {total_docs:,} |
| Total Tokens | {stats.get("total_tokens", 0):,} |
| Avg Edu Score | {stats.get("avg_edu_score", 0):.3f} |
| High Edu Rate | {stats.get("high_edu_rate", 0) * 100:.1f}% |
| CommonCrawl Dumps | {stats.get("num_dumps", 0)} |

## Files

- `global_stats` - Overall summary
- `temporal_stats` - Per-dump breakdown (sorted chronologically)
"""


def _build_readme_footer(args) -> str:
    """Build README footer with reproduction instructions."""
    lang_arg = "--all-languages" if args.all_languages else f"--lang {args.lang}"
    return f"""
## Reproduce

```bash
uv run https://huggingface.co/datasets/uv-scripts/dataset-stats/raw/main/finepdfs-stats.py \\
    {lang_arg} --output-repo your-username/stats
```

## Source

- **Dataset**: [{args.source_dataset}](https://huggingface.co/datasets/{args.source_dataset})
- **Script**: [uv-scripts/dataset-stats](https://huggingface.co/datasets/uv-scripts/dataset-stats)
"""


def create_readme(
    args,
    global_stats: pl.DataFrame,
    temporal_stats: pl.DataFrame,
    scan_time: float,
    ascii_charts: str,
) -> str:
    """Create README content for the stats dataset."""
    stats = global_stats.to_dicts()[0]
    total_docs = stats.get("total_docs", 0)

    scope = (
        "all languages"
        if args.all_languages
        else COMMON_LANGUAGES.get(args.lang, args.lang)
    )

    header = _build_readme_header(args, stats, scope)
    trend = _build_readme_trend_section(ascii_charts, temporal_stats)
    summary = _build_readme_summary(stats, scope, scan_time, total_docs)
    footer = _build_readme_footer(args)

    return header + trend + summary + footer


def main():
    parser = argparse.ArgumentParser(
        description="Analyze educational quality trends across CommonCrawl dumps",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--source-dataset",
        type=str,
        default="HuggingFaceFW/finepdfs-edu",
        help="Source dataset (default: HuggingFaceFW/finepdfs-edu)",
    )

    parser.add_argument(
        "--lang",
        type=str,
        default="eng_Latn",
        help="Language+script code (default: eng_Latn)",
    )

    parser.add_argument(
        "--all-languages",
        action="store_true",
        help="Analyze all languages (70+) instead of single language",
    )

    parser.add_argument(
        "--show-plan",
        action="store_true",
        help="Show Polars query plan (demonstrates optimization)",
    )

    parser.add_argument(
        "--list-languages",
        action="store_true",
        help="List available languages and exit",
    )

    parser.add_argument(
        "--limit",
        type=int,
        help="Limit to first N rows (for testing)",
    )

    parser.add_argument(
        "--output-repo",
        type=str,
        help="HuggingFace dataset repository to upload results",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="./stats_output",
        help="Local directory for output files",
    )

    parser.add_argument(
        "--hf-token",
        type=str,
        help="HuggingFace API token (or set HF_TOKEN env var)",
    )

    parser.add_argument(
        "--private",
        action="store_true",
        help="Make the output dataset private",
    )

    args = parser.parse