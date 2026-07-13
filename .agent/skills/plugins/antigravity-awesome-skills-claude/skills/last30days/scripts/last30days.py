#!/usr/bin/env python3
"""
last30days - Research a topic from the last 30 days on Reddit + X.

Usage:
    python3 last30days.py <topic> [options]

Options:
    --mock              Use fixtures instead of real API calls
    --emit=MODE         Output mode: compact|json|md|context|path (default: compact)
    --sources=MODE      Source selection: auto|reddit|x|both (default: auto)
    --quick             Faster research with fewer sources (8-12 each)
    --deep              Comprehensive research with more sources (50-70 Reddit, 40-60 X)
    --debug             Enable verbose debug logging
"""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# Add lib to path
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from lib import (
    dates,
    dedupe,
    env,
    http,
    models,
    normalize,
    openai_reddit,
    reddit_enrich,
    render,
    schema,
    score,
    ui,
    websearch,
    xai_x,
)


def load_fixture(name: str) -> dict:
    """Load a fixture file."""
    fixture_path = SCRIPT_DIR.parent / "fixtures" / name
    if fixture_path.exists():
        with open(fixture_path) as f:
            return json.load(f)
    return {}


def _search_reddit(
    topic: str,
    config: dict,
    selected_models: dict,
    from_date: str,
    to_date: str,
    depth: str,
    mock: bool,
) -> tuple:
    """Search Reddit via OpenAI (runs in thread).

    Returns:
        Tuple of (reddit_items, raw_openai, error)
    """
    raw_openai = None
    reddit_error = None

    if mock:
        raw_openai = load_fixture("openai_sample.json")
    else:
        try:
            raw_openai = openai_reddit.search_reddit(
                config["OPENAI_API_KEY"],
                selected_models["openai"],
                topic,
                from_date,
                to_date,
                depth=depth,
            )
        except http.HTTPError as e:
            raw_openai = {"error": str(e)}
            reddit_error = f"API error: {e}"
        except Exception as e:
            raw_openai = {"error": str(e)}
            reddit_error = f"{type(e).__name__}: {e}"

    # Parse response
    reddit_items = openai_reddit.parse_reddit_response(raw_openai or {})

    # Quick retry with simpler query if few results
    if len(reddit_items) < 5 and not mock and not reddit_error:
        core = openai_reddit._extract_core_subject(topic)
        if core.lower() != topic.lower():
            try:
                retry_raw = openai_reddit.search_reddit(
                    config["OPENAI_API_KEY"],
                    selected_models["openai"],
                    core,
                    from_date, to_date,
                    depth=depth,
                )
                retry_items = openai_reddit.parse_reddit_response(retry_raw)
                # Add items not already found (by URL)
                existing_urls = {item.get("url") for item in reddit_items}
                for item in retry_items:
                    if item.get("url") not in existing_urls:
                        reddit_items.append(item)
            except Exception:
                pass

    return reddit_items, raw_openai, reddit_error


def _search_x(
    topic: str,
    config: dict,
    selected_models: dict,
    from_date: str,
    to_date: str,
    depth: str,
    mock: bool,
) -> tuple:
    """Search X via xAI (runs in thread).

    Returns:
        Tuple of (x_items, raw_xai, error)
    """
    raw_xai = None
    x_error = None

    if mock:
        raw_xai = load_fixture("xai_sample.json")
    else:
        try:
            raw_xai = xai_x.search_x(
                config["XAI_API_KEY"],
                selected_models["xai"],
                topic,
                from_date,
                to_date,
                depth=depth,
            )
        except http.HTTPError as e:
            raw_xai = {"error": str(e)}
            x_error = f"API error: {e}"
        except Exception as e:
            raw_xai = {"error": str(e)}
            x_error = f"{type(e).__name__}: {e}"

    # Parse response
    x_items = xai_x.parse_x_response(raw_xai or {})

    return x_items, raw_xai, x_error


