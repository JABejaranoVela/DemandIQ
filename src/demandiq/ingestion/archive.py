import hashlib
import os
import tempfile
from pathlib import Path

from demandiq.ingestion.m5 import InputError


def archive_source(source: Path, directory: Path) -> dict:
    """Hash the bytes being copied; parse that copy, never the changing original."""
    if not source.is_file():
        raise InputError("missing_file", f"Required file not found: {source.name}")
    directory.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    temporary: Path | None = None
    try:
        with (
            source.open("rb") as reader,
            tempfile.NamedTemporaryFile(dir=directory, suffix=".tmp", delete=False) as writer,
        ):
            temporary = Path(writer.name)
            while block := reader.read(1024 * 1024):
                digest.update(block)
                writer.write(block)
                size += len(block)
        checksum = digest.hexdigest()
        destination = directory / f"{checksum}.csv"
        if destination.exists():
            with destination.open("rb") as existing:
                if hashlib.file_digest(existing, "sha256").hexdigest() != checksum:
                    raise InputError(
                        "archive_corrupt", "An archived source failed checksum verification"
                    )
            temporary.unlink()
        else:
            os.replace(temporary, destination)
        return {
            "filename": source.name,
            "sha256": checksum,
            "size_bytes": size,
            "archive_name": destination.name,
        }
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
