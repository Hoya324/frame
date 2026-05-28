from datetime import date

import pytest

from crawler.models import Status
from crawler.normalize.status import compute_status


@pytest.mark.parametrize(
    "today, start, end, expected",
    [
        (date(2026, 5, 28), date(2026, 6, 1), date(2026, 7, 1), Status.UPCOMING),
        (date(2026, 6, 15), date(2026, 6, 1), date(2026, 7, 1), Status.ONGOING),
        (date(2026, 7, 2), date(2026, 6, 1), date(2026, 7, 1), Status.PAST),
        (date(2026, 6, 1), date(2026, 6, 1), date(2026, 7, 1), Status.ONGOING),  # boundary
        (date(2026, 7, 1), date(2026, 6, 1), date(2026, 7, 1), Status.ONGOING),  # boundary
        (date(2026, 5, 28), None, None, Status.UNKNOWN),
        (date(2026, 5, 28), date(2026, 6, 1), None, Status.UPCOMING),
        (date(2026, 5, 28), None, date(2026, 7, 1), Status.UNKNOWN),
    ],
)
def test_compute_status(today, start, end, expected):
    assert compute_status(today, start, end) is expected
