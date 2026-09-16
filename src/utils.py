"""Shared helpers for the Trufi data-understanding pipeline."""

import io
from pathlib import Path

import polars as pl

ENCODING_ISSUES: list[str] = []


def read_csv_safe(path: Path, **kwargs) -> pl.DataFrame:
    """Read a CSV, falling back to Latin-1 decoding on UTF-8 failures.

    Five raw files mix UTF-8 with Latin-1-encoded accented characters
    (e.g. municipio names like "Santivañez"). Latin-1 maps every byte
    1:1 to a codepoint, so re-decoding the whole file that way recovers
    the correct text without touching the pure-ASCII majority of rows.
    """
    try:
        return pl.read_csv(path, **kwargs)
    except Exception as e:
        if "utf-8" not in str(e).lower() and "utf8" not in str(e).lower():
            raise
        raw = path.read_bytes()
        text = raw.decode("latin-1")
        ENCODING_ISSUES.append(path.name)
        return pl.read_csv(io.StringIO(text), **kwargs)
