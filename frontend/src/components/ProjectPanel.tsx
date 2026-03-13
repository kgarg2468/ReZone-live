"use client";

import { useMemo } from "react";
import type { BuildingSummary } from "@/lib/api";

interface ProjectPanelProps {
  buildings: BuildingSummary[];
  selectedBuildingId: string | null;
  onSelectBuilding: (buildingId: string) => void;
  onAnalyze: () => void;
  onRemove: () => void;
  analyzing: boolean;
  cityFilter: string;
  onCityFilterChange: (city: string) => void;
}

function vacancyColor(vacancy: number): string {
  if (vacancy >= 65) return "#22c55e";
  if (vacancy >= 45) return "#f59e0b";
  return "#ef4444";
}

export default function ProjectPanel({
  buildings,
  selectedBuildingId,
  onSelectBuilding,
  onAnalyze,
  onRemove,
  analyzing,
  cityFilter,
  onCityFilterChange,
}: ProjectPanelProps) {
  const cities = useMemo(
    () => ["All", ...Array.from(new Set(buildings.map((building) => building.city))).sort()],
    [buildings]
  );

  const filteredBuildings = useMemo(() => {
    if (cityFilter === "All") return buildings;
    return buildings.filter((building) => building.city === cityFilter);
  }, [buildings, cityFilter]);

  return (
    <section>
      <div className="building-list-header">
        <h2 className="panel-title">Project List</h2>
        <span className="building-count">{filteredBuildings.length}</span>
      </div>

      <div className="city-tabs">
        {cities.map((city) => (
          <button
            className={`city-tab ${cityFilter === city ? "active" : ""}`}
            key={city}
            onClick={() => onCityFilterChange(city)}
            type="button"
          >
            {city}
          </button>
        ))}
      </div>

      <div>
        {filteredBuildings.map((building) => {
          const isSelected = selectedBuildingId === building.id;
          const vacancy = Math.max(0, Math.min(100, building.vacancy_pct));
          const vacancyFill = vacancyColor(vacancy);

          return (
            <article
              className={`building-card ${isSelected ? "selected" : ""}`}
              key={building.id}
              onClick={() => onSelectBuilding(building.id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelectBuilding(building.id);
                }
              }}
              role="button"
              tabIndex={0}
            >
              <div className="building-card-header">
                <div className="building-name">{building.name}</div>
                <div className="building-city">{building.city}</div>
              </div>

              <div className="building-meta">
                <div className="building-stat">
                  Size: <span>{building.sqft.toLocaleString()} sqft</span>
                </div>
                <div className="building-stat">
                  Floors: <span>{building.floors}</span>
                </div>
                <div className="building-stat">
                  Structure: <span>{building.structural_type}</span>
                </div>
                <div className="building-stat">
                  Vacancy: <span>{vacancy}%</span>
                </div>
              </div>

              <div className="building-vacancy">
                <div className="vacancy-bar-track">
                  <div
                    className="vacancy-bar-fill"
                    style={{ width: `${vacancy}%`, backgroundColor: vacancyFill }}
                  />
                </div>
                <span className="vacancy-label" style={{ color: vacancyFill }}>
                  {vacancy}%
                </span>
              </div>

              {isSelected ? (
                <div className="building-actions">
                  <button className="btn btn-primary btn-sm" onClick={onAnalyze} type="button">
                    {analyzing ? "Analyzing..." : "Analyze"}
                  </button>
                  <button className="btn btn-danger btn-sm" onClick={onRemove} type="button">
                    Remove
                  </button>
                </div>
              ) : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}
