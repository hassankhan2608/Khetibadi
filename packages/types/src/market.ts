export type PriceAlertDirection = "above" | "below";

export interface MarketPrice {
  id: string;
  commodity: string;
  state: string;
  market: string;
  unit: string;
  min_price: number;
  max_price: number;
  modal_price: number;
  observed_at: string;
}

export interface MarketPriceFilters {
  commodity?: string;
  state?: string;
  page?: number;
  limit?: number;
}

export interface MarketHistoryFilters extends MarketPriceFilters {
  from?: string;
  to?: string;
}

export interface PriceAlert {
  id: string;
  user_id: string;
  commodity: string;
  state: string;
  market: string;
  direction: PriceAlertDirection;
  target_price: number;
  active: boolean;
  created_at: string;
}

export interface PriceAlertCreateRequest {
  commodity: string;
  state: string;
  market?: string;
  direction: PriceAlertDirection;
  target_price: number;
}
