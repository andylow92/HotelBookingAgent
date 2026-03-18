"""Tests for the generic scoring engine."""

import pytest

from travelneg.provider_agent.scorer import (
    score_option,
    rank_and_tag,
    generate_negotiation_note,
    compute_distance,
)
from travelneg.shared.domain_config import get_domain
from travelneg.shared.models import Coords, Weights


HOTEL_DOMAIN = get_domain("hotels")
RESTAURANT_DOMAIN = get_domain("restaurants")


def _make_option(**overrides):
    defaults = dict(
        option_id="opt_1",
        name="Test Option",
        price=89,
        rating=4.3,
        distance_km=0.3,
        flexibility="free",
        matched_features=["wifi", "breakfast"],
        desired_features=["wifi", "breakfast", "pool"],
        weights=Weights(),
        max_budget=150,
        domain=HOTEL_DOMAIN,
    )
    defaults.update(overrides)
    return score_option(**defaults)


# --- Basic scoring ---

def test_score_is_between_0_and_1():
    opt = _make_option()
    assert 0 <= opt.total_score <= 1


def test_perfect_score():
    """An option that maxes out every dimension should score ~1.0."""
    opt = _make_option(
        price=0,
        rating=5.0,
        distance_km=0.0,
        flexibility="free",
        matched_features=["wifi", "breakfast", "pool"],
        desired_features=["wifi", "breakfast", "pool"],
    )
    assert opt.total_score == pytest.approx(1.0, abs=0.01)


def test_worst_score():
    """An option that bottoms out every dimension should score ~0.0."""
    opt = _make_option(
        price=150,
        rating=0.0,
        distance_km=5.0,
        flexibility="none",
        matched_features=[],
        desired_features=["wifi"],
    )
    assert opt.total_score == pytest.approx(0.0, abs=0.01)


# --- Weight changes affect ranking ---

def test_price_weight_boost_changes_ranking():
    cheap = _make_option(option_id="cheap", name="Cheap", price=50, rating=3.0)
    fancy = _make_option(option_id="fancy", name="Fancy", price=140, rating=4.9)

    # Default weights: price=0.25 → fancy might win on rating
    # Heavy price weights: price=0.55 → cheap should win
    cheap_heavy = _make_option(
        option_id="cheap", name="Cheap", price=50, rating=3.0,
        weights=Weights(price=0.55, location=0.10, rating=0.15, flexibility=0.10, match=0.10),
    )
    fancy_heavy = _make_option(
        option_id="fancy", name="Fancy", price=140, rating=4.9,
        weights=Weights(price=0.55, location=0.10, rating=0.15, flexibility=0.10, match=0.10),
    )
    assert cheap_heavy.total_score > fancy_heavy.total_score


def test_rating_weight_boost_changes_ranking():
    cheap = _make_option(
        option_id="cheap", name="Cheap", price=50, rating=3.0,
        weights=Weights(price=0.10, location=0.10, rating=0.55, flexibility=0.10, match=0.15),
    )
    fancy = _make_option(
        option_id="fancy", name="Fancy", price=140, rating=4.9,
        weights=Weights(price=0.10, location=0.10, rating=0.55, flexibility=0.10, match=0.15),
    )
    assert fancy.total_score > cheap.total_score


# --- Flexibility ---

def test_flexibility_values():
    free = _make_option(flexibility="free")
    partial = _make_option(flexibility="partial")
    none = _make_option(flexibility="none")
    assert free.score_breakdown.flexibility == 1.0
    assert partial.score_breakdown.flexibility == 0.3
    assert none.score_breakdown.flexibility == 0.0


# --- Match scoring ---

def test_match_all_desired():
    opt = _make_option(
        matched_features=["wifi", "breakfast", "pool"],
        desired_features=["wifi", "breakfast", "pool"],
    )
    assert opt.score_breakdown.match == 1.0


def test_match_none_desired():
    opt = _make_option(matched_features=[], desired_features=["wifi", "pool"])
    assert opt.score_breakdown.match == 0.0


def test_match_no_preferences():
    """If user desires nothing, match should be perfect."""
    opt = _make_option(matched_features=["wifi"], desired_features=[])
    assert opt.score_breakdown.match == 1.0


# --- Rank and tag ---

def test_rank_and_tag_top_3():
    options = [
        _make_option(option_id=f"opt_{i}", name=f"Option {i}", price=50 + i * 30, rating=3.0 + i * 0.5)
        for i in range(5)
    ]
    ranked = rank_and_tag(options, top_n=3)
    assert len(ranked) == 3
    assert ranked[0].total_score >= ranked[1].total_score >= ranked[2].total_score


def test_rank_tags_assigned():
    options = [
        _make_option(option_id="cheap", name="Cheap", price=40, rating=3.0),
        _make_option(option_id="mid", name="Mid", price=90, rating=4.2),
        _make_option(option_id="fancy", name="Fancy", price=145, rating=4.9),
    ]
    ranked = rank_and_tag(options)
    tags = [o.tag for o in ranked]
    assert "CHEAPEST" in tags
    assert "HIGHEST_RATED" in tags


# --- Negotiation note ---

def test_negotiation_note_not_empty():
    options = [_make_option(option_id="a", name="Hotel A")]
    ranked = rank_and_tag(options)
    note = generate_negotiation_note(ranked, max_budget=150)
    assert len(note) > 20
    assert "Hotel A" in note


def test_negotiation_note_empty_list():
    note = generate_negotiation_note([], max_budget=150)
    assert "No options" in note


# --- Distance computation ---

def test_compute_distance_real():
    a = Coords(lat=52.5219, lon=13.4132)
    b = Coords(lat=52.5251, lon=13.3694)
    dist = compute_distance(a, b)
    assert dist is not None
    assert dist > 0


def test_compute_distance_none_when_missing():
    assert compute_distance(None, Coords(lat=0, lon=0)) is None
    assert compute_distance(Coords(lat=0, lon=0), None) is None


# --- Domain agnostic ---

def test_works_with_restaurant_domain():
    opt = score_option(
        option_id="rest_1",
        name="La Tapería",
        price=25,
        rating=4.7,
        distance_km=0.8,
        flexibility="partial",
        matched_features=["vegan", "terrace"],
        desired_features=["vegan", "outdoor"],
        weights=Weights(),
        max_budget=50,
        domain=RESTAURANT_DOMAIN,
    )
    assert 0 <= opt.total_score <= 1
    assert opt.score_breakdown.price == pytest.approx(0.5, abs=0.01)


def test_weights_normalize():
    """Weights that don't sum to 1.0 should still produce valid scores."""
    opt = _make_option(weights=Weights(price=5, location=5, rating=5, flexibility=5, match=5))
    assert 0 <= opt.total_score <= 1
