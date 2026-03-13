const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface BuildingSummary {
  id: string;
  name: string;
  address: string;
  city: string;
  sqft: number;
  floors: number;
  vacancy_pct: number;
  structural_type: string;
  lat: number;
  lng: number;
}

export interface LayerInfo {
  name: string;
  source: string;
  feature_count: number;
  geojson: GeoJSON.FeatureCollection;
}

export interface CostEstimate {
  category: string;
  low_estimate: number;
  high_estimate: number;
  notes: string;
}

export interface ConversionRecommendation {
  conversion_type: string;
  confidence: number;
  rationale: string;
  estimated_units: number;
  cost_estimates: CostEstimate[];
  timeline_months: number;
}

export interface UtilityAssessment {
  utility_type: string;
  nearest_distance_km: number;
  capacity: string;
  condition: string;
  age_years: number;
  score: number;
}

export interface ZoningAssessment {
  zone_name: string;
  zone_type: string;
  allows_residential: boolean;
  max_density: number;
  max_height_ft: number;
  requires_rezoning: boolean;
  score: number;
}

export interface TransitAssessment {
  nearest_stations: Array<{
    name: string;
    line: string;
    type: string;
    distance_km: number;
    daily_ridership: number;
  }>;
  avg_distance_km: number;
  total_daily_ridership: number;
  score: number;
}

export interface StructuralAssessment {
  structural_type: string;
  year_built: number;
  floors: number;
  sqft: number;
  ceiling_height_ft: number;
  has_elevator: boolean;
  conversion_difficulty: string;
  score: number;
}

export interface FeasibilityResponse {
  building_id: string;
  building_name: string;
  address: string;
  score: number;
  tier: string;
  tier_description: string;
  zoning: ZoningAssessment;
  utilities: UtilityAssessment[];
  transit: TransitAssessment;
  structural: StructuralAssessment;
  recommendation: ConversionRecommendation;
  factor_scores: Record<string, number>;
}

export async function fetchLayers(): Promise<Record<string, LayerInfo>> {
  const res = await fetch(`${API_BASE}/api/layers`);
  if (!res.ok) throw new Error("Failed to fetch layers");
  return res.json();
}

export async function fetchBuildings(): Promise<BuildingSummary[]> {
  const res = await fetch(`${API_BASE}/api/buildings`);
  if (!res.ok) throw new Error("Failed to fetch buildings");
  return res.json();
}

export async function checkFeasibility(
  buildingId: string
): Promise<FeasibilityResponse> {
  const res = await fetch(`${API_BASE}/api/feasibility-check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ building_id: buildingId }),
  });
  if (!res.ok) throw new Error("Feasibility check failed");
  return res.json();
}
