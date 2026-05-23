"""Per-stage unit tests for common.hang_pipeline."""

from __future__ import annotations

import json

import pytest

from common.hang_pipeline import (
    FINGERPRINT_VERSION,
    Cluster,
    NormalisedEvent,
    SessionSummary,
    Severity,
    SummaryBuilder,
    above_threshold,
    bucket_severity,
    build_normalised_event,
    cluster_events,
    compress_to_budget,
    compute_fingerprint,
    detect_quiet_periods,
    detect_temporal_bursts,
    diff_sessions,
    estimate_tokens,
    event_from_jsonl,
    event_to_jsonl,
    extract_duration_ms,
    extract_symbol,
    format_cluster_detail,
    format_diff,
    format_l0,
    format_l1,
    format_l2,
    is_hang_message,
    normalise_message,
    parse_log_line,
    process_distribution,
    rank_clusters,
    summary_from_json,
    summary_to_json,
)


# === parse ===


def test_parse_log_line_extracts_hang_event():
    line = (
        "2026-05-22 14:30:52.123456-0800 0x1234 Default   0x0 1234 0 "
        "MyApp: Hang detected by RunningBoard: 487ms"
    )
    event = parse_log_line(line)
    assert event is not None
    assert event["process"] == "MyApp"
    assert event["pid"] == 1234
    assert event["duration_ms"] == 487


def test_parse_log_line_returns_none_for_non_hang():
    line = (
        "2026-05-22 14:30:52.123456-0800 0x1234 Default   0x0 1234 0 "
        "MyApp: just a regular log line"
    )
    assert parse_log_line(line) is None


def test_parse_log_line_returns_none_for_garbage():
    assert parse_log_line("") is None
    assert parse_log_line("not a log line at all") is None


def test_is_hang_message_matches_keywords():
    assert is_hang_message("Hang detected")
    assert is_hang_message("Main thread stall")
    assert is_hang_message("App unresponsive")
    assert is_hang_message("RunningBoard watchdog tripped")
    assert is_hang_message("jetsam killed it")
    assert not is_hang_message("everything is fine")


def test_extract_duration_ms_seconds():
    assert extract_duration_ms("Hang for 2.5s") == 2500.0
    assert extract_duration_ms("stalled 1.2 seconds") == 1200.0


def test_extract_duration_ms_milliseconds():
    assert extract_duration_ms("Hang for 487ms") == 487.0
    assert extract_duration_ms("250 milliseconds late") == 250.0


def test_extract_duration_ms_none():
    assert extract_duration_ms("no duration here") is None


# === normalise ===


def test_normalise_strips_boilerplate_and_redacts():
    msg = "Hang detected by RunningBoard: pid:1234 at 0xdeadbeef for 487ms"
    out = normalise_message(msg)
    assert "Hang detected by RunningBoard" not in out
    assert "0xdead" not in out
    assert "1234" not in out
    assert out.startswith("<pid>") or "<addr>" in out


def test_normalise_truncates():
    msg = "Hang " + "x" * 200
    out = normalise_message(msg, max_len=20)
    assert len(out) <= 20


def test_normalise_collapses_whitespace():
    out = normalise_message("Hang   detected\n\tat\tmain")
    assert "  " not in out
    assert "\n" not in out


def test_extract_symbol_objc():
    assert extract_symbol("crashed at [ImageDecoder decode:]") == "[ImageDecoder decode:]"


def test_extract_symbol_swift():
    sym = extract_symbol("Hang in MyClass.runWork() on main thread")
    assert sym is not None and "MyClass.runWork" in sym


def test_extract_symbol_none():
    assert extract_symbol("just text no symbols") is None


# === threshold ===


def test_above_threshold_filters_correctly():
    assert above_threshold(500.0, 250)
    assert above_threshold(250.0, 250)
    assert not above_threshold(100.0, 250)
    assert not above_threshold(None, 250)


# === severity ===


@pytest.mark.parametrize(
    "ms,expected",
    [
        (0, Severity.MINOR),
        (100, Severity.MINOR),
        (249, Severity.MINOR),
        (250, Severity.WARN),
        (400, Severity.WARN),
        (499, Severity.WARN),
        (500, Severity.CRITICAL),
        (1500, Severity.CRITICAL),
        (1999, Severity.CRITICAL),
        (2000, Severity.FROZEN),
        (5000, Severity.FROZEN),
    ],
)
def test_bucket_severity_boundaries(ms, expected):
    assert bucket_severity(ms) == expected


