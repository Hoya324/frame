from crawler.masters.models import MasterSeed
from crawler.masters.roster import ROSTER


def test_roster_nonempty_and_well_formed():
    assert len(ROSTER) >= 8
    ids = [m.id for m in ROSTER]
    assert len(ids) == len(set(ids)), "master ids must be unique"
    for m in ROSTER:
        assert isinstance(m, MasterSeed)
        assert m.region in {"kr", "jp", "foreign"}
        assert m.sources, f"{m.id} has no sources"
        for sq in m.sources:
            assert sq.source in {"the_met", "aic"}
            assert bool(sq.query) ^ bool(sq.object_ids), "exactly one of query/object_ids"


def test_roster_covers_all_three_regions():
    regions = {m.region for m in ROSTER}
    assert {"kr", "jp", "foreign"} <= regions
