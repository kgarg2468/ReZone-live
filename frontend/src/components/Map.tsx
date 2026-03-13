"use client";

import { useCallback, useEffect, useRef } from "react";
import mapboxgl from "mapbox-gl";
import type { BBox, BuildingSummary, LayerInfo } from "@/lib/api";
import type { LayerKey } from "@/components/LayerPanel";

type MapStyle = "satellite" | "dark";

interface MapProps {
  mapStyle: MapStyle;
  layers: Partial<Record<LayerKey, LayerInfo>>;
  visibleLayers: Record<LayerKey, boolean>;
  buildings: BuildingSummary[];
  selectedBuildingId: string | null;
  onSelectBuilding: (buildingId: string) => void;
  onViewportChange?: (bbox: BBox) => void;
}

const MAP_STYLE_URLS: Record<MapStyle, string> = {
  satellite: "mapbox://styles/mapbox/satellite-streets-v12",
  dark: "mapbox://styles/mapbox/dark-v11",
};

const LAYER_GROUPS: Record<LayerKey, string[]> = {
  office_buildings: ["office-buildings-fill", "office-buildings-outline", "office-buildings-selected"],
  zoning_districts: ["zoning-fill", "zoning-outline"],
  utility_infrastructure: ["utility-lines", "utility-points"],
  transit_stops: ["transit-points"],
};

function addOrUpdateSource(map: mapboxgl.Map, sourceId: string, data: GeoJSON.FeatureCollection): void {
  const existing = map.getSource(sourceId) as mapboxgl.GeoJSONSource | undefined;
  if (existing) {
    existing.setData(data);
    return;
  }

  map.addSource(sourceId, {
    type: "geojson",
    data,
  });
}

function ensureLayer(map: mapboxgl.Map, layer: mapboxgl.LayerSpecification): void {
  if (!map.getLayer(layer.id)) {
    map.addLayer(layer);
  }
}

