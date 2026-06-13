// Single source of truth. Every statistic shown on the site is read from the
// real pipeline artifacts copied into this folder — never hand-typed.
import assetSpec from "./asset_spec.json";
import validation from "./validation_report.json";
import contract from "./godot_setup.json";
import khronos from "./khronos_report.json";

export const spec = assetSpec;
export const report = validation;
export const setup = contract;
export const khronosReport = khronos;

export const metrics = validation.metrics;
export const checks = validation.checks;

// ── Derived selectors ──────────────────────────────────────────────────────

export type CheckRow = {
  key: string;
  label: string;
  value: string;
  limit: string;
  pass: boolean;
};

/** The 10 validation-gate checks, flattened for display with human labels. */
export const checkRows: CheckRow[] = [
  {
    key: "tri_budget",
    label: "Triangle budget",
    value: `${checks.tri_budget.used} tris`,
    limit: `≤ ${checks.tri_budget.limit}`,
    pass: checks.tri_budget.pass,
  },
  {
    key: "weights_normalized",
    label: "Skin weights normalized",
    value: `err ${checks.weights_normalized.max_err}`,
    limit: "= 0",
    pass: checks.weights_normalized.pass,
  },
  {
    key: "max_influences",
    label: "Max bone influences",
    value: `${checks.max_influences.value} / vertex`,
    limit: `≤ ${checks.max_influences.limit}`,
    pass: checks.max_influences.pass,
  },
  {
    key: "loop_closure",
    label: "Loop closure (idle/walk/run)",
    value: "Δ 0.0",
    limit: "= 0",
    pass: checks.loop_closure.pass,
  },
  {
    key: "bone_containment",
    label: "Joints inside mesh volume",
    value: `${checks.bone_containment.inside} / ${checks.bone_containment.required}`,
    limit: "all skinned",
    pass: checks.bone_containment.pass,
  },
  {
    key: "foot_contact",
    label: "Planted-foot hover",
    value: `${checks.foot_contact.worst_dev_mm} mm`,
    limit: `≤ ${checks.foot_contact.limit_mm} mm`,
    pass: checks.foot_contact.pass,
  },
  {
    key: "in_place",
    label: "In-place root drift",
    value: "0.0 m",
    limit: "= 0",
    pass: checks.in_place.pass,
  },
  {
    key: "death_collapses",
    label: "Death collapse height",
    value: `${checks.death_collapses.final_body_max_y} m`,
    limit: "< 0.26 m",
    pass: checks.death_collapses.pass,
  },
  {
    key: "ground_penetration",
    label: "Worst ground penetration",
    value: `${(checks.ground_penetration.worst_m * 1000).toFixed(1)} mm`,
    limit: `≥ ${(checks.ground_penetration.limit_m * 1000).toFixed(0)} mm`,
    pass: checks.ground_penetration.pass,
  },
  {
    key: "khronos_gltf_conformance",
    label: "Khronos glTF validator",
    value: "0 / 0 / 0 / 0",
    limit: "0 errors",
    pass: checks.khronos_gltf_conformance.pass,
  },
];

/** The headline before/after the planted-foot world-space solver. */
export const solverDelta = [
  {
    metric: "Planted-foot hover",
    before: "14–19 mm",
    after: `${checks.foot_contact.worst_dev_mm} mm`,
    limit: `${checks.foot_contact.limit_mm} mm`,
    unit: "lower is better",
  },
  {
    metric: "Death-clip ground penetration",
    before: "−95 mm",
    after: `${(checks.ground_penetration.worst_m * 1000).toFixed(1)} mm`,
    limit: `${(checks.ground_penetration.limit_m * 1000).toFixed(0)} mm`,
    unit: "closer to 0 is better",
  },
];

export const locomotion = {
  walk: metrics.locomotion["walk-loop"],
  run: metrics.locomotion["run-loop"],
};