# === fingerprint ===


def test_compute_fingerprint_prefers_symbol():
    fp = compute_fingerprint("[ImageDecoder decode:]", "fallback prefix")
    assert fp.startswith("sym:")
    assert "ImageDecoder" in fp


def test_compute_fingerprint_falls_back_to_prefix():
    fp = compute_fingerprint(None, "fallback prefix")
    assert fp.startswith("msg:")
    assert "fallback prefix" in fp


# === build_normalised_event ===


def test_build_normalised_event_full():
    raw = {
        "timestamp": "2026-05-22 14:30:52.000000-0800",
        "pid": 1234,
        "process": "MyApp",
        "message": "Hang detected by RunningBoard: 487ms at [ImageDecoder decode:]",
        "duration_ms": 487.0,
    }
    event = build_normalised_event(raw, session_start_ms=0, current_ms=12_400)
    assert event is not None
    assert event.duration_ms == 487.0
    assert event.severity == Severity.WARN
    assert event.symbol == "[ImageDecoder decode:]"
    assert event.delta_ms == 12_400
    assert event.fingerprint.startswith("sym:")


def test_build_normalised_event_returns_none_without_duration():
    raw = {"timestamp": "", "pid": 0, "process": "X", "message": "Hang somewhere"}
    assert build_normalised_event(raw, session_start_ms=0) is None


# === cluster ===


def _event(fp_symbol: str, duration: float, delta: int = 1000, process: str = "MyApp") -> NormalisedEvent:
    return NormalisedEvent(
        delta_ms=delta,
        process=process,
        pid=1,
        duration_ms=duration,
        severity=bucket_severity(duration),
        symbol=fp_symbol,
        message_prefix="prefix",
        fingerprint=compute_fingerprint(fp_symbol, "prefix"),
    )


def test_cluster_groups_by_fingerprint():
    events = [
        _event("[A foo]", 300),
        _event("[A foo]", 500),
        _event("[B bar]", 100),
    ]
    clusters = cluster_events(events)
    assert len(clusters) == 2
    by_fp = {c.fingerprint: c for c in clusters}
    a_cluster = by_fp[compute_fingerprint("[A foo]", "prefix")]
    assert a_cluster.count == 2
    assert a_cluster.max_duration_ms == 500
    assert a_cluster.severity == Severity.CRITICAL


def test_cluster_picks_max_severity():
    events = [_event("[A foo]", 100), _event("[A foo]", 3000)]
    cluster = cluster_events(events)[0]
    assert cluster.severity == Severity.FROZEN


# === aggregators ===


def test_detect_temporal_bursts():
    events = [
        _event("[X]", 300, delta=100),
        _event("[X]", 300, delta=300),
        _event("[X]", 300, delta=800),
        _event("[X]", 300, delta=10_000),
    ]
    bursts = detect_temporal_bursts(events, window_ms=1000, min_count=3)
    assert len(bursts) == 1
    assert bursts[0]["count"] == 3


def test_detect_quiet_periods():
    events = [
        _event("[X]", 300, delta=0),
        _event("[X]", 300, delta=8000),
        _event("[X]", 300, delta=9000),
    ]
    quiet = detect_quiet_periods(events, threshold_ms=5000)
    assert len(quiet) == 1
    assert quiet[0]["gap_ms"] == 8000


def test_process_distribution():
    events = [
        _event("[X]", 300, process="A"),
        _event("[X]", 300, process="A"),
        _event("[X]", 300, process="B"),
    ]
    dist = process_distribution(events)
    assert dist == {"A": 2, "B": 1}


# === rank ===


def test_rank_orders_by_severity_then_duration():
    minor = _event("[m]", 100)
    critical = _event("[c]", 600)
    frozen = _event("[f]", 3000)
    clusters = cluster_events([minor, critical, frozen])
    ranked = rank_clusters(clusters)
    assert ranked[0].severity == Severity.FROZEN
    assert ranked[-1].severity == Severity.MINOR


def test_rank_top_n():
    events = [_event(f"[c{i}]", 500) for i in range(5)]
    clusters = cluster_events(events)
    assert len(rank_clusters(clusters, top_n=2)) == 2


# === formatters ===


def _build_summary(event_count: int = 10) -> SessionSummary:
    events = [_event(f"[c{i % 3}]", 400 + i * 10, delta=i * 1000) for i in range(event_count)]
    builder = SummaryBuilder(
        session_id="hang-20260522-143052-abcd",
        started_at="2026-05-22T14:30:52",
        duration_ms=30_000,
        matched_lines=event_count,
        total_lines=event_count * 10,
        dropped_below_threshold=2,
    )
    return builder.build(events)


