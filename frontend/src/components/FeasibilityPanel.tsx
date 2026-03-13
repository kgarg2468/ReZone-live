"use client";

import type { FeasibilityResponse } from "@/lib/api";

export interface LatestAnalysisSummary {
  buildingName: string;
  address: string;
  tier: string;
  score: number;
  analyzedAt: string;
}

interface FeasibilityPanelProps {
  result: FeasibilityResponse | null;
  selectedBuildingName: string | null;
  analyzing: boolean;
  latestAnalysis: LatestAnalysisSummary | null;
}

function getScoreColor(score: number): string {
  if (score >= 80) return "#22c55e";
  if (score >= 60) return "#3b82f6";
  if (score >= 40) return "#f59e0b";
  return "#ef4444";
}

function getTierClass(tier: string): string {
  const normalized = tier.toLowerCase();
  if (normalized === "excellent") return "tier-excellent";
  if (normalized === "good") return "tier-good";
  if (normalized === "moderate") return "tier-moderate";
  return "tier-poor";
}

function currency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

interface FactorItem {
  key: string;
  label: string;
  score: number;
  detail: string;
  confidence?: number;
}

function LatestAnalysisCard({ latestAnalysis }: { latestAnalysis: LatestAnalysisSummary | null }) {
  if (!latestAnalysis) return null;

  return (
    <div className="analysis-summary-card">
      <div className="analysis-summary-header">
        <span className="analysis-summary-label">Latest Analysis</span>
        <span className="analysis-summary-time">{latestAnalysis.analyzedAt}</span>
      </div>
      <div className="analysis-summary-building">{latestAnalysis.buildingName}</div>
      <div className="analysis-summary-address">{latestAnalysis.address}</div>
      <div className="analysis-summary-metrics">
        <span className={`tier-badge ${getTierClass(latestAnalysis.tier)}`}>{latestAnalysis.tier}</span>
        <span className="analysis-summary-score" style={{ color: getScoreColor(latestAnalysis.score) }}>
          Score: {latestAnalysis.score}
        </span>
      </div>
    </div>
  );
}

