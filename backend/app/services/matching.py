"""Rule-based lost/found matching.

Scores are recommendations for people to review. Nothing here approves a claim or changes
ownership; confirming a match only marks both reports MATCHED.

Each signal yields a value in [0, 1] or None when it cannot be judged (e.g. a colour is missing).
The final score is the weighted mean over available signals, scaled to 0 to 100.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import Settings
from app.db.enums import ItemStatus, MatchStatus, NotificationType, ReportType
from app.db.models import Item, Match, Notification

MATCHABLE_STATUSES = (ItemStatus.OPEN, ItemStatus.MATCHED)
DATE_TOLERANCE = timedelta(days=1)
MAX_CANDIDATES = 500

STOPWORDS = frozenset(
    "a an and are at be by for from has have i in is it its left lost found my near of on or our "
    "the this that to was were with item thing someone".split()
)

# Shade -> colour family. Exact shade match scores 1.0, same family 0.6.
COLOR_FAMILIES = {
    "grey": "grey", "gray": "grey", "silver": "grey", "charcoal": "grey",
    "black": "black",
    "white": "white", "cream": "white", "ivory": "white", "beige": "brown",
    "brown": "brown", "tan": "brown",
    "red": "red", "maroon": "red", "burgundy": "red", "crimson": "red",
    "pink": "pink", "rose": "pink", "magenta": "pink",
    "orange": "orange",
    "yellow": "yellow", "gold": "yellow", "golden": "yellow",
    "green": "green", "olive": "green", "lime": "green", "teal": "green",
    "blue": "blue", "navy": "blue", "turquoise": "blue", "cyan": "blue",
    "purple": "purple", "violet": "purple", "lavender": "purple",
}
COLOR_ALIASES = {"gray": "grey", "golden": "gold"}


@dataclass(frozen=True)
class ReportFeatures:
    """The fields matching looks at, decoupled from the ORM so scoring is a pure function."""

    category_id: int
    category_name: str
    location_id: int
    location_name: str
    occurred_at: datetime
    text: str
    color: str | None

    @classmethod
    def from_item(cls, item: Item) -> "ReportFeatures":
        return cls(
            category_id=item.category_id,
            category_name=item.category.name,
            location_id=item.location_id,
            location_name=item.location.name,
            occurred_at=item.occurred_at,
            text=" ".join(filter(None, (item.title, item.description, item.brand))),
            color=item.color,
        )


@dataclass(frozen=True)
class Signal:
    name: str
    value: float | None
    detail: str


@dataclass(frozen=True)
class MatchResult:
    score: float
    reasons: list[dict[str, Any]]


def tokenize(text: str) -> list[str]:
    tokens = []
    for raw in re.findall(r"[a-z0-9]+", text.lower()):
        if len(raw) < 2 or raw in STOPWORDS:
            continue
        if len(raw) > 3 and raw.endswith("s") and not raw.endswith("ss"):
            raw = raw[:-1]
        tokens.append(raw)
    return tokens


def _category(lost: ReportFeatures, found: ReportFeatures) -> Signal:
    if lost.category_id == found.category_id:
        return Signal("category", 1.0, f"Both are in {lost.category_name}.")
    return Signal("category", 0.0, f"Different categories: {lost.category_name} and {found.category_name}.")


def _description(lost: ReportFeatures, found: ReportFeatures) -> Signal:
    a, b = Counter(tokenize(lost.text)), Counter(tokenize(found.text))
    if not a or not b:
        return Signal("description", None, "Not enough descriptive words to compare.")
    dot = sum(a[t] * b[t] for t in a.keys() & b.keys())
    cosine = dot / (math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values())))
    shared = sorted(a.keys() & b.keys())
    if not shared:
        return Signal("description", 0.0, "No words in common.")
    words = ", ".join(shared[:6]) + (" and more" if len(shared) > 6 else "")
    return Signal("description", round(cosine, 4), f"Shared words: {words}.")


def _normalise_color(color: str) -> list[str]:
    return [COLOR_ALIASES.get(t, t) for t in re.findall(r"[a-z]+", color.lower())]


def _color(lost: ReportFeatures, found: ReportFeatures) -> Signal:
    if not lost.color or not found.color:
        return Signal("color", None, "Colour missing on one report.")
    a, b = set(_normalise_color(lost.color)), set(_normalise_color(found.color))
    if a & b:
        return Signal("color", 1.0, f"Same colour: {found.color}.")
    families_a = {COLOR_FAMILIES[t] for t in a if t in COLOR_FAMILIES}
    families_b = {COLOR_FAMILIES[t] for t in b if t in COLOR_FAMILIES}
    if families_a & families_b:
        return Signal("color", 0.6, f"Similar colours: {lost.color} and {found.color}.")
    return Signal("color", 0.0, f"Different colours: {lost.color} and {found.color}.")


def _location(lost: ReportFeatures, found: ReportFeatures) -> Signal:
    if lost.location_id == found.location_id:
        return Signal("location", 1.0, f"Both at {lost.location_name}.")
    return Signal("location", 0.0, f"Different places: {lost.location_name} and {found.location_name}.")


def _date(lost: ReportFeatures, found: ReportFeatures, window_days: int) -> Signal:
    gap = found.occurred_at - lost.occurred_at
    days = gap.total_seconds() / 86400
    if gap < -DATE_TOLERANCE:
        return Signal("date", 0.0, "Found before it was reported lost.")
    if abs(days) <= 1:
        return Signal("date", 1.0, "Lost and found within a day of each other.")
    value = max(0.0, 1 - (days - 1) / (window_days - 1))
    whole_days = round(days)
    return Signal("date", round(value, 4), f"Found {whole_days} day{'s' if whole_days != 1 else ''} after it was lost.")


def score_pair(lost: ReportFeatures, found: ReportFeatures, settings: Settings) -> MatchResult:
    signals = [
        _category(lost, found),
        _description(lost, found),
        _color(lost, found),
        _location(lost, found),
        _date(lost, found, settings.match_date_window_days),
    ]
    weights = settings.match_weights
    available = sum(weights[s.name] for s in signals if s.value is not None)
    reasons: list[dict[str, Any]] = []
    total = 0.0
    for s in signals:
        weight = weights[s.name]
        points = (s.value * weight / available * 100) if s.value is not None and available else 0.0
        total += points
        reasons.append(
            {"signal": s.name, "weight": weight, "value": s.value, "points": round(points, 1), "detail": s.detail}
        )
    return MatchResult(score=round(min(100.0, total), 1), reasons=reasons)


def _candidates(db: Session, item: Item, window_days: int) -> list[Item]:
    """Opposite-type, still-matchable reports by other people inside the plausible date range."""
    window = timedelta(days=window_days)
    if item.report_type == ReportType.LOST:
        other_type, start, end = ReportType.FOUND, item.occurred_at - DATE_TOLERANCE, item.occurred_at + window
    else:
        other_type, start, end = ReportType.LOST, item.occurred_at - window, item.occurred_at + DATE_TOLERANCE
    stmt = (
        select(Item)
        .options(joinedload(Item.category), joinedload(Item.location))
        .where(
            Item.report_type == other_type,
            Item.status.in_(MATCHABLE_STATUSES),
            Item.reporter_id != item.reporter_id,
            Item.occurred_at.between(start, end),
        )
        .order_by(Item.created_at.desc())
        .limit(MAX_CANDIDATES)
    )
    return list(db.scalars(stmt))


def _notify_new_match(db: Session, lost: Item, found: Item) -> None:
    db.add(
        Notification(
            user_id=lost.reporter_id,
            type=NotificationType.MATCH_SUGGESTED,
            title="Possible match for your lost item",
            message=(
                f'A found report "{found.title}" may match your lost item "{lost.title}". '
                "Review the suggestion and submit a claim if it is yours."
            ),
            item_id=lost.id,
        )
    )


def refresh_matches(db: Session, item: Item, settings: Settings, actor_id: int | None) -> int:
    """Recompute suggestions for one report inside the caller's transaction. Returns new suggestions created.

    SUGGESTED rows are updated or removed when the score drops below the threshold; CONFIRMED and
    DISMISSED rows are human decisions and are never changed here.
    """
    db.flush()
    is_lost = item.report_type == ReportType.LOST
    existing = {
        (m.found_item_id if is_lost else m.lost_item_id): m
        for m in db.scalars(select(Match).where((Match.lost_item_id if is_lost else Match.found_item_id) == item.id))
    }

    if item.status not in MATCHABLE_STATUSES:
        for match in existing.values():
            if match.status == MatchStatus.SUGGESTED:
                db.delete(match)
        return 0

    features = ReportFeatures.from_item(item)
    seen: set[int] = set()
    created = 0
    for other in _candidates(db, item, settings.match_date_window_days):
        seen.add(other.id)
        other_features = ReportFeatures.from_item(other)
        if is_lost:
            lost, found, result = item, other, score_pair(features, other_features, settings)
        else:
            lost, found, result = other, item, score_pair(other_features, features, settings)
        match = existing.get(other.id)

        if match is not None:
            if match.status == MatchStatus.SUGGESTED:
                if result.score >= settings.match_threshold:
                    match.score, match.reasons = result.score, result.reasons
                else:
                    db.delete(match)
            continue
        if result.score >= settings.match_threshold:
            db.add(Match(lost_item_id=lost.id, found_item_id=found.id, score=result.score, reasons=result.reasons))
            if lost.reporter_id != actor_id:
                _notify_new_match(db, lost, found)
            created += 1

    # Suggestions whose counterpart dropped out of the candidate set (date edited, closed) are stale.
    for other_id, match in existing.items():
        if other_id not in seen and match.status == MatchStatus.SUGGESTED:
            db.delete(match)
    return created


def dismiss_suggestions_for(db: Session, item_id: int) -> None:
    """Called when a report closes: open suggestions involving it are dismissed, keeping history."""
    stmt = select(Match).where(
        Match.status == MatchStatus.SUGGESTED, or_(Match.lost_item_id == item_id, Match.found_item_id == item_id)
    )
    for match in db.scalars(stmt):
        match.status = MatchStatus.DISMISSED
