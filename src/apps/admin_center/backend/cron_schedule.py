from __future__ import annotations

from datetime import datetime, timedelta, timezone


FIELD_RANGES = (
    (0, 59),
    (0, 23),
    (1, 31),
    (1, 12),
    (0, 7),
)


def _parse_field(value: str, minimum: int, maximum: int) -> set[int]:
    result: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            raise ValueError("empty cron field")
        base, separator, step_text = part.partition("/")
        step = int(step_text) if separator else 1
        if step <= 0:
            raise ValueError("cron step must be positive")
        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            start_text, end_text = base.split("-", 1)
            start, end = int(start_text), int(end_text)
        else:
            start = end = int(base)
        if start < minimum or end > maximum or start > end:
            raise ValueError(f"cron value must be between {minimum} and {maximum}")
        result.update(range(start, end + 1, step))
    return result


def parse_cron(expression: str) -> tuple[set[int], set[int], set[int], set[int], set[int]]:
    fields = str(expression or "").split()
    if len(fields) != 5:
        raise ValueError("cron expression must contain 5 fields")
    parsed = tuple(
        _parse_field(field, minimum, maximum)
        for field, (minimum, maximum) in zip(fields, FIELD_RANGES)
    )
    if 7 in parsed[4]:
        parsed[4].discard(7)
        parsed[4].add(0)
    return parsed  # type: ignore[return-value]


def cron_matches(expression: str, value: datetime) -> bool:
    minute, hour, day, month, weekday = parse_cron(expression)
    value = value.astimezone(timezone.utc)
    cron_weekday = (value.weekday() + 1) % 7
    day_matches = value.day in day
    weekday_matches = cron_weekday in weekday
    day_wildcard = str(expression).split()[2] == "*"
    weekday_wildcard = str(expression).split()[4] == "*"
    if not day_wildcard and not weekday_wildcard:
        calendar_matches = day_matches or weekday_matches
    else:
        calendar_matches = day_matches and weekday_matches
    return (
        value.minute in minute
        and value.hour in hour
        and value.month in month
        and calendar_matches
    )


def cron_is_due(expression: str, last_run_at: datetime | None, now: datetime) -> bool:
    parse_cron(expression)
    now = now.astimezone(timezone.utc).replace(second=0, microsecond=0)
    if last_run_at is None:
        return cron_matches(expression, now)
    cursor = last_run_at.astimezone(timezone.utc).replace(second=0, microsecond=0) + timedelta(minutes=1)
    if cursor > now:
        return False
    oldest_relevant = now - timedelta(days=366)
    if cursor < oldest_relevant:
        cursor = oldest_relevant
    while cursor <= now:
        if cron_matches(expression, cursor):
            return True
        cursor += timedelta(minutes=1)
    return False