export default function FeasibilityPanel({
  result,
  selectedBuildingName,
  analyzing,
  latestAnalysis,
}: FeasibilityPanelProps) {
  if (!result) {
    return (
      <aside className="panel panel-right animate-slide-right">
        <div className="panel-header">
          <h2 className="panel-title">Feasibility Analysis</h2>
        </div>

        <LatestAnalysisCard latestAnalysis={latestAnalysis} />

        <div className="panel-body">
          <div className="empty-panel">
            <p className="empty-panel-title">
              {analyzing
                ? "Running feasibility engine..."
                : selectedBuildingName
                  ? `Ready to analyze ${selectedBuildingName}`
                  : "Double-click a map building to start"}
            </p>
            <p className="empty-panel-copy">
              Double-click any office building on the map to run analysis instantly. ReZone scores zoning,
              utility access, transit, and structural complexity, then recommends a conversion strategy with
              cost and timeline estimates.
            </p>
          </div>
        </div>
      </aside>
    );
  }

  const scoreColor = getScoreColor(result.score);
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const progressOffset = circumference - (result.score / 100) * circumference;

  const factors: FactorItem[] = [
    {
      key: "zoning",
      label: "Zoning",
      score: result.factor_scores.zoning,
      detail: result.zoning.requires_rezoning
        ? `Current district (${result.zoning.zone_name}) requires rezoning.`
        : `Residential use allowed in ${result.zoning.zone_name}.`,
      confidence: result.data_confidence?.zoning,
    },
    {
      key: "utilities",
      label: "Utilities",
      score: result.factor_scores.utilities,
      detail: `${result.utilities.length} utility systems evaluated in radius.`,
      confidence: result.data_confidence?.utilities,
    },
    {
      key: "transit",
      label: "Transit",
      score: result.factor_scores.transit,
      detail: `${result.transit.nearest_stations.length} nearby stations with ${result.transit.total_daily_ridership.toLocaleString()} daily riders.`,
      confidence: result.data_confidence?.transit,
    },
    {
      key: "structural",
      label: "Structural",
      score: result.factor_scores.structural,
      detail: `${result.structural.structural_type}, ${result.structural.floors} floors, ${result.structural.conversion_difficulty} conversion difficulty.`,
      confidence: result.data_confidence?.structural,
    },
  ];

  const lowTotal = result.recommendation.cost_estimates.reduce(
    (sum, item) => sum + item.low_estimate,
    0
  );
  const highTotal = result.recommendation.cost_estimates.reduce(
    (sum, item) => sum + item.high_estimate,
    0
  );

  return (
    <aside className="panel panel-right animate-slide-right">
      <div className="panel-header">
        <h2 className="panel-title">Feasibility Analysis</h2>
      </div>

      <LatestAnalysisCard latestAnalysis={latestAnalysis} />

      <div className="panel-body">
        <div className="score-section">
          <div className="score-ring">
            <svg aria-hidden="true">
              <circle className="score-ring-bg" cx="60" cy="60" r={radius} />
              <circle
                className="score-ring-fill"
                cx="60"
                cy="60"
                r={radius}
                style={{
                  strokeDasharray: circumference,
                  strokeDashoffset: progressOffset,
                  stroke: scoreColor,
                }}
              />
            </svg>
            <div className="score-value" style={{ color: scoreColor }}>
              {result.score}
            </div>
          </div>
          <div className="score-label">Feasibility Score</div>
          <span className={`tier-badge ${getTierClass(result.tier)}`}>{result.tier}</span>
          <p className="factor-detail" style={{ marginTop: "10px" }}>
            {result.tier_description}
          </p>
          {result.data_confidence ? (
            <p className="factor-detail" style={{ marginTop: "6px" }}>
              Live Data Confidence: {Math.round(result.data_confidence.overall * 100)}%
            </p>
          ) : null}
        </div>

        <div className="section-divider">Factor Breakdown</div>
        {factors.map((factor) => (
          <div className="factor-card" key={factor.key}>
            <div className="factor-header">
              <span className="factor-name">{factor.label}</span>
              <div>
                {factor.confidence !== undefined ? (
                  <span className="tier-badge tier-good" style={{ marginRight: "8px" }}>
                    Live {Math.round(factor.confidence * 100)}%
                  </span>
                ) : null}
                <span className="factor-score" style={{ color: getScoreColor(factor.score) }}>
                  {Math.round(factor.score)}
                </span>
              </div>
            </div>
            <div className="factor-bar">
              <div
                className="factor-bar-fill"
                style={{
                  width: `${Math.max(0, Math.min(100, factor.score))}%`,
                  backgroundColor: getScoreColor(factor.score),
                }}
              />
            </div>
            <p className="factor-detail">{factor.detail}</p>
          </div>
        ))}

        <div className="section-divider">Conflicts</div>
        <div className="factor-card">
          {result.conflicts.length === 0 ? (
            <p className="factor-detail">No critical blockers detected in current pass.</p>
          ) : (
            <ul className="conflict-list">
              {result.conflicts.map((conflict) => (
                <li className="factor-detail" key={conflict}>
                  {conflict}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="section-divider">Recommendation</div>
        <div className="recommendation">
          <h3 className="recommendation-type">{result.recommendation.conversion_type}</h3>
          <p className="recommendation-rationale">{result.recommendation.rationale}</p>

          <div className="recommendation-stats">
            <div className="rec-stat">
              <div className="rec-stat-value">{Math.round(result.recommendation.confidence * 100)}%</div>
              <div className="rec-stat-label">Confidence</div>
            </div>
            <div className="rec-stat">
              <div className="rec-stat-value">{result.recommendation.estimated_units}</div>
              <div className="rec-stat-label">Est. Units</div>
            </div>
            <div className="rec-stat">
              <div className="rec-stat-value">{result.recommendation.timeline_months}</div>
              <div className="rec-stat-label">Months</div>
            </div>
            <div className="rec-stat">
              <div className="rec-stat-value">{currency(lowTotal)}</div>
              <div className="rec-stat-label">Low Budget</div>
            </div>
          </div>
        </div>

        <table className="cost-table">
          <thead>
            <tr>
              <th>Category</th>
              <th>Estimate</th>
            </tr>
          </thead>
          <tbody>
            {result.recommendation.cost_estimates.map((item) => (
              <tr key={item.category}>
                <td>{item.category}</td>
                <td>{`${currency(item.low_estimate)} - ${currency(item.high_estimate)}`}</td>
              </tr>
            ))}
            <tr>
              <td className="cost-total">Total</td>
              <td className="cost-total">{`${currency(lowTotal)} - ${currency(highTotal)}`}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </aside>
  );
}
