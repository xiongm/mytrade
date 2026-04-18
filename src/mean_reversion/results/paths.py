from pathlib import Path

from .models import RunContext


def bucket_dir(root: Path, context: RunContext) -> Path:
    bucket = f"{context.market}__{context.instrument_type}__{context.source}"
    return root / context.strategy / bucket


def bundle_dir(root: Path, context: RunContext, fingerprint: str) -> Path:
    return bucket_dir(root, context) / "bundles" / fingerprint


def history_file(root: Path, context: RunContext) -> Path:
    return bucket_dir(root, context) / "history" / f"{context.timestamp}.json"


def latest_dir(root: Path, context: RunContext) -> Path:
    return bucket_dir(root, context) / "latest"
