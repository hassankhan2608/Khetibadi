export interface ApiResponse<T> {
  data: T;
}

export interface PaginationMeta {
  page: number;
  limit: number;
  total: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  meta: PaginationMeta;
}

export interface ApiError {
  error: string;
  message: string;
}

export type ApiEnvelope<T> = ApiResponse<T> | PaginatedResponse<T>;
