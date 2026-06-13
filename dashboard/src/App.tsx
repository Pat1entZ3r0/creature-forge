import { useEffect, useState } from "react";
import { checkDetail, checkLabel } from "./types";
import type { AssetSpec, RunManifest, ValidationReport } from "./types";

const BASE = import.meta.env.BASE_URL;
const D = (f: string) => `${BASE}data/${f}`;

type SetupAnim = { name: string; loop: boolean; role: string };
type Setup = {
  display_name: string;
  health: number;
  animations: SetupAnim[];
  locomotion: { walk: { speed_mps: number }; run: { speed_mps: number } };
};

async function getJSON<T>(f: string): Promise<T | null> {
  try {
    const r = await fetch(D(f));
    return r.ok ? ((await r.json()) as T) : null;
  } catch {
    return null;
  }
}

export default function App() {
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [manifest, setManifest] = useState<RunManifest | null>(null);
  const [spec, setSpec] = useState<AssetSpec | null>(null);
  const [setup, setSetup] = useState<Setup | null>(null);
  const [clip, setClip] = useState("walk-loop");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    (async () => {
      setReport(await getJSON<ValidationReport>("validation_report.json"));
      setManifest(await getJSON<RunManifest>("run_manifest.json"));
      setSpec(await getJSON<AssetSpec>("spider_alien.asset_spec.json"));
      setSetup(await getJSON<Setup>("spider_alien.godot_setup.json"));
      setLoaded(true);
    })();
  }, []);

  if (loaded && !report) {
    return (
      <main className="empty">
        <h1 className="brand">◆ creature&#8209;forge</h1>
        <p>No run artifacts found. Generate one, then sync:</p>
        <pre>make run{"\n"}cd dashboard &amp;&amp; npm run sync</pre>
      </main>
    );
  }
  if (!report) return <main className="empty">loading…</main>;

  const checks = Object.entries(report.checks);
  const passed = checks.filter(([, c]) => c.pass).length;
  const clips = setup?.animations.map((a) => a.name) ?? Object.keys(report.metrics.locomotion);
  const loco = report.metrics.locomotion;

  return (
    <>
      <div className="grain" aria-hidden />
      <header className="top">
        <span className="brand">◆ creature&#8209;forge</span>
        <span className="mono dim">run dashboard</span>
      </header>

      <main className="wrap">
        <section className="hero">
          <div className="hero__head">
            <span className="kicker">
              {report.overall_pass ? "validated · shipping" : "gate failed"}
            </span>
            <h1>{setup?.display_name ?? report.file}</h1>
            {spec && <p className="prompt">“{spec.prompt}”</p>}
            <div className="meta mono dim">
              {spec && <span>seed {spec.seed}</span>}
              {manifest && <span>· {manifest.archetype}</span>}
              {manifest && <span>· tier {manifest.mesh_tier_requested}</span>}
              {setup && <span>· {setup.health} hp</span>}
            </div>
            <div className="bigstats">
              <Stat v={`${report.metrics.triangles}`} l="triangles" sub={spec ? `budget ${spec.tri_budget}` : ""} />
              <Stat v={`${report.metrics.joints}`} l="joints" />
              <Stat v={`${clips.length}`} l="clips" />
              <Stat v={`${passed}/${checks.length}`} l="checks" accent={report.overall_pass} />
            </div>
          </div>

          <div className="viewer">
            <model-viewer
              src={D("spider_alien.glb")}
              animation-name={clip}
              autoplay
              camera-controls
              interaction-prompt="none"
              shadow-intensity="0.6"
              exposure="0.9"
              style={{ width: "100%", height: "100%", background: "transparent" }}
            />
            <div className="dock">
              {clips.map((c) => (
                <button key={c} className={c === clip ? "on" : ""} onClick={() => setClip(c)}>
                  {c.replace("-loop", "")}
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className="panel">
          <h2>Validation gate</h2>
          <ul className="checks">
            {checks.map(([key, c]) => (
              <li key={key} className={c.pass ? "" : "fail"}>
                <span className="pill">{c.pass ? "pass" : "fail"}</span>
                <span className="lbl">{checkLabel(key)}</span>
                <span className="mono dim val">{checkDetail(key, c)}</span>
              </li>
            ))}
          </ul>
        </section>

        <div className="cols">
          <section className="panel">
            <h2>Measured locomotion</h2>
            <p className="mono dim small">measured from the mesh by Stage 8, written back to the contract</p>
            <div className="loco">
              {Object.entries(loco).map(([name, l]) => (
                <div className="loco__row" key={name}>
                  <span className="loco__v">{l.recommended_speed_mps}</span>
                  <span className="mono">m/s</span>
                  <span className="mono dim">
                    {l.gait} · {l.cycle_s}s · foot dev {l.stance_foot_dev_mm}mm · drift {l.in_place_drift_m}m
                  </span>
                </div>
              ))}
            </div>
          </section>

          {manifest && (
            <section className="panel">
              <h2>Run manifest</h2>
              <p className="mono dim small">
                {manifest.success ? "success" : "FAILED"} · {manifest.total_seconds}s ·
                pipeline v{manifest.model_versions.pipeline}
              </p>
              <ul className="attempts">
                {manifest.attempts.map((a) => (
                  <li key={a.attempt}>
                    <span className="mono dim">#{a.attempt}</span>
                    <span className="mono">seed {a.seed}</span>
                    <span className="mono dim">{a.seconds}s</span>
                    <span className={"tag " + (a.cache_hit ? "cache" : a.overall_pass ? "ok" : "bad")}>
                      {a.cache_hit ? "CACHE HIT" : a.gate ?? (a.overall_pass ? "PASS" : "FAIL")}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>

        <section className="panel">
          <h2>QA contact sheet</h2>
          <img className="sheet" src={D("qa_contact_sheet.png")} alt="QA contact sheet" loading="lazy" />
        </section>

        <footer className="mono dim">
          creature-forge · independent validator · Khronos {String(report.checks.khronos_gltf_conformance?.errors ?? "—")}/
          {String(report.checks.khronos_gltf_conformance?.warnings ?? "—")}/0/0
        </footer>
      </main>
    </>
  );
}

function Stat({ v, l, sub, accent }: { v: string; l: string; sub?: string; accent?: boolean }) {
  return (
    <div className="stat">
      <span className={"stat__v" + (accent ? " ac" : "")}>{v}</span>
      <span className="stat__l">{l}</span>
      {sub && <span className="stat__sub">{sub}</span>}
    </div>
  );
}
