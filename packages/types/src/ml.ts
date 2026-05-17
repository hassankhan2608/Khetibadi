export interface CropFeatures {
  nitrogen: number;
  phosphorus: number;
  potassium: number;
  temperature: number;
  humidity: number;
  ph: number;
  rainfall: number;
}

export interface CropRecommendationRequest extends CropFeatures {
  season: string;
  state: string;
}

export interface CropRecommendation {
  crop: string;
  confidence: number;
  alternatives: string[];
  model_mode: "stub";
  warning: string | null;
}

export interface YieldPredictionRequest extends CropFeatures {
  crop: string;
  area_hectares: number;
  season: string;
}

export interface YieldPrediction {
  crop: string;
  predicted_yield_tonnes: number;
  yield_per_hectare_tonnes: number;
  model_mode: "stub";
  warning: string | null;
}

export interface FertilizerRecommendationRequest extends CropFeatures {
  crop: string;
  soil_type: string;
}

export interface FertilizerRecommendation {
  recommendation: string;
  nitrogen_kg_per_ha: number;
  phosphorus_kg_per_ha: number;
  potassium_kg_per_ha: number;
  model_mode: "stub";
  warning: string | null;
}
