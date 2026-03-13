"use client";

import { useMemo, useState } from "react";
import type { LayerInfo } from "@/lib/api";

export type LayerKey =
  | "office_buildings"
  | "zoning_districts"
  | "utility_infrastructure"
  | "transit_stops";

interface LayerPanelProps {
  layers: Partial<Record<LayerKey, LayerInfo>>;
  visibleLayers: Record<LayerKey, boolean>;
  onToggleLayer: (layer: LayerKey) => void;
}

const layerConfig: Array<{ key: LayerKey; name: string; color: string }> = [
  { key: "office_buildings", name: "Office Buildings", color: "#f59e0b" },
  { key: "zoning_districts", name: "Zoning Districts", color: "#3b82f6" },
  { key: "utility_infrastructure", name: "Utility Infrastructure", color: "#22c55e" },
  { key: "transit_stops", name: "Transit Stops", color: "#f97316" },
];

export default function LayerPanel({
  layers,
  visibleLayers,
  onToggleLayer,
}: LayerPanelProps) {
  const [collapsed, setCollapsed] = useState(false);

  const layerCount = useMemo(
    () => layerConfig.reduce((count, layer) => count + (layers[layer.key] ? 1 : 0), 0),
    [layers]
  );

  return (
    <section>
      <div className="panel-header">
        <h2 className="panel-title">Data Layers</h2>
        <div className="panel-header-actions">
          <span className="building-count">{layerCount}</span>
          <button
            className="panel-close"
            onClick={() => setCollapsed((value) => !value)}
            type="button"
            aria-label={collapsed ? "Expand layer panel" : "Collapse layer panel"}
          >
            {collapsed ? "+" : "-"}
          </button>
        </div>
      </div>

      <div className={`panel-body panel-body-transition ${collapsed ? "panel-body-hidden" : ""}`}>
        {layerConfig.map((layer) => {
          const layerInfo = layers[layer.key];
          return (
            <div className="layer-item" key={layer.key}>
              <span className="layer-dot" style={{ color: layer.color, backgroundColor: layer.color }} />

              <div className="layer-info">
                <div className="layer-name">{layer.name}</div>
                <div className="layer-source">
                  {layerInfo ? `${layerInfo.feature_count} features` : "Loading..."}
                </div>
                {layerInfo ? <div className="layer-source">{layerInfo.source}</div> : null}
              </div>

              <label className="toggle" aria-label={`Toggle ${layer.name}`}>
                <input
                  checked={visibleLayers[layer.key]}
                  onChange={() => onToggleLayer(layer.key)}
                  type="checkbox"
                />
                <span className="toggle-slider" />
              </label>
            </div>
          );
        })}
      </div>
    </section>
  );
}
