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
  minVacancyFilter: number;
  onMinVacancyFilterChange: (value: number) => void;
  collapsed: boolean;
  onToggleCollapsed: () => void;
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
  minVacancyFilter,
  onMinVacancyFilterChange,
  collapsed,
  onToggleCollapsed,
}: ProjectPanelProps) {
  const cities = useMemo(
    () => ["All", ...Array.from(new Set(buildings.map((building) => building.city))).sort()],
    [buildings]
  );

  const cityFilteredBuildings = useMemo(() => {
    if (cityFilter === "All") return buildings;
    return buildings.filter((building) => building.city === cityFilter);
  }, [buildings, cityFilter]);

  const filteredBuildings = useMemo(() => {
    const visible = cityFilteredBuildings.filter((building) => building.vacancy_pct >= minVacancyFilter);
    visible.sort(
      (a, b) => a.vacancy_pct - b.vacancy_pct || a.name.localeCompare(b.name)
    );
    return visible;
  }, [cityFilteredBuildings, minVacancyFilter]);

  return (
    <section>
      <div className="building-list-header">
        <h2 className="panel-title">Project List</h2>
        <div className="panel-header-actions">
          <span className="building-count">{filteredBuildings.length}</span>
          <button
            className="panel-close"
            onClick={onToggleCollapsed}
            type="button"
            aria-label={collapsed ? "Expand project list" : "Collapse project list"}
          >
            {collapsed ? "+" : "-"}
          </button>
        </div>
      </div>

      <div className={`panel-body-transition ${collapsed ? "panel-body-hidden" : ""}`}>
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

        <div className="vacancy-filter">
          <label className="vacancy-filter-label" htmlFor="vacancy-filter-range">
            Vacancy &gt;= {minVacancyFilter}%
          </label>
          <input
            className="vacancy-filter-range"
            id="vacancy-filter-range"
            type="range"
            min={0}
            max={100}
            step={5}
            value={minVacancyFilter}
            onChange={(event) => onMinVacancyFilterChange(Number(event.target.value))}
          />
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
      </div>
    </section>
  );
}
