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

    Mixes all four Severity tiers, ≥10 unique fingerprints, two processes, and
    a temporal burst + quiet gap so SummaryBuilder's aggregators have content
    to surface. Stress-shape rather than soft-shape so the token-budget tests
    actually exercise the formatter.
    """
    # (symbol, base_duration_ms, severity_band, process) — long symbol prefixes for stress.
    specs = [
        ("[ImageDecoderForLargeRasterAssets decodeWithOptions:]", 1100, "critical", "MyApp"),
        ("[NetworkSession.background fetchUpstreamPayload:]", 900, "critical", "MyApp"),
        ("MainViewModel.refreshFromRemoteSource(timeout:)", 700, "critical", "MyApp"),
        ("[FileCache flushAllDirtyPagesToDisk]", 380, "warn", "MyApp"),
        ("RunningBoard watchdog: assertion expired", 350, "warn", "MyApp"),
        ("[Layout calculateBoundsInsideContainer:withConstraints:]", 310, "warn", "MyApp"),
        ("[Database executeUnboundedQuery:onConnection:]", 180, "minor", "MyApp"),
        ("AnimationCoordinator.tickWithDisplayLinkFrame", 150, "minor", "Helper"),
        ("[AudioEngine renderQuantum:withInterruptions:]", 120, "minor", "Helper"),
        ("[Notification postOnDistributedCenter:]", 100, "minor", "Helper"),
        ("MainThreadDispatch.semaphoreWaitLongerThanForever()", 2800, "frozen", "MyApp"),
        ("[DiskArbitration mountAllRetrying:]", 3200, "frozen", "Helper"),
    ]
    # Per-cluster event counts — first cluster is hot (drives near-max count).
    counts = [18, 6, 4, 5, 4, 3, 3, 2, 2, 1, 1, 1]
    delta_step = duration_window_ms // count
    events: list[NormalisedEvent] = []
    event_idx = 0
    for spec_idx, ((symbol, base_dur, _band, process), per_cluster) in enumerate(
        zip(specs, counts, strict=True)
    ):
        for j in range(per_cluster):
            # Pack the first cluster temporally close to trigger detect_temporal_bursts.
            if spec_idx == 0:
                delta = j * 120  # 18 events inside a 2.1s window
            else:
                # Other clusters spread across the window with a deliberate quiet gap
                # in the middle for detect_quiet_periods to pick up.
                delta = delta_step * event_idx
                if delta_step * event_idx > duration_window_ms // 2:
                    delta += 7000  # 7s gap → triggers quiet_period detection
            duration = base_dur + (j % 4) * 25
            events.append(
                NormalisedEvent(
                    delta_ms=delta,
                    process=process,
                    pid=4242 if process == "MyApp" else 5151,
                    duration_ms=duration,
                    severity=bucket_severity(duration),
                    symbol=symbol,
                    message_prefix=f"hang in {symbol}",
                    fingerprint=compute_fingerprint(symbol, f"hang in {symbol}"),
                    raw_message=f"Hang detected: {duration}ms in {symbol}",
                )
            )
            event_idx += 1
            if event_idx >= count:
                return events
    return events


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
