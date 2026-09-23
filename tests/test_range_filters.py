"""Range lookups must reach CourtListener as one comma-separated param."""

from datetime import date

import httpx
import pytest

from courtlistener import CourtListener
from courtlistener.utils import flatten_filters


def _params(**filters):
    client = CourtListener(api_token="unused")
    return client.clusters.validate_filters(filters)


class TestRangeSerialization:
    def test_flatten_joins_range_values(self):
        flat = flatten_filters({"date_filed": {"range": ("a", "b")}})
        assert flat == {"date_filed__range": "a,b"}

    def test_dunder_range_is_one_param(self):
        params = _params(date_filed__range=["2020-01-01", "2020-12-31"])
        assert params["date_filed__range"] == "2020-01-01,2020-12-31"
        query = str(httpx.QueryParams(params))
        assert query == "date_filed__range=2020-01-01%2C2020-12-31"

    def test_nested_range_matches_dunder(self):
        params = _params(
            date_filed={"range": [date(2020, 1, 1), date(2020, 12, 31)]}
        )
        assert params["date_filed__range"] == "2020-01-01,2020-12-31"

    def test_other_lookups_are_untouched(self):
        params = _params(date_filed={"gte": "2020-01-01"})
        assert params["date_filed__gte"] == date(2020, 1, 1)


@pytest.mark.integration
def test_range_filter_is_applied(client):
    results = client.clusters.list(
        date_filed__range=["2020-01-01", "2020-01-31"],
        fields=["date_filed"],
    ).get_results()
    assert results
    for result in results:
        assert "2020-01-01" <= result["date_filed"] <= "2020-01-31"
