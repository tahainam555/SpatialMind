export type Wall = 'north' | 'south' | 'east' | 'west';
export type OpeningKind = 'door' | 'window';
export type RoomType = 'bedroom' | 'living_room' | 'office';

export interface Opening {
  kind: OpeningKind;
  wall: Wall;
  offset: number;
  width: number;
}

export interface Room {
  width: number;
  depth: number;
  height: number;
  openings: Opening[];
}

export interface PlacedObject {
  id: string;
  category: string;
  width: number;
  depth: number;
  height: number;
  x: number;
  y: number;
  rotation: number;
}

export interface ObjectRequest {
  category: string;
  quantity: number;
}

export interface Constraint {
  type: string;
  subject: string;
  target?: string | null;
  wall?: Wall | null;
  distance?: number | null;
}

export interface SceneSpec {
  room_type: RoomType;
  room?: Room | null;
  objects: ObjectRequest[];
  constraints: Constraint[];
  style?: string | null;
}

export interface Violation {
  kind: string;
  objects: string[];
  message: string;
  magnitude: number;
  hard: boolean;
}

export interface ConstraintResult {
  constraint: string;
  satisfied: boolean;
  detail: string;
}

export interface VerificationReport {
  violations: Violation[];
  constraint_results: ConstraintResult[];
  metrics: Record<string, number>;
  score: number;
  passed: boolean;
}

export interface TraceStep {
  stage: string;
  iteration: number;
  duration_ms: number;
  summary: string;
  passed?: boolean | null;
}

export interface ScenePayloadObject {
  id: string;
  category: string;
  asset: string;
  location: [number, number, number];
  rotation_z_deg: number;
  dimensions: [number, number, number];
}

export interface ScenePayload {
  format: string;
  room: Room;
  objects: ScenePayloadObject[];
}

export interface GenerationResult {
  prompt: string;
  provider: string;
  spec: SceneSpec;
  memory: {
    room: Room;
    constraints: Constraint[];
    objects: Record<string, PlacedObject>;
    iteration: number;
    events: Array<{ iteration: number; action: string; detail: string }>;
  };
  scene: ScenePayload;
  initial_report: VerificationReport;
  final_report: VerificationReport;
  iterations: number;
  passed: boolean;
  refined: boolean;
  fault_injected: string | null;
  trace: TraceStep[];
  total_ms: number;
}

export interface CatalogItem {
  category: string;
  width: number;
  depth: number;
  height: number;
  freestanding: boolean;
}

export interface HealthInfo {
  status: string;
  version: string;
  provider: string;
}