def run_research(
    topic: str,
    sources: str,
    config: dict,
    selected_models: dict,
    from_date: str,
    to_date: str,
    depth: str = "default",
    mock: bool = False,
    progress: ui.ProgressDisplay = None,
) -> tuple:
    """Run the research pipeline.

    Returns:
        Tuple of (reddit_items, x_items, web_needed, raw_openai, raw_xai, raw_reddit_enriched, reddit_error, x_error)

    Note: web_needed is True when WebSearch should be performed by Claude.
    The script outputs a marker and Claude handles WebSearch in its session.
    """
    reddit_items = []
    x_items = []
    raw_openai = None
    raw_xai = None
    raw_reddit_enriched = []
    reddit_error = None
    x_error = None

    # Check if WebSearch is needed (always needed in web-only mode)
    web_needed = sources in ("all", "web", "reddit-web", "x-web")

    # Web-only mode: no API calls needed, Claude handles everything
    if sources == "web":
        if progress:
            progress.start_web_only()
            progress.end_web_only()
        return reddit_items, x_items, True, raw_openai, raw_xai, raw_reddit_enriched, reddit_error, x_error

    # Determine which searches to run
    run_reddit = sources in ("both", "reddit", "all", "reddit-web")
    run_x = sources in ("both", "x", "all", "x-web")

    # Run Reddit and X searches in parallel
    reddit_future = None
    x_future = None

    with ThreadPoolExecutor(max_workers=2) as executor:
        # Submit both searches
        if run_reddit:
            if progress:
                progress.start_reddit()
            reddit_future = executor.submit(
                _search_reddit, topic, config, selected_models,
                from_date, to_date, depth, mock
            )

        if run_x:
            if progress:
                progress.start_x()
            x_future = executor.submit(
                _search_x, topic, config, selected_models,
                from_date, to_date, depth, mock
            )

        # Collect results
        if reddit_future:
            try:
                reddit_items, raw_openai, reddit_error = reddit_future.result()
                if reddit_error and progress:
                    progress.show_error(f"Reddit error: {reddit_error}")
            except Exception as e:
                reddit_error = f"{type(e).__name__}: {e}"
                if progress:
                    progress.show_error(f"Reddit error: {e}")
            if progress:
                progress.end_reddit(len(reddit_items))

        if x_future:
            try:
                x_items, raw_xai, x_error = x_future.result()
                if x_error and progress:
                    progress.show_error(f"X error: {x_error}")
            except Exception as e:
                x_error = f"{type(e).__name__}: {e}"
                if progress:
                    progress.show_error(f"X error: {e}")
            if progress:
                progress.end_x(len(x_items))

    # Enrich Reddit items with real data (sequential, but with error handling per-item)
    if reddit_items:
        if progress:
            progress.start_reddit_enrich(1, len(reddit_items))

        for i, item in enumerate(reddit_items):
            if progress and i > 0:
                progress.update_reddit_enrich(i + 1, len(reddit_items))

            try:
                if mock:
                    mock_thread = load_fixture("reddit_thread_sample.json")
                    reddit_items[i] = reddit_enrich.enrich_reddit_item(item, mock_thread)
                else:
                    reddit_items[i] = reddit_enrich.enrich_reddit_item(item)
            except Exception as e:
                # Log but don't crash - keep the unenriched item
                if progress:
                    progress.show_error(f"Enrich failed for {item.get('url', 'unknown')}: {e}")

            raw_reddit_enriched.append(reddit_items[i])

        if progress:
            progress.end_reddit_enrich()

    return reddit_items, x_items, web_needed, raw_openai, raw_xai, raw_reddit_enriched, reddit_error, x_error


def _parse_args(argv=None):
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Research a topic from the last 30 days on Reddit + X"
    )
    parser.add_argument("topic", nargs="?", help="Topic to research")
    parser.add_argument("--mock", action="store_true", help="Use fixtures")
    parser.add_argument(
        "--emit",
        choices=["compact", "json", "md", "context", "path"],
        default="compact",
        help="Output mode",
    )
    parser.add_argument(
        "--sources",
        choices=["auto", "reddit", "x", "both"],
        default="auto",
        help="Source selection",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Faster research with fewer sources (8-12 each)",
    )
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Comprehensive research with more sources (50-70 Reddit, 40-60 X)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose debug logging",
    )
    parser.add_argument(
        "--include-web",
        action="store_true",
        help="Include general web search alongside Reddit/X (lower weighted)",
    )
    return parser.parse_args(argv)


def _resolve_depth(quick: bool, deep: bool) -> str:
    """Determine the research depth from flags."""
    if quick and deep:
        print("Error: Cannot use both --quick and --deep", file=sys.stderr)
        sys.exit(1)
    if quick:
        return "quick"
    if deep:
        return "deep"
    return "default"


