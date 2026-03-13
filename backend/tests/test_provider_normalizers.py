from app.services.providers.pluto import NYCPlutoProvider
from app.services.providers.zoning import NYCZoningProvider
from app.services.providers.utilities import OverpassUtilityProvider


def test_pluto_normalize_feature_extracts_core_fields():
    raw_feature = {
        "type": "Feature",
        "id": "sample-1",
        "properties": {
            "bbl": "1000010001",
            "address": "120 Broadway",
            "borough": "MN",
            "bldgarea": "180000",
            "numfloors": "18",
            "yearbuilt": "1968",
            "landuse": "05",
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-74.0110, 40.7060],
                [-74.0106, 40.7060],
                [-74.0106, 40.7064],
                [-74.0110, 40.7064],
                [-74.0110, 40.7060],
            ]],
        },
    }

    normalized = NYCPlutoProvider.normalize_feature(raw_feature)
    assert normalized is not None
    props = normalized["properties"]
    assert props["id"] == "1000010001"
    assert props["city"] == "New York"
    assert props["sqft"] == 180000
    assert props["floors"] == 18
    assert props["vacancy_is_proxy"] is True


def test_zoning_normalize_feature_infers_zone_type_and_density():
    raw_feature = {
        "type": "Feature",
        "properties": {
            "OBJECTID": 1123,
            "ZONEDIST": "MX-8",
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-74.01, 40.71],
                [-74.00, 40.71],
                [-74.00, 40.72],
                [-74.01, 40.72],
                [-74.01, 40.71],
            ]],
        },
    }

    normalized = NYCZoningProvider.normalize_feature(raw_feature, index=0)
    assert normalized is not None
    props = normalized["properties"]
    assert props["zone_type"] == "mixed-use"
    assert props["allows_residential"] is True
    assert props["max_density"] >= 6.0


def test_overpass_normalize_element_classifies_electrical():
    element = {
        "type": "way",
        "id": 778899,
        "center": {"lat": 40.75, "lon": -73.99},
        "tags": {
            "power": "line",
            "voltage": "138000",
        },
    }

    normalized = OverpassUtilityProvider.normalize_element(element)
    assert normalized is not None
    props = normalized["properties"]
    assert props["utility_type"] == "electrical"
    assert props["capacity"] == "high"
    assert props["is_proxy"] is True

