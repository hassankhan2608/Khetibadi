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
  reasons: string[];
  model_mode: "stub";
  warning?: string;
}

export interface YieldPredictionRequest extends CropFeatures {
  crop: string;
  area_hectares: number;
  season: string;
}

export interface YieldPrediction {
  crop: string;
  estimated_yield_tonnes_per_hectare: number;
  estimated_total_tonnes: number;
  confidence: number;
  model_mode: "stub";
  warning?: string;
}

export interface FertilizerRecommendationRequest extends CropFeatures {
  crop: string;
  soil_type: string;
}

export interface FertilizerRecommendation {
  nitrogen_kg_per_hectare: number;
  phosphorus_kg_per_hectare: number;
  potassium_kg_per_hectare: number;
  notes: string[];
  model_mode: "stub";
  warning?: string;
}