def _resolve_sources(args, config, available):
    """Determine the effective sources mode and any error message."""
    if args.mock:
        return (args.sources if args.sources != "auto" else "both"), None
    sources, error = env.validate_sources(args.sources, available, args.include_web)
    return sources, error


def _select_models(args, config):
    """Select models (mock or real) for the configured sources."""
    if args.mock:
        mock_openai_models = load_fixture("models_openai_sample.json").get("data", [])
        mock_xai_models = load_fixture("models_xai_sample.json").get("data", [])
        return models.get_models(
            {
                "OPENAI_API_KEY": "mock",
                "XAI_API_KEY": "mock",
                **config,
            },
            mock_openai_models,
            mock_xai_models,
        )
    return models.get_models(config)


def _determine_mode(sources: str) -> str:
    """Map a sources value to a human-readable mode string."""
    mapping = {
        "all": "all",
        "both": "both",
        "reddit": "reddit-only",
        "reddit-web": "reddit-web",
        "x": "x-only",
        "x-web": "x-web",
        "web": "web-only",
    }
    return mapping.get(sources, sources)


def _process_items(reddit_items, x_items, from_date, to_date, progress):
    """Normalize, filter, score, sort, and dedupe items."""
    progress.start_processing()

    normalized_reddit = normalize.normalize_reddit_items(reddit_items, from_date, to_date)
    normalized_x = normalize.normalize_x_items(x_items, from_date, to_date)

    filtered_reddit = normalize.filter_by_date_range(normalized_reddit, from_date, to_date)
    filtered_x = normalize.filter_by_date_range(normalized_x, from_date, to_date)

    scored_reddit = score.score_reddit_items(filtered_reddit)
    scored_x = score.score_x_items(filtered_x)

    sorted_reddit = score.sort_items(scored_reddit)
    sorted_x = score.sort_items(scored_x)

    deduped_reddit = dedupe.dedupe_reddit(sorted_reddit)
    deduped_x = dedupe.dedupe_x(sorted_x)

    progress.end_processing()
    return deduped_reddit, deduped_x


def _build_report(
    topic, from_date, to_date, mode, selected_models,
    deduped_reddit, deduped_x, reddit_error, x_error,
    raw_openai, raw_xai, raw_reddit_enriched,
):
    """Create and write the report object."""
    report = schema.create_report(
        topic,
        from_date,
        to_date,
        mode,
        selected_models.get("openai"),
        selected_models.get("xai"),
    )
    report.reddit = deduped_reddit
    report.x = deduped_x
    report.reddit_error = reddit_error
    report.x_error = x_error
    report.context_snippet_md = render.render_context_snippet(report)
    render.write_outputs(report, raw_openai, raw_xai, raw_reddit_enriched)
    return report


def main():
    args = _parse_args()

    # Enable debug logging if requested
    if args.debug:
        os.environ["LAST30DAYS_DEBUG"] = "1"
        from lib import http as http_module
        http_module.DEBUG = True

    depth = _resolve_depth(args.quick, args.deep)

    if not args.topic:
        print("Error: Please provide a topic to research.", file=sys.stderr)
        print("Usage: python3 last30days.py <topic> [options]", file=sys.stderr)
        sys.exit(1)

    # Load config
    config = env.get_config()

    # Check available sources
    available = env.get_available_sources(config)

    sources, error = _resolve_sources(args, config, available)
    if error:
        if "WebSearch fallback" in error:
            print(f"Note: {error}", file=sys.stderr)
        else:
            print(f"Error: {error}", file=sys.stderr)
            sys.exit(1)

    # Get date range
    from_date, to_date = dates.get_date_range(30)

    # Check what keys are missing for promo messaging
    missing_keys = env.get_missing_keys(config)

    # Initialize progress display
    progress = ui.ProgressDisplay(args.topic, show_banner=True)

    # Show promo for missing keys BEFORE research
    if missing_keys != 'none':
        progress.show_promo(missing_keys)

    # Select models
    selected_models = _select_models(args, config)

    # Determine mode string
    mode = _determine_mode(sources)

    # Run research
    reddit_items, x_items, web_needed, raw_openai, raw_xai, raw_reddit_enriched, reddit_error, x_error = run_research(
        args.topic,
        sources,
        config,
        selected_models,
        from_date