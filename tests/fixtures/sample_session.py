"""Builders for synthetic 30s / 50-event session data.

Kept as code (not a static .jsonl) so the fixture stays in sync with any
field-name changes in ``hang_pipeline``.
"""

from __future__ import annotations

from common.hang_pipeline import (
    NormalisedEvent,
    SessionSummary,
    Severity,
    SummaryBuilder,
    bucket_severity,
    compute_fingerprint,
)


def make_events(count: int = 50, duration_window_ms: int = 30_000) -> list[NormalisedEvent]:
    """Produce ``count`` synthetic events spread over ``duration_window_ms``.

    Distribution: ~10 unique fingerprints, biased toward a few hot clusters so
    output stays compact under the token-budget contract.
    """
    events: list[NormalisedEvent] = []
    symbols = [
        "[ImageDecoder decode:]",
        "[NetworkSession fetch:]",
        "MainViewModel.refresh()",
        "[FileCache flush]",
        "RunningBoard watchdog",
        "[Layout calculateBounds]",
        "[Database query:]",
        "AnimationCoordinator.tick",
        "[AudioEngine render]",
        "[Notification post]",
    ]
    # Hot clusters: first 3 symbols get most of the volume.
    hot_share = [22, 12, 8]  # 42 events across hot clusters
    cold_share = [1] * (count - sum(hot_share))  # remaining spread across cold clusters
    shares = hot_share + cold_share
    delta_step = duration_window_ms // count
    for i, share_idx in enumerate(_flatten_share(shares)):
        symbol = symbols[share_idx % len(symbols)]
        # Hot clusters get higher durations.
        duration = 600 + (share_idx * 80) + (i % 5) * 20
        events.append(
            NormalisedEvent(
                delta_ms=delta_step * i,
                process="MyApp",
                pid=4242,
                duration_ms=duration,
                severity=bucket_severity(duration),
                symbol=symbol,
                message_prefix=f"hang in {symbol}",
                fingerprint=compute_fingerprint(symbol, f"hang in {symbol}"),
                raw_message=f"Hang detected: {duration}ms in {symbol}",
            )
        )
    return events


def _flatten_share(shares: list[int]) -> list[int]:
    """Convert per-bucket counts into a flat index list."""
    return [idx for idx, count in enumerate(shares) for _ in range(count)]


def make_summary(
    event_count: int = 50,
    session_id: str = "hang-20260522-143052-abcd",
    top_n: int | None = None,
    extras: dict | None = None,
) -> SessionSummary:
    """Run the pipeline against synthetic events and return a SessionSummary."""
    events = make_events(event_count)
    builder = SummaryBuilder(
        session_id=session_id,
        started_at="2026-05-22T14:30:52",
        duration_ms=30_000,
        matched_lines=event_count,
        total_lines=event_count * 10,
        dropped_below_threshold=event_count // 5,
        extras=extras or {},
    )
    return builder.build(events, top_n=top_n)


def assert_token_budget(text: str, max_tokens: int) -> None:
    """Char/4 estimator — matches ``hang_pipeline.estimate_tokens`` exactly."""
    actual = len(text) // 4
    assert actual <= max_tokens, (
        f"Token budget exceeded: {actual} > {max_tokens}\n--- output ---\n{text}"
    )
