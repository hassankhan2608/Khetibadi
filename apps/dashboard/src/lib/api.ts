import type { AxiosError } from "axios";
import axios, { type AxiosRequestConfig } from "axios";

import type {
  ApiResponse,
  AuthSession,
  ChangePasswordRequest,
  ChatMessage,
  ChatSession,
  ChatSessionCreateRequest,
  CropRecommendation,
  CropRecommendationRequest,
  DetectionJob,
  DiseaseDetectionResult,
  Farm,
  FarmCreateRequest,
  FertilizerRecommendation,
  FertilizerRecommendationRequest,
  LoginRequest,
  MarketPrice,
  PaginatedResponse,
  PriceAlert,
  PriceAlertCreateRequest,
  RegisterRequest,
  SoilSample,
  SoilSampleCreateRequest,
  WeatherData,
  YieldPrediction,
  YieldPredictionRequest,
} from "@khetibadi/types";

import { clearAuth, getAccessToken, setAuth } from "../store/auth-store";

const baseURL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL,
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token !== null) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let refreshPromise: Promise<AuthSession> | null = null;

async function refreshSession(): Promise<AuthSession> {
  refreshPromise ??= authApi.refresh();
  try {
    return await refreshPromise;
  } finally {
    refreshPromise = null;
  }
}

function isRefreshRequest(config: AxiosRequestConfig | undefined): boolean {
  return config?.url === "/auth/refresh";
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (AxiosRequestConfig & { _retry?: boolean }) | undefined;
    if (
      error.response?.status !== 401
      || original?._retry === true
      || original === undefined
      || isRefreshRequest(original)
    ) {
      return Promise.reject(error);
    }
    original._retry = true;
    try {
      const session = await refreshSession();
      setAuth(session);
      return api(original);
    } catch (refreshError) {
      clearAuth();
      return Promise.reject(refreshError);
    }
  },
);

function data<T>(response: { data: ApiResponse<T> }): T {
  return response.data.data;
}

export const authApi = {
  async login(req: LoginRequest): Promise<AuthSession> {
    return data(await api.post<ApiResponse<AuthSession>>("/auth/login", req));
  },
  async register(req: RegisterRequest): Promise<AuthSession> {
    return data(await api.post<ApiResponse<AuthSession>>("/auth/register", req));
  },
  async refresh(): Promise<AuthSession> {
    return data(await api.post<ApiResponse<AuthSession>>("/auth/refresh"));
  },
  async logout(): Promise<void> {
    await api.post("/auth/logout");
  },
  async changePassword(req: ChangePasswordRequest): Promise<void> {
    await api.put("/auth/password", req);
  },
};

export async function ensureAuthSession(): Promise<boolean> {
  if (getAccessToken() !== null) {
    return true;
  }
  try {
    const session = await refreshSession();
    setAuth(session);
    return true;
  } catch {
    clearAuth();
    return false;
  }
}

export const farmApi = {
  async list(): Promise<Farm[]> {
    return (await api.get<PaginatedResponse<Farm>>("/farms")).data.data;
  },
  async create(req: FarmCreateRequest): Promise<Farm> {
    return data(await api.post<ApiResponse<Farm>>("/farms", req));
  },
  async update(id: string, req: Partial<FarmCreateRequest>): Promise<Farm> {
    return data(await api.patch<ApiResponse<Farm>>(`/farms/${id}`, req));
  },
  async remove(id: string): Promise<void> {
    await api.delete(`/farms/${id}`);
  },
  async soilSamples(id: string): Promise<SoilSample[]> {
    return (await api.get<PaginatedResponse<SoilSample>>(`/farms/${id}/soil-samples`)).data.data;
  },
  async addSoilSample(id: string, req: SoilSampleCreateRequest): Promise<SoilSample> {
    return data(await api.post<ApiResponse<SoilSample>>(`/farms/${id}/soil-samples`, req));
  },
  async weather(id: string): Promise<WeatherData> {
    return data(await api.get<ApiResponse<WeatherData>>(`/farms/${id}/weather`));
  },
};

export const marketApi = {
  async prices(): Promise<MarketPrice[]> {
    return (await api.get<PaginatedResponse<MarketPrice>>("/market/prices")).data.data;
  },
  async commodities(): Promise<string[]> {
    return data(await api.get<ApiResponse<string[]>>("/market/commodities"));
  },
  async alerts(): Promise<PriceAlert[]> {
    return data(await api.get<ApiResponse<PriceAlert[]>>("/market/alerts"));
  },
  async createAlert(req: PriceAlertCreateRequest): Promise<PriceAlert> {
    return data(await api.post<ApiResponse<PriceAlert>>("/market/alerts", req));
  },
};

export const mlApi = {
  async recommend(req: CropRecommendationRequest): Promise<CropRecommendation> {
    return (await api.post<CropRecommendation>("/ml/crop/recommend", req)).data;
  },
  async yield(req: YieldPredictionRequest): Promise<YieldPrediction> {
    return (await api.post<YieldPrediction>("/ml/crop/yield", req)).data;
  },
  async fertilizer(req: FertilizerRecommendationRequest): Promise<FertilizerRecommendation> {
    return (await api.post<FertilizerRecommendation>("/ml/crop/fertilizer", req)).data;
  },
};

export const visionApi = {
  async detect(file: File): Promise<DiseaseDetectionResult> {
    const form = new FormData();
    form.append("image", file);
    return (await api.post<DiseaseDetectionResult>("/ml/vision/detect", form)).data;
  },
  async submit(file: File): Promise<{ job_id: string; status: string }> {
    const form = new FormData();
    form.append("image", file);
    return (await api.post<{ job_id: string; status: string }>("/ml/vision/detect/async", form)).data;
  },
  async job(jobId: string): Promise<DetectionJob> {
    return (await api.get<DetectionJob>(`/ml/vision/jobs/${jobId}`)).data;
  },
  async classes(): Promise<{ classes: string[] }> {
    return (await api.get<{ classes: string[] }>("/ml/vision/classes")).data;
  },
};

export const chatApi = {
  async sessions(): Promise<ChatSession[]> {
    return (await api.get<{ sessions: ChatSession[] }>("/ai/chat/sessions")).data.sessions;
  },
  async createSession(req: ChatSessionCreateRequest): Promise<ChatSession> {
    return (await api.post<{ session: ChatSession }>("/ai/chat/sessions", req)).data.session;
  },
  async messages(sessionId: string): Promise<ChatMessage[]> {
    return (await api.get<{ messages: ChatMessage[] }>(`/ai/chat/sessions/${sessionId}/messages`)).data.messages;
  },
};

export function apiBaseURL(): string {
  return baseURL;
}
