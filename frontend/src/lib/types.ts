export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  access_expires_in: number;
  refresh_expires_in: number;
}

export type ViolationDecision = 'confirmed' | 'false_alarm';

export interface Violation {
  id: number;
  camera_id: number;
  zone_id: number | null;
  track_id: string | null;
  type: string;
  timestamp: string;
  frame_path: string | null;
  frame_url?: string | null;
  face_id: number | null;
  identity_status: string;
  status: string;
  admitted?: boolean;
  camera_name?: string | null;
  zone_name?: string | null;
}

export interface ViolationListResponse {
  items: Violation[];
  total: number;
  limit: number;
  offset: number;
}

export interface WsViolationMessage {
  type: string;
  data: Violation;
}

export interface Camera {
  id: number;
  name: string;
  rtsp_url: string;
  status: string;
  worker_id: number | null;
  config: Record<string, unknown>;
}

export type StatusUpdateHandler = (id: number, status: string) => void;