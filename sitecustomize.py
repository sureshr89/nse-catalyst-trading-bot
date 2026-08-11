"""
Runtime reliability patch for the Streamlit paper bot.

This file is loaded automatically by Python's site module on startup.
It keeps large Yahoo Finance requests from blocking the trading worker.
Single-ticker requests are left untouched except for a safe timeout.
Large multi-ticker requests are split into small batches and downloaded
concurrently; failed batches are skipped instead of freezing the scanner.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import yfinance as yf


_ORIGINAL_DOWNLOAD = yf.download
_DEFAULT_TIMEOUT = 10
_BATCH_SIZE = 25
_MAX_WORKERS = 4


def _as_ticker_list(tickers):
    if isinstance(tickers, str):
        return [item.strip() for item in tickers.split() if item.strip()]
    try:
        return [str(item).strip() for item in tickers if str(item).strip()]
    except TypeError:
        return [str(tickers).strip()]


def _download_batch(batch, kwargs):
    local_kwargs = dict(kwargs)
    local_kwargs["tickers"] = batch
    local_kwargs["timeout"] = _DEFAULT_TIMEOUT
    # Let this outer batch layer control concurrency.
    local_kwargs["threads"] = False
    try:
        return _ORIGINAL_DOWNLOAD(**local_kwargs)
    except Exception as exc:
        print(f"Yahoo batch failed ({len(batch)} tickers): {exc}")
        return pd.DataFrame()


def _safe_download(*args, **kwargs):
    # Preserve positional yfinance usage.
    if args:
        if "tickers" not in kwargs:
            kwargs["tickers"] = args[0]
        args = args[1:]
    if args:
        # Unusual positional arguments: fall back to the original function.
        return _ORIGINAL_DOWNLOAD(*args, **kwargs)

    tickers = _as_ticker_list(kwargs.get("tickers", ""))
    if not tickers:
        kwargs.setdefault("timeout", _DEFAULT_TIMEOUT)
        return _ORIGINAL_DOWNLOAD(**kwargs)

    kwargs.setdefault("timeout", _DEFAULT_TIMEOUT)

    # Small/single requests do not need batching.
    if len(tickers) <= _BATCH_SIZE:
        return _ORIGINAL_DOWNLOAD(**kwargs)

    batches = [
        tickers[index:index + _BATCH_SIZE]
        for index in range(0, len(tickers), _BATCH_SIZE)
    ]

    frames = []
    executor = ThreadPoolExecutor(max_workers=_MAX_WORKERS)
    futures = [
        executor.submit(_download_batch, batch, kwargs)
        for batch in batches
    ]

    try:
        for future in as_completed(futures, timeout=_DEFAULT_TIMEOUT + 5):
            try:
                frame = future.result()
            except Exception as exc:
                print(f"Yahoo batch worker failed: {exc}")
                continue
            if frame is not None and not frame.empty:
                frames.append(frame)
    except Exception as exc:
        print(f"Yahoo multi-batch timeout: {exc}")
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    if not frames:
        return pd.DataFrame()

    try:
        # yfinance returns a common Datetime index and MultiIndex columns
        # for multi-ticker requests. Concatenating columns preserves the
        # format expected by IndustryDirection._extract_stock_data().
        result = pd.concat(frames, axis=1)
        result = result.loc[:, ~result.columns.duplicated()]
        return result.sort_index()
    except Exception as exc:
        print(f"Yahoo batch merge failed: {exc}")
        return pd.DataFrame()


# Install once; avoid wrapping the wrapper if Streamlit reloads modules.
if getattr(yf.download, "_nse_catalyst_patched", False) is False:
    _safe_download._nse_catalyst_patched = True
    yf.download = _safe_download
