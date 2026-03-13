const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type BBox = [number, number, number, number];

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
  source?: string;
  is_proxy?: boolean;
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
    source?: string;
    is_proxy?: boolean;
  }>;
  avg_distance_km: number;
  total_daily_ridership: number;
  score: number;
  source?: string;
  is_proxy?: boolean;
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
  conflicts: string[];
  zoning: ZoningAssessment;
  utilities: UtilityAssessment[];
  transit: TransitAssessment;
  structural: StructuralAssessment;
  recommendation: ConversionRecommendation;
  factor_scores: Record<string, number>;
  data_confidence?: {
    overall: number;
    zoning: number;
    utilities: number;
    transit: number;
    structural: number;
  };
}

function bboxParam(bbox?: BBox): string | null {
  if (!bbox) return null;
  return bbox.join(",");
}

export async function fetchLayers(params?: {
  bbox?: BBox;
  layers?: string[];
}): Promise<Record<string, LayerInfo>> {
  const search = new URLSearchParams();
  const bbox = bboxParam(params?.bbox);
  if (bbox) search.set("bbox", bbox);
  if (params?.layers?.length) search.set("layers", params.layers.join(","));
  const qs = search.toString();
  const res = await fetch(`${API_BASE}/api/layers${qs ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error("Failed to fetch layers");
  return res.json();
}

export async function fetchBuildings(params?: {
  bbox?: BBox;
  limit?: number;
  offset?: number;
}): Promise<BuildingSummary[]> {
  const search = new URLSearchParams();
  const bbox = bboxParam(params?.bbox);
  if (bbox) search.set("bbox", bbox);
  search.set("limit", String(params?.limit ?? 200));
  search.set("offset", String(params?.offset ?? 0));

  const res = await fetch(`${API_BASE}/api/buildings?${search.toString()}`);
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
