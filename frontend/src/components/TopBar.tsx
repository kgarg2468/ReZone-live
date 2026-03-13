"use client";

type MapStyle = "satellite" | "dark";

interface TopBarProps {
  mapStyle: MapStyle;
  onToggleMapStyle: () => void;
  onNewAnalysis: () => void;
}

export default function TopBar({
  mapStyle,
  onToggleMapStyle,
  onNewAnalysis,
}: TopBarProps) {
  return (
    <header className="topbar animate-fade-in">
      <div className="topbar-brand">
        <div className="topbar-logo">HX</div>
        <div>
          <h1 className="topbar-title">HomeX - Spatial Intelligence for Housing</h1>
          <span className="topbar-subtitle">Office-to-Housing Conversion Intelligence</span>
        </div>
      </div>

      <div className="topbar-actions">
        <button className="btn btn-secondary" onClick={onToggleMapStyle} type="button">
          {mapStyle === "satellite" ? "Satellite" : "Dark"} Style
        </button>
        <button className="btn btn-primary" onClick={onNewAnalysis} type="button">
          New Analysis
        </button>
      </div>
    </header>
  );
}
