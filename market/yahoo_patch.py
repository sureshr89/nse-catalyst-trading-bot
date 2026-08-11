"""Reliable Yahoo Finance downloader used by the paper scanner."""

from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import yfinance as yf


_ORIGINAL_DOWNLOAD = yf.download
_TIMEOUT = 10
_BATCH_SIZE = 25
_WORKERS = 4


def _tickers(value):
    if isinstance(value, str):
        return [item.strip() for item in value.split() if item.strip()]
    try:
        return [str(item).strip() for item in value if str(item).strip()]
    except TypeError:
        return [str(value).strip()]


def _batch_download(batch, kwargs):
    local = dict(kwargs)
    local["tickers"] = batch
    local["threads"] = False
    local["timeout"] = _TIMEOUT
    try:
        return _ORIGINAL_DOWNLOAD(**local)
    except Exception as exc:
        print(f"Yahoo batch failed ({len(batch)}): {exc}")
        return pd.DataFrame()


def safe_download(*args, **kwargs):
    if args:
        kwargs.setdefault("tickers", args[0])
        args = args[1:]
    if args:
        return _ORIGINAL_DOWNLOAD(*args, **kwargs)

    names = _tickers(kwargs.get("tickers", ""))
    kwargs.setdefault("timeout", _TIMEOUT)

    if len(names) <= _BATCH_SIZE:
        return _ORIGINAL_DOWNLOAD(**kwargs)

    batches = [
        names[i:i + _BATCH_SIZE]
        for i in range(0, len(names), _BATCH_SIZE)
    ]

    executor = ThreadPoolExecutor(max_workers=_WORKERS)
    futures = [executor.submit(_batch_download, batch, kwargs) for batch in batches]
    frames = []

    try:
        for future in as_completed(futures, timeout=_TIMEOUT + 5):
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
        merged = pd.concat(frames, axis=1)
        merged = merged.loc[:, ~merged.columns.duplicated()]
        return merged.sort_index()
    except Exception as exc:
        print(f"Yahoo batch merge failed: {exc}")
        return pd.DataFrame()


def install():
    if getattr(yf.download, "_nse_catalyst_patched", False):
        return
    safe_download._nse_catalyst_patched = True
    yf.download = safe_download


install()
