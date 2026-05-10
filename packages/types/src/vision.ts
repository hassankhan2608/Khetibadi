export interface ImageMetadata {
  filename: string;
  content_type: string;
  width: number;
  height: number;
  size_bytes: number;
}

export interface DiseaseDetectionResult {
  disease: string;
  confidence: number;
  is_healthy: boolean;
  background_removed: boolean;
  fallback_resize: boolean;
  annotated_image_base64: string;
  model_mode: "stub";
  warning?: string;
  metadata: ImageMetadata;
}

export type DetectionJobStatus = "queued" | "completed" | "failed";

export interface DetectionJob {
  job_id: string;
  status: DetectionJobStatus;
  submitted_at: string;
  expires_at: string;
  result?: DiseaseDetectionResult;
  error?: string;
}
