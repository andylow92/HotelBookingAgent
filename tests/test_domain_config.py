"""Tests for domain configuration and Weights.normalized() edge cases."""

import pytest

from travelneg.shared.domain_config import DomainConfig, DOMAINS, get_domain
from travelneg.shared.models import Weights


# --- get_domain valid lookups ---

@pytest.mark.parametrize("name", list(DOMAINS))
def test_get_domain_returns_config_for_each_known_domain(name):
    cfg = get_domain(name)
    assert isinstance(cfg, DomainConfig)
    assert cfg.name == name


def test_get_domain_case_insensitive():
    assert get_domain("Hotels") == get_domain("hotels")
    assert get_domain("  RESTAURANTS  ") == get_domain("restaurants")


# --- get_domain invalid lookups ---

def test_get_domain_unknown_raises():
    with pytest.raises(ValueError, match="Unknown domain"):
        get_domain("flights")


def test_get_domain_empty_string_raises():
    with pytest.raises(ValueError, match="Unknown domain"):
        get_domain("")


# --- Domain configs have sensible defaults ---

@pytest.mark.parametrize("name", list(DOMAINS))
def test_domain_has_positive_max_values(name):
    cfg = get_domain(name)
    assert cfg.max_distance_km > 0
    assert cfg.max_budget_default > 0


@pytest.mark.parametrize("name", list(DOMAINS))
def test_domain_has_non_empty_labels(name):
    cfg = get_domain(name)
    assert cfg.price_label
    assert cfg.location_label
    assert cfg.rating_label
    assert cfg.flexibility_label
    assert cfg.match_label


@pytest.mark.parametrize("name", list(DOMAINS))
def test_domain_has_common_features(name):
    cfg = get_domain(name)
    assert len(cfg.common_features) >= 3


# --- Weights.normalized() ---

def test_normalized_sums_to_one():
    w = Weights(price=3, location=1, rating=1, flexibility=1, match=1)
    n = w.normalized()
    total = n.price + n.location + n.rating + n.flexibility + n.match
    assert total == pytest.approx(1.0)


def test_normalized_already_summing_to_one():
    w = Weights()  # defaults sum to 1.0
    n = w.normalized()
    assert n.price == pytest.approx(w.price)
    assert n.location == pytest.approx(w.location)
    assert n.rating == pytest.approx(w.rating)


def test_normalized_all_zeros_returns_defaults():
    w = Weights(price=0, location=0, rating=0, flexibility=0, match=0)
    n = w.normalized()
    # Falls back to default weights
    assert n == Weights()


def test_normalized_preserves_proportions():
    w = Weights(price=2, location=1, rating=1, flexibility=1, match=1)
    n = w.normalized()
    # price should be twice as large as location
    assert n.price == pytest.approx(2 * n.location)