def test_format_l0_one_line():
    summary = _build_summary()
    out = format_l0(summary)
    assert "\n" not in out
    assert summary.session_id in out


def test_format_l1_default_shape():
    summary = _build_summary()
    out = format_l1(summary)
    lines = out.split("\n")
    # 1 header + 3 clusters + 1 drill hint
    assert len(lines) == 5
    assert lines[-1].startswith("Drill:")


def test_format_l1_empty_session():
    builder = SummaryBuilder(
        session_id="hang-empty",
        started_at="2026-05-22T14:30:52",
        duration_ms=5000,
        matched_lines=0,
        total_lines=100,
    )
    summary = builder.build([])
    out = format_l1(summary)
    assert "no hangs" in out.lower()


def test_format_l2_includes_aggregates():
    summary = _build_summary(event_count=20)
    out = format_l2(summary)
    assert "Severity:" in out
    assert "Lines:" in out


def test_format_cluster_detail():
    summary = _build_summary()
    cluster = summary.clusters[0]
    events = [
        e
        for e in [
            _event(cluster.sample_event.symbol or "[c0]", cluster.max_duration_ms, delta=i * 100)
            for i in range(5)
        ]
    ]
    out = format_cluster_detail(cluster, events)
    assert "fingerprint=" in out
    assert "severity=" in out


# === token budget ===


def test_estimate_tokens_is_char_div_4():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 400) == 100


def test_compress_to_budget_picks_l1_at_default():
    summary = _build_summary()
    out = compress_to_budget(summary, max_tokens=None)
    assert "Drill:" in out


def test_compress_to_budget_falls_back_to_l0_at_tight_budget():
    summary = _build_summary(event_count=20)
    out = compress_to_budget(summary, max_tokens=10)
    assert "\n" not in out


def test_compress_to_budget_uses_l2_at_high_budget():
    summary = _build_summary(event_count=20)
    out = compress_to_budget(summary, max_tokens=2000)
    assert "Severity:" in out


# === diff ===


def test_diff_detects_new_critical():
    a = _build_summary(event_count=5)
    b_events = [
        _event(f"[c{i % 3}]", 400 + i * 10, delta=i * 1000) for i in range(5)
    ] + [_event("[new-critical]", 1500, delta=20_000)]
    b = SummaryBuilder(
        session_id="hang-b",
        started_at="2026-05-22T14:31:00",
        duration_ms=30_000,
    ).build(b_events)
    out = diff_sessions(a, b)
    assert not out["version_mismatch"]
    assert any("new-critical" in c["symbol_or_prefix"] for c in out["new_clusters"])
    assert "regression" in out["verdict"]


def test_diff_version_mismatch_skips_structural_compare():
    a = _build_summary()
    b = _build_summary()
    b.fingerprint_version = 99
    out = diff_sessions(a, b)
    assert out["version_mismatch"]
    assert "skipped" in out["verdict"]


def test_format_diff_renders_verdict():
    a = _build_summary()
    a.fingerprint_version = 1
    b = _build_summary()
    b.fingerprint_version = 99
    out = format_diff(diff_sessions(a, b))
    assert "version_mismatch" in out or "mismatch" in out.lower()


# === serialisation ===


def test_summary_roundtrip():
    summary = _build_summary()
    payload = summary_to_json(summary)
    # Must be JSON-serialisable
    encoded = json.dumps(payload)
    rebuilt = summary_from_json(json.loads(encoded))
    assert rebuilt.session_id == summary.session_id
    assert rebuilt.event_count == summary.event_count
    assert len(rebuilt.clusters) == len(summary.clusters)
    assert rebuilt.fingerprint_version == FINGERPRINT_VERSION


def test_event_jsonl_roundtrip():
    event = _event("[A foo]", 600, delta=12_400)
    line = event_to_jsonl(event)
    rebuilt = event_from_jsonl(line)
    assert rebuilt.fingerprint == event.fingerprint
    assert rebuilt.severity == Severity.CRITICAL


def test_cluster_to_json_handles_enum():
    summary = _build_summary()
    payload = summary_to_json(summary)
    for cluster in payload["clusters"]:
        # Must be a plain string, not an enum repr
        assert cluster["severity"] in {s.value for s in Severity}
