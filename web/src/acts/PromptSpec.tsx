import { Reveal } from "../ui/Reveal";
import { spec } from "../data";

const mandatory = ["units", "up / forward axes", "target scale", "locomotion policy", "seed"];

export function PromptSpec() {
  return (
    <section className="section" id="spec">
      <span className="section__index">01</span>
      <div className="wrap">
        <div className="section__head">
          <span className="kicker">stage 1 — spec compiler</span>
          <h2>The sentence becomes a contract.</h2>
          <p className="lead">
            An LLM fills a strict schema; a non-LLM validator rejects anything out of
            range. The original schema omitted the five fields that silently break a
            mesh in-engine — a spider imported at 100× scale, facing the wrong way,
            sliding on its feet. They are now mandatory.
          </p>
        </div>

        <div className="spec-grid">
          <Reveal className="spec-prompt panel panel--corner">
            <span className="mono-label">natural language in</span>
            <p className="spec-prompt__text">
              {spec.prompt}
              <span className="caret" />
            </p>
            <div className="spec-mandatory">
              <span className="mono-label">now mandatory ↓</span>
              <ul>
                {mandatory.map((m) => (
                  <li key={m}>
                    <span className="tag">+ {m}</span>
                  </li>
                ))}
              </ul>
            </div>
          </Reveal>

          <Reveal delay={0.12} className="spec-json panel panel--corner">
            <span className="mono-label">asset_spec.json out</span>
            <dl className="kv">
              <Row k="style" v={spec.style} />
              <Row k="units" v={spec.units} hi />
              <Row k="up / forward" v={`${spec.axes.up} / ${spec.axes.forward}`} hi />
              <Row k="body length" v={`${spec.scale_hint.body_length_m} m`} hi />
              <Row k="tri budget" v={`${spec.mesh_budget_tris}`} />
              <Row k="texture" v={spec.texture.mode} />
              <Row k="archetype" v={`${spec.rig_archetype} · ${spec.limbs} limbs`} />
              <Row k="locomotion" v="in_place" hi />
              <Row k="target" v={spec.target_engine} />
              <Row k="seed" v={`${spec.seed}`} hi />
            </dl>
            <div className="spec-json__anims">
              <span className="mono-label">animations</span>
              <div className="chips">
                {spec.animations.map((a) => (
                  <span key={a} className="chip">
                    {a}
                  </span>
                ))}
              </div>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

function Row({ k, v, hi }: { k: string; v: string; hi?: boolean }) {
  return (
    <div className={`kv__row${hi ? " kv__row--hi" : ""}`}>
      <dt>{k}</dt>
      <dd>{v}</dd>
    </div>
  );
}