export default function Map({
  mapStyle,
  layers,
  visibleLayers,
  buildings,
  selectedBuildingId,
  onSelectBuilding,
  onViewportChange,
}: MapProps) {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);

  const token = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;

  const emitBounds = useCallback(
    (map: mapboxgl.Map) => {
      if (!onViewportChange) return;
      const bounds = map.getBounds();
      if (!bounds) return;
      onViewportChange([
        bounds.getWest(),
        bounds.getSouth(),
        bounds.getEast(),
        bounds.getNorth(),
      ]);
    },
    [onViewportChange]
  );

  const syncMapLayers = useCallback(
    (map: mapboxgl.Map) => {
      const office = layers.office_buildings?.geojson;
      const zoning = layers.zoning_districts?.geojson;
      const utility = layers.utility_infrastructure?.geojson;
      const transit = layers.transit_stops?.geojson;

      if (office) {
        addOrUpdateSource(map, "office-buildings-source", office);

        ensureLayer(map, {
          id: "office-buildings-fill",
          type: "fill",
          source: "office-buildings-source",
          paint: {
            "fill-color": [
              "interpolate",
              ["linear"],
              ["get", "vacancy_pct"],
              0,
              "#ef4444",
              40,
              "#f59e0b",
              70,
              "#22c55e",
              100,
              "#16a34a",
            ],
            "fill-opacity": 0.46,
          },
        });

        ensureLayer(map, {
          id: "office-buildings-outline",
          type: "line",
          source: "office-buildings-source",
          paint: {
            "line-color": "#f8fafc",
            "line-opacity": 0.7,
            "line-width": 1,
          },
        });

        ensureLayer(map, {
          id: "office-buildings-selected",
          type: "line",
          source: "office-buildings-source",
          paint: {
            "line-color": "#f59e0b",
            "line-width": 3,
          },
          filter: ["==", ["get", "id"], ""],
        });
      }

      if (zoning) {
        addOrUpdateSource(map, "zoning-source", zoning);

        ensureLayer(map, {
          id: "zoning-fill",
          type: "fill",
          source: "zoning-source",
          paint: {
            "fill-color": [
              "match",
              ["get", "zone_type"],
              "mixed-use",
              "#3b82f6",
              "residential",
              "#22c55e",
              "commercial",
              "#8b5cf6",
              "industrial",
              "#ef4444",
              "#94a3b8",
            ],
            "fill-opacity": 0.12,
          },
        });

        ensureLayer(map, {
          id: "zoning-outline",
          type: "line",
          source: "zoning-source",
          paint: {
            "line-color": "#3b82f6",
            "line-width": 1,
            "line-opacity": 0.45,
          },
        });
      }

      if (utility) {
        addOrUpdateSource(map, "utility-source", utility);

        ensureLayer(map, {
          id: "utility-lines",
          type: "line",
          source: "utility-source",
          filter: ["==", ["geometry-type"], "LineString"],
          paint: {
            "line-color": [
              "match",
              ["get", "utility_type"],
              "water_main",
              "#06b6d4",
              "sewer",
              "#84cc16",
              "electrical",
              "#f59e0b",
              "gas",
              "#fb7185",
              "#a1a1aa",
            ],
            "line-width": 2,
            "line-opacity": 0.75,
          },
        });

        ensureLayer(map, {
          id: "utility-points",
          type: "circle",
          source: "utility-source",
          filter: ["==", ["geometry-type"], "Point"],
          paint: {
            "circle-color": "#f59e0b",
            "circle-radius": 5,
            "circle-stroke-color": "#0b1221",
            "circle-stroke-width": 1,
          },
        });
      }

      if (transit) {
        addOrUpdateSource(map, "transit-source", transit);

        ensureLayer(map, {
          id: "transit-points",
          type: "circle",
          source: "transit-source",
          paint: {
            "circle-color": "#f97316",
            "circle-radius": [
              "interpolate",
              ["linear"],
              ["get", "daily_ridership"],
              0,
              3,
              20000,
              6,
              90000,
              10,
            ],
            "circle-opacity": 0.85,
            "circle-stroke-color": "#fff7ed",
            "circle-stroke-width": 1,
          },
        });
      }

      if (map.getLayer("office-buildings-selected")) {
        map.setFilter("office-buildings-selected", [
          "==",
          ["get", "id"],
          selectedBuildingId ?? "",
        ]);
      }
    },
    [layers, selectedBuildingId]
  );

  const syncLayerVisibility = useCallback(
    (map: mapboxgl.Map) => {
      (Object.keys(LAYER_GROUPS) as LayerKey[]).forEach((layerName) => {
        const visibility = visibleLayers[layerName] ? "visible" : "none";
        LAYER_GROUPS[layerName].forEach((mapLayerId) => {
          if (!map.getLayer(mapLayerId)) return;
          map.setLayoutProperty(mapLayerId, "visibility", visibility);
        });
      });
    },
    [visibleLayers]
  );

  useEffect(() => {
    if (!mapContainerRef.current || !token) {
      return;
    }

    mapboxgl.accessToken = token;

    const map = new mapboxgl.Map({
      container: mapContainerRef.current,
      style: MAP_STYLE_URLS[mapStyle],
      center: [-74.006, 40.7128],
      zoom: 11,
      pitch: 42,
      bearing: -18,
      antialias: true,
    });

    mapRef.current = map;
    map.addControl(new mapboxgl.NavigationControl({ showCompass: true, showZoom: true }), "bottom-right");

    map.on("load", () => {
      syncMapLayers(map);
      syncLayerVisibility(map);
      emitBounds(map);

      map.on("click", "office-buildings-fill", (event) => {
        const feature = event.features?.[0];
        const buildingId = feature?.properties?.id;
        const buildingName = feature?.properties?.name;
        const sqft = feature?.properties?.sqft;
        const vacancy = feature?.properties?.vacancy_pct;

        if (!buildingId || typeof buildingId !== "string") return;

        onSelectBuilding(buildingId);

        new mapboxgl.Popup({ closeButton: true, closeOnClick: true })
          .setLngLat(event.lngLat)
          .setHTML(
            `<strong>${buildingName ?? "Office Building"}</strong><br/>`
              + `${sqft ? Number(sqft).toLocaleString() : "-"} sqft<br/>`
              + `Vacancy: ${vacancy ?? "-"}%`
          )
          .addTo(map);
      });

      map.on("mouseenter", "office-buildings-fill", () => {
        map.getCanvas().style.cursor = "pointer";
      });

      map.on("mouseleave", "office-buildings-fill", () => {
        map.getCanvas().style.cursor = "";
      });
    });

    map.on("moveend", () => {
      emitBounds(map);
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [emitBounds, mapStyle, onSelectBuilding, syncLayerVisibility, syncMapLayers, token]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    syncMapLayers(map);
  }, [syncMapLayers]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    syncLayerVisibility(map);
  }, [syncLayerVisibility]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selectedBuildingId) return;

    const selected = buildings.find((building) => building.id === selectedBuildingId);
    if (!selected) return;

    map.flyTo({
      center: [selected.lng, selected.lat],
      zoom: 15,
      pitch: 52,
      bearing: -20,
      duration: 1200,
      essential: true,
    });
  }, [buildings, selectedBuildingId]);

  if (!token) {
    return (
      <div className="map-container">
        <div className="loading-overlay">
          <div className="loading-text">Set NEXT_PUBLIC_MAPBOX_TOKEN to render the map.</div>
        </div>
      </div>
    );
  }

  return <div className="map-container" ref={mapContainerRef} />;
}
