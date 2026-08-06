from app.api.routes.intelligence import geo_for_source


def test_geo_for_known_international_source() -> None:
    geo = geo_for_source("Reuters", "international")
    assert geo is not None
    assert geo.country == "英国"
    assert geo.lat != 0
    assert geo.lng != 0


def test_geo_skips_unknown_source_and_other_categories() -> None:
    assert geo_for_source("某中文源", "international") is None
    assert geo_for_source("Reuters", "ai") is None
    assert geo_for_source("Reuters", "technology") is None
