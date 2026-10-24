"""Pure scoring tests: positive and negative examples, missing attributes and configurable weights."""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import get_settings
from app.services.matching import ReportFeatures, score_pair, tokenize

BASE = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


def features(**overrides) -> ReportFeatures:
    fields = {
        "category_id": 1,
        "category_name": "Electronics",
        "location_id": 1,
        "location_name": "Main Library",
        "occurred_at": BASE,
        "text": "Black phone with a cracked blue case Pixel",
        "color": "Black",
    }
    return ReportFeatures(**(fields | overrides))


def reasons_by_signal(result) -> dict[str, dict]:
    return {r["signal"]: r for r in result.reasons}


@pytest.fixture
def settings():
    return get_settings()


def test_strong_positive_match(settings):
    lost = features()
    found = features(text="Found a black Pixel phone, cracked case", occurred_at=BASE + timedelta(hours=8))
    result = score_pair(lost, found, settings)
    assert result.score >= 90
    reasons = reasons_by_signal(result)
    assert set(reasons) == {"category", "description", "color", "location", "date"}
    assert reasons["category"]["points"] == 30 and reasons["location"]["points"] == 15
    assert "pixel" in reasons["description"]["detail"]
    assert abs(sum(r["points"] for r in result.reasons) - result.score) < 0.5


@pytest.mark.parametrize(
    "found_overrides",
    [
        # Everything different.
        {"category_id": 2, "category_name": "Keys", "location_id": 2, "location_name": "Dining Hall",
         "text": "Three silver keys on a red lanyard ring", "color": "Silver",
         "occurred_at": BASE + timedelta(days=9)},
        # Same place and day, but a different kind of object with no words in common.
        {"category_id": 3, "category_name": "Clothing", "text": "Wool scarf, knitted", "color": "Green"},
    ],
)
def test_negative_examples_stay_below_threshold(settings, found_overrides):
    result = score_pair(features(), features(**found_overrides), settings)
    assert result.score < settings.match_threshold


@pytest.mark.parametrize(("hours", "text"), [(30, "Found 1 day after"), (72, "Found 3 days after")])
def test_date_detail_wording(settings, hours, text):
    found = features(occurred_at=BASE + timedelta(hours=hours))
    assert reasons_by_signal(score_pair(features(), found, settings))["date"]["detail"].startswith(text)


def test_found_before_lost_scores_no_date_points(settings):
    result = score_pair(features(), features(occurred_at=BASE - timedelta(days=3)), settings)
    assert reasons_by_signal(result)["date"]["value"] == 0.0


@pytest.mark.parametrize(
    ("gap_days", "expected"),
    [(0, 1.0), (1, 1.0), (7.5, 0.5), (14, 0.0), (30, 0.0)],
)
def test_date_decay(settings, gap_days, expected):
    found = features(occurred_at=BASE + timedelta(days=gap_days))
    assert reasons_by_signal(score_pair(features(), found, settings))["date"]["value"] == expected


def test_missing_colour_is_excluded_not_penalised(settings):
    with_colour = score_pair(features(), features(), settings)
    without_colour = score_pair(features(), features(color=None), settings)
    colour = reasons_by_signal(without_colour)["color"]
    assert colour["value"] is None and colour["points"] == 0
    assert "missing" in colour["detail"].lower()
    assert with_colour.score == without_colour.score == 100.0  # renormalised over available signals


def test_unusable_description_is_excluded(settings):
    result = score_pair(features(text="the and of"), features(), settings)
    assert reasons_by_signal(result)["description"]["value"] is None


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [("Grey", "gray", 1.0), ("Navy", "blue", 0.6), ("dark blue", "Blue", 1.0), ("Red", "Green", 0.0)],
)
def test_colour_matching(settings, a, b, expected):
    result = score_pair(features(color=a), features(color=b), settings)
    assert reasons_by_signal(result)["color"]["value"] == expected


def test_weights_are_configurable(settings):
    category_only = settings.model_copy(update={
        "match_weight_category": 1, "match_weight_description": 0, "match_weight_color": 0,
        "match_weight_location": 0, "match_weight_date": 0,
    })
    different = features(location_id=9, location_name="Elsewhere", text="nothing alike", color="Red",
                         occurred_at=BASE + timedelta(days=13))
    assert score_pair(features(), different, category_only).score == 100.0
    assert score_pair(features(), different, settings).score < 50


def test_tokenize_drops_stopwords_and_plurals():
    assert tokenize("Lost my Keys and the glasses at the Library!") == ["key", "glasse", "library"]
    assert tokenize("a I x") == []
