export type GeoJSONPosition = [number, number];

export interface GeoJSONPolygon {
  type: "Polygon";
  coordinates: GeoJSONPosition[][];
}

export interface Farm {
  id: string;
  user_id: string;
  name: string;
  crop: string;
  soil_type: string;
  area_hectares: number;
  boundary: GeoJSONPolygon;
  created_at: string;
  updated_at: string;
}

export interface FarmCreateRequest {
  name: string;
  crop: string;
  soil_type: string;
  area_hectares: number;
  boundary: GeoJSONPolygon;
}

export type FarmUpdateRequest = Partial<FarmCreateRequest>;

export interface SoilSample {
  id: string;
  farm_id: string;
  user_id: string;
  ph: number;
  nitrogen: number;
  phosphorus: number;
  potassium: number;
  organic_carbon: number;
  moisture: number;
  collected_at: string;
  created_at: string;
}

export interface SoilSampleCreateRequest {
  ph: number;
  nitrogen: number;
  phosphorus: number;
  potassium: number;
  organic_carbon: number;
  moisture: number;
  collected_at?: string;
}

export interface WeatherData {
  farm_id: string;
  temperature_celsius: number;
  humidity_percent: number;
  rainfall_mm: number;
  wind_speed_mps: number;
  condition: string;
  source: string;
  cached: boolean;
  observed_at: string;
}
