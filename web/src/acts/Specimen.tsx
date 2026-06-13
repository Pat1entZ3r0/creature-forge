import { useState } from "react";
import { SpiderCanvas } from "../scene/SpiderViewer";
import { clipOrder } from "../data/content";
import { metrics, setup } from "../data";

export function Specimen() {
  const [clip, setClip] = useState<string>("walk-loop");
  const [ps1, setPs1] = useState(true);
  const [wireframe, setWireframe] = useState(false);

  const active = clipOrder.find((c) => c.name === clip) ?? clipOrder[0];

  return (
    <section className="section section--flush" id="specimen">
      <span className="section__index">03</span>
      <div className="wrap">
        <div className="section__head">
          <span className="kicker">live specimen · 134 kb</span>
          <h2>The real GLB, in your browser.</h2>
          <p className="lead">
            Loaded at runtime via the no-editor path, skinned on the GPU, rendered
            through a PS1 shader — clip-space vertex snapping and ordered dither, the
            shader-side half of the look the pipeline defers to the engine. Drag to
            orbit. One-shot states return to idle; death holds its final pose.
          </p>
        </div>
      </div>

      <div className="viewer">
        <div className="viewer__frame panel panel--corner">
          <SpiderCanvas
            clip={clip}
            ps1={ps1}
            wireframe={wireframe}
            controls
            onFinished={setClip}
            className="viewer__canvas"
          />

          <div className="hud hud--tl">
            <span className="mono-label">specimen</span>
            <span className="hud__name">{setup.display_name}</span>
          </div>

          <div className="hud hud--tr">
            <HudStat k="tris" v={`${metrics.triangles}`} />
            <HudStat k="verts" v={`${metrics.vertices}`} />
            <HudStat k="joints" v={`${metrics.joints}`} />
          </div>

          <div className="hud hud--bl">
            <span className="hud__clip">▶ {active.label}</span>
            <span className="mono-label">
              {active.name} · {active.kind}
            </span>
          </div>

          <span className="hud__hint mono-label">drag · scroll to zoom</span>
        </div>

        <aside className="viewer__panel">
          <div className="dock">
            <span className="mono-label">animation clips</span>
            <div className="dock__grid">
              {clipOrder.map((c) => (
                <button
                  key={c.name}
                  className={`dock__btn${c.name === clip ? " is-active" : ""} dock__btn--${c.kind}`}
                  onClick={() => setClip(c.name)}
                >
                  <span className="dock__btn-label">{c.label}</span>
                  <span className="dock__btn-name">{c.name}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="toggles">
            <Toggle label="PS1 shader fx" on={ps1} onClick={() => setPs1((v) => !v)} />
            <Toggle label="wireframe" on={wireframe} onClick={() => setWireframe((v) => !v)} />
          </div>

          <p className="viewer__note mono-label">
            rigid skin · 1 influence / vertex · flat-shaded vertex colors · +Y up · −Z fwd
          </p>
        </aside>
      </div>
    </section>
  );
}

function HudStat({ k, v }: { k: string; v: string }) {
  return (
    <span className="hud__stat">
      <b>{v}</b>
      <i>{k}</i>
    </span>
  );
}

function Toggle({ label, on, onClick }: { label: string; on: boolean; onClick: () => void }) {
  return (
    <button className={`toggle${on ? " is-on" : ""}`} onClick={onClick} role="switch" aria-checked={on}>
      <span className="toggle__track">
        <span className="toggle__knob" />
      </span>
      <span className="toggle__label">{label}</span>
    </button>
  );
}
