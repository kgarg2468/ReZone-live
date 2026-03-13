"use client";

import { useEffect, useMemo, useState } from "react";
import Map from "@/components/Map";
import TopBar from "@/components/TopBar";
import LayerPanel, { type LayerKey } from "@/components/LayerPanel";
import ProjectPanel from "@/components/ProjectPanel";
import FeasibilityPanel, { type LatestAnalysisSummary } from "@/components/FeasibilityPanel";
import {
  checkFeasibility,
  fetchBuildings,
  fetchLayers,
  type BuildingSummary,
  type FeasibilityResponse,
  type LayerInfo,
} from "@/lib/api";

const defaultVisibility: Record<LayerKey, boolean> = {
  office_buildings: true,
  zoning_districts: true,
  utility_infrastructure: true,
  transit_stops: true,
};

export default function Home() {
  const [layers, setLayers] = useState<Partial<Record<LayerKey, LayerInfo>>>({});
  const [buildings, setBuildings] = useState<BuildingSummary[]>([]);
  const [visibleLayers, setVisibleLayers] = useState<Record<LayerKey, boolean>>(defaultVisibility);
  const [selectedBuildingId, setSelectedBuildingId] = useState<string | null>(null);
  const [result, setResult] = useState<FeasibilityResponse | null>(null);
  const [latestAnalysis, setLatestAnalysis] = useState<LatestAnalysisSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [mapStyle, setMapStyle] = useState<"satellite" | "dark">("satellite");
  const [cityFilter, setCityFilter] = useState("All");
  const [error, setError] = useState<string | null>(null);

  const selectedBuilding = useMemo(
    () => buildings.find((building) => building.id === selectedBuildingId) ?? null,
    [buildings, selectedBuildingId]
  );

  useEffect(() => {
    let mounted = true;

    const loadInitialData = async () => {
      try {
        setLoading(true);
        setError(null);
        const [layerPayload, buildingPayload] = await Promise.all([fetchLayers(), fetchBuildings()]);

        if (!mounted) return;

        setLayers(layerPayload as Partial<Record<LayerKey, LayerInfo>>);
        setBuildings(buildingPayload);
      } catch (loadError) {
        if (!mounted) return;
        const message = loadError instanceof Error ? loadError.message : "Failed to load HomeX data";
        setError(message);
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    loadInitialData();

    return () => {
      mounted = false;
    };
  }, []);

  const handleToggleLayer = (layer: LayerKey) => {
    setVisibleLayers((current) => ({ ...current, [layer]: !current[layer] }));
  };

  const handleSelectBuilding = (buildingId: string) => {
    setSelectedBuildingId(buildingId);
    if (result?.building_id !== buildingId) {
      setResult(null);
    }
  };

  const handleAnalyze = async () => {
    if (!selectedBuildingId || analyzing) return;

    try {
      setAnalyzing(true);
      setError(null);
      const response = await checkFeasibility(selectedBuildingId);
      setResult(response);
      setLatestAnalysis({
        buildingName: response.building_name,
        address: response.address,
        tier: response.tier,
        score: response.score,
        analyzedAt: new Date().toLocaleString(),
      });
    } catch (analysisError) {
      const message = analysisError instanceof Error ? analysisError.message : "Analysis failed";
      setError(message);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleRemove = () => {
    if (selectedBuildingId && result?.building_id === selectedBuildingId) {
      setResult(null);
    }
    setSelectedBuildingId(null);
  };

  const handleNewAnalysis = () => {
    setSelectedBuildingId(null);
    setResult(null);
    setError(null);
    setVisibleLayers(defaultVisibility);
    setCityFilter("All");
    setLatestAnalysis(null);
  };

  return (
    <main>
      <TopBar
        mapStyle={mapStyle}
        onToggleMapStyle={() => setMapStyle((style) => (style === "satellite" ? "dark" : "satellite"))}
        onNewAnalysis={handleNewAnalysis}
      />

      <Map
        key={mapStyle}
        mapStyle={mapStyle}
        layers={layers}
        visibleLayers={visibleLayers}
        buildings={buildings}
        selectedBuildingId={selectedBuildingId}
        onSelectBuilding={handleSelectBuilding}
      />

      <aside className="panel panel-left panel-left-stack animate-slide-left">
        <LayerPanel layers={layers} visibleLayers={visibleLayers} onToggleLayer={handleToggleLayer} />
        <div className="panel-body">
          <ProjectPanel
            buildings={buildings}
            selectedBuildingId={selectedBuildingId}
            onSelectBuilding={handleSelectBuilding}
            onAnalyze={handleAnalyze}
            onRemove={handleRemove}
            analyzing={analyzing}
            cityFilter={cityFilter}
            onCityFilterChange={setCityFilter}
          />
        </div>
      </aside>

      <FeasibilityPanel
        result={result}
        selectedBuildingName={selectedBuilding?.name ?? null}
        analyzing={analyzing}
        latestAnalysis={latestAnalysis}
      />

      {loading ? (
        <div className="loading-overlay">
          <div className="loading-spinner" />
          <div className="loading-text">Loading HomeX spatial layers...</div>
        </div>
      ) : null}

      {error ? (
        <div className="error-toast" role="alert">
          {error}
        </div>
      ) : null}
    </main>
  );
}
