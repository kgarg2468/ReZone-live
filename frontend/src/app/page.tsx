"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Map from "@/components/Map";
import TopBar from "@/components/TopBar";
import LayerPanel, { type LayerKey } from "@/components/LayerPanel";
import ProjectPanel from "@/components/ProjectPanel";
import FeasibilityPanel, { type LatestAnalysisSummary } from "@/components/FeasibilityPanel";
import {
  type BBox,
  checkFeasibility,
  fetchAllBuildings,
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

const DEFAULT_BBOX: BBox = [-74.03, 40.7, -73.93, 40.89];
const DEFAULT_LAYERS: LayerKey[] = [
  "office_buildings",
  "zoning_districts",
  "utility_infrastructure",
  "transit_stops",
];

export default function Home() {
  const [layers, setLayers] = useState<Partial<Record<LayerKey, LayerInfo>>>({});
  const [buildings, setBuildings] = useState<BuildingSummary[]>([]);
  const [visibleLayers, setVisibleLayers] = useState<Record<LayerKey, boolean>>(defaultVisibility);
  const [selectedBuildingId, setSelectedBuildingId] = useState<string | null>(null);
  const [result, setResult] = useState<FeasibilityResponse | null>(null);
  const [latestAnalysis, setLatestAnalysis] = useState<LatestAnalysisSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const analyzingRef = useRef(false);
  const [mapStyle, setMapStyle] = useState<"satellite" | "dark">("satellite");
  const [cityFilter, setCityFilter] = useState("All");
  const [minVacancyFilter, setMinVacancyFilter] = useState(0);
  const [projectPanelCollapsed, setProjectPanelCollapsed] = useState(false);
  const [feasibilityPanelCollapsed, setFeasibilityPanelCollapsed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [viewportBbox, setViewportBbox] = useState<BBox>(DEFAULT_BBOX);
  const [queryBbox, setQueryBbox] = useState<BBox>(DEFAULT_BBOX);

  const selectedBuilding = useMemo(
    () => buildings.find((building) => building.id === selectedBuildingId) ?? null,
    [buildings, selectedBuildingId]
  );

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setQueryBbox(viewportBbox);
    }, 450);
    return () => window.clearTimeout(timeout);
  }, [viewportBbox]);

  useEffect(() => {
    let mounted = true;

    const loadDataForViewport = async () => {
      try {
        setLoading(true);
        setError(null);
        const [layerPayload, buildingPayload] = await Promise.all([
          fetchLayers({ bbox: queryBbox, layers: DEFAULT_LAYERS }),
          fetchAllBuildings({ bbox: queryBbox }),
        ]);

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

    loadDataForViewport();

    return () => {
      mounted = false;
    };
  }, [queryBbox]);

  useEffect(() => {
    if (!selectedBuildingId) return;
    const stillVisible = buildings.some((building) => building.id === selectedBuildingId);
    if (!stillVisible) {
      setSelectedBuildingId(null);
      setResult(null);
    }
  }, [buildings, selectedBuildingId]);

  const handleToggleLayer = (layer: LayerKey) => {
    setVisibleLayers((current) => ({ ...current, [layer]: !current[layer] }));
  };

  const handleSelectBuilding = (buildingId: string) => {
    setSelectedBuildingId(buildingId);
    if (result?.building_id !== buildingId) {
      setResult(null);
    }
  };

  const runAnalysis = async (buildingId: string) => {
    if (analyzingRef.current) return;

    try {
      analyzingRef.current = true;
      setAnalyzing(true);
      setError(null);
      const response = await checkFeasibility(buildingId);
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
      analyzingRef.current = false;
    }
  };

  const handleAnalyze = async () => {
    if (!selectedBuildingId) return;
    setFeasibilityPanelCollapsed(false);
    await runAnalysis(selectedBuildingId);
  };

  const handleAnalyzeBuilding = async (buildingId: string) => {
    setFeasibilityPanelCollapsed(false);
    await runAnalysis(buildingId);
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
    setMinVacancyFilter(0);
    setLatestAnalysis(null);
    setProjectPanelCollapsed(false);
    setFeasibilityPanelCollapsed(false);
    setViewportBbox(DEFAULT_BBOX);
    setQueryBbox(DEFAULT_BBOX);
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
        onAnalyzeBuilding={handleAnalyzeBuilding}
        onViewportChange={setViewportBbox}
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
            minVacancyFilter={minVacancyFilter}
            onMinVacancyFilterChange={setMinVacancyFilter}
            collapsed={projectPanelCollapsed}
            onToggleCollapsed={() => setProjectPanelCollapsed((value) => !value)}
          />
        </div>
      </aside>

      <FeasibilityPanel
        result={result}
        selectedBuildingName={selectedBuilding?.name ?? null}
        analyzing={analyzing}
        latestAnalysis={latestAnalysis}
        collapsed={feasibilityPanelCollapsed}
        onToggleCollapsed={() => setFeasibilityPanelCollapsed((value) => !value)}
      />

      {loading && buildings.length === 0 ? (
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
