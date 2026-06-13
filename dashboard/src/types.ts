export type Check = { pass?: boolean; [k: string]: unknown };

export type Loco = {
  gait: string;
  cycle_s: number;
  stance_foot_dev_mm: number;
  mean_stride_m: number;
  recommended_speed_mps: number;
  in_place_drift_m: number;
};

export type ValidationReport = {
  file: string;
  checks: Record<string, Check>;
  metrics: {
    triangles: number;
    vertices: number;
    joints: number;
    locomotion: Record<string, Loco>;
  };
  warnings: string[];
  overall_pass: boolean;
};

export type Attempt = {
  attempt: number;
  seed: number;
  cache_key: string;
  cache_hit?: boolean;
  overall_pass?: boolean;
  gate?: string;
  failing?: string[];
  seconds: number;
};

export type RunManifest = {
  prompt: string;
  archetype: string;
  mesh_tier_requested: string;
  model_versions: Record<string, string>;
  attempts: Attempt[];
  success: boolean;
  total_seconds: number;
  diagnosis: { message: string } | null;
};

export type AssetSpec = {
  prompt: string;
  archetype: string;
  seed: number;
  style: string;
  target_height_m: number;
  tri_budget: number;
  material_model: string;
};

const CHECK_LABELS: Record<string, string> = {
  tri_budget: "Triangle budget",
  weights_normalized: "Skin weights normalized",
  max_influences: "Max bone influences",
  loop_closure: "Loop closure",
  bone_containment: "Joints inside mesh",
  foot_contact: "Planted-foot contact",
  in_place: "In-place root drift",
  death_collapses: "Death collapse",
  ground_penetration: "Ground penetration",
  khronos_gltf_conformance: "Khronos glTF (0/0/0/0)",
};

export function checkLabel(key: string): string {
  return CHECK_LABELS[key] ?? key;
}

export function checkDetail(key: string, c: Check): string {
  switch (key) {
    case "tri_budget":
      return `${c.used} / ${c.limit}`;
    case "foot_contact":
      return `${c.worst_dev_mm} mm ≤ ${c.limit_mm}`;
    case "ground_penetration":
      return `${((c.worst_m as number) * 1000).toFixed(1)} mm ≥ ${((c.limit_m as number) * 1000).toFixed(0)}`;
    case "max_influences":
      return `${c.value} / ${c.limit}`;
    case "death_collapses":
      return `${c.final_body_max_y} m < ${c.limit}`;
    case "khronos_gltf_conformance":
      return `${c.errors}/${c.warnings}/${c.infos}/${c.hints}`;
    case "weights_normalized":
      return `err ${c.max_err}`;
    default:
      return "";
  }
}
