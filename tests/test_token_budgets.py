"""Contract: --stop output ≤ 200 tokens, --get-details ≤ 2000 tokens (char/4)."""

from __future__ import annotations

from common.hang_pipeline import (
    compress_to_budget,
    estimate_tokens,
    format_cluster_detail,
    format_l0,
    format_l1,
    format_l2,
)
from tests.fixtures.sample_session import (
    assert_token_budget,
    make_events,
    make_summary,
)


def test_l0_is_one_line_under_30_tokens():
    summary = make_summary()
    out = format_l0(summary)
    assert "\n" not in out
    assert_token_budget(out, 30)


def test_l1_default_under_200_tokens():
    """Issue #77 contract: default --stop output ≤ 200 tokens on 30s/50-event session."""
    summary = make_summary()
    out = format_l1(summary)
    assert_token_budget(out, 200)


def test_l2_full_under_2000_tokens():
    """Issue #77 contract: --get-details (without --cluster) ≤ 2000 tokens."""
    summary = make_summary()
    out = format_l2(summary)
    assert_token_budget(out, 2000)


def test_l3_cluster_detail_under_2000_tokens():
    summary = make_summary()
    cluster = summary.clusters[0]
    events = [e for e in make_events() if e.fingerprint == cluster.fingerprint]
    out = format_cluster_detail(cluster, events)
    assert_token_budget(out, 2000)


def test_compress_to_budget_honours_tight_limits():
    summary = make_summary()
    # Tight budget should fall back to L0 (~20 tokens).
    out = compress_to_budget(summary, max_tokens=30)
    assert estimate_tokens(out) <= 30
    assert "\n" not in out


def test_compress_to_budget_uses_l1_at_default_window():
    summary = make_summary()
    out = compress_to_budget(summary, max_tokens=150)
    assert estimate_tokens(out) <= 150


def test_compress_to_budget_uses_l2_when_room():
    summary = make_summary()
    out = compress_to_budget(summary, max_tokens=1500)
    assert estimate_tokens(out) <= 1500
    # L2 reports a "Severity:" histogram line; L1 does not.
    assert "Severity:" in out


def test_compress_with_no_budget_returns_l1():
    summary = make_summary()
    out = compress_to_budget(summary, max_tokens=None)
    assert "Drill:" in out
