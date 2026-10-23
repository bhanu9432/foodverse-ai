"""Small helpers for cleaning up model output."""


def num(x, lo: float = 0, hi: float = 1e6, default: float = 0.0) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    if v != v:  # NaN
        return default
    return max(lo, min(hi, v))


def text(x, limit: int = 400, default: str = "") -> str:
    if x is None:
        return default
    return str(x).strip()[:limit]


def as_list(x) -> list:
    return x if isinstance(x, list) else []
