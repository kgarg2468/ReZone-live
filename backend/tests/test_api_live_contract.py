from fastapi import FastAPI
from fastapi.testclient import TestClient
from shapely.geometry import Point, Polygon, mapping

from app.routes import api as api_routes


class FakeGeoDataService:
    def __init__(self):
        self.building_poly = Polygon([
            (-74.0098, 40.7095),
            (-74.0092, 40.7095),
            (-74.0092, 40.7100),
            (-74.0098, 40.7100),
            (-74.0098, 40.7095),
        ])
        self.building_feature = {
            "type": "Feature",
            "id": "1000010001",
            "properties": {
                "id": "1000010001",
                "name": "120 Broadway Office Property",
                "address": "120 Broadway",
                "city": "New York",
                "sqft": 180000,
                "floors": 18,
                "year_built": 1968,
                "vacancy_pct": 58,
                "current_use": "Commercial/Office",
                "structural_type": "steel-frame",
                "parking_spaces": 0,
                "has_elevator": True,
                "ceiling_height_ft": 12,
                "lat": 40.70975,
                "lng": -74.0095,
                "structural_type_is_proxy": True,
                "ceiling_height_is_proxy": True,
                "has_elevator_is_proxy": True,
            },
            "geometry": mapping(self.building_poly),
        }

    def layer_counts(self):
        return {
            "office_buildings": 1,
            "zoning_districts": 1,
            "utility_infrastructure": 4,
            "transit_stops": 2,
        }

    def get_all_buildings(self, bbox=None, limit=200, offset=0):
        return [self.building_feature["properties"]]

    def layer_names(self):
        return [
            "office_buildings",
            "zoning_districts",
            "utility_infrastructure",
            "transit_stops",
        ]

    def get_layer(self, name, bbox=None, limit=500, offset=0):
        if name == "office_buildings":
            return {"type": "FeatureCollection", "features": [self.building_feature]}
        if name == "zoning_districts":
            return {
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "properties": {
                        "id": "zone_1",
                        "name": "C6-4X",
                        "zone_type": "commercial",
                        "allows_residential": False,
                        "max_density": 12,
                        "max_height_ft": 420,
                    },
                    "geometry": mapping(Polygon([
                        (-74.015, 40.705),
                        (-74.000, 40.705),
                        (-74.000, 40.715),
                        (-74.015, 40.715),
                        (-74.015, 40.705),
                    ])),
                }],
            }
        return {"type": "FeatureCollection", "features": []}

    def get_building_by_id(self, building_id):
        if building_id != "1000010001":
            return None
        return self.building_feature, self.building_poly

    def nearest_building(self, point):
        return self.building_feature, self.building_poly, 0.05

    def find_containing_zone(self, point):
        zone = self.get_layer("zoning_districts")["features"][0]
        return zone, Polygon(zone["geometry"]["coordinates"][0])

    def features_within_radius(self, layer_name, center, radius_km):
        if layer_name == "utility_infrastructure":
            base = [
                ("water_main", "high", "good", 12, 0.1),
                ("sewer", "medium", "fair", 35, 0.25),
                ("electrical", "high", "good", 8, 0.08),
                ("gas", "low", "fair", 40, 0.35),
            ]
            rows = []
            for idx, (utype, cap, cond, age, dist) in enumerate(base):
                feat = {
                    "type": "Feature",
                    "properties": {
                        "id": f"util_{idx}",
                        "utility_type": utype,
                        "capacity": cap,
                        "condition": cond,
                        "age_years": age,
                        "source": "OpenStreetMap Overpass",
                        "is_proxy": True,
                    },
                    "geometry": mapping(Point(center.x + idx * 0.0001, center.y + idx * 0.0001)),
                }
                rows.append((feat, Point(center.x, center.y), dist))
            return rows

        if layer_name == "transit_stops":
            rows = []
            for idx, riders in enumerate([18000, 24000]):
                feat = {
                    "type": "Feature",
                    "properties": {
                        "id": f"tr_{idx}",
                        "station_name": f"Station {idx}",
                        "line_name": "A/C/E",
                        "transit_type": "subway",
                        "daily_ridership": riders,
                        "source": "Transitland",
                        "is_proxy": True,
                    },
                    "geometry": mapping(Point(center.x + idx * 0.0002, center.y + idx * 0.0002)),
                }
                rows.append((feat, Point(center.x, center.y), 0.12 + idx * 0.04))
            return rows
        return []


def test_buildings_endpoint_supports_bbox_limit_offset():
    fake_geo = FakeGeoDataService()
    app = FastAPI()
    api_routes.init(fake_geo)
    app.include_router(api_routes.router)
    client = TestClient(app)

    res = client.get("/api/buildings?bbox=-74.02,40.70,-73.99,40.72&limit=50&offset=0")
    assert res.status_code == 200
    payload = res.json()
    assert len(payload) == 1
    assert payload[0]["id"] == "1000010001"


def test_feasibility_endpoint_returns_data_confidence():
    fake_geo = FakeGeoDataService()
    app = FastAPI()
    api_routes.init(fake_geo)
    app.include_router(api_routes.router)
    client = TestClient(app)

    res = client.post(
        "/api/feasibility-check",
        json={"building_id": "1000010001", "radius_km": 1.0},
    )
    assert res.status_code == 200
    payload = res.json()
    assert "data_confidence" in payload
    assert payload["data_confidence"]["overall"] > 0
    assert payload["utilities"][0]["source"] == "OpenStreetMap Overpass"
    assert payload["transit"]["is_proxy"] is True

