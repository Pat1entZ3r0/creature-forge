import { Reveal } from "../ui/Reveal";
import { checkRows, solverDelta, report } from "../data";

export function Validation() {
  const passed = checkRows.filter((c) => c.pass).length;

  return (
    <section className="section" id="validation">
      <span className="section__index">04</span>
      <div className="wrap">
        <div className="section__head">
          <span className="kicker">stage 8 — the closed loop</span>
          <h2>Don't trust it. Measure it.</h2>
          <p className="lead">
            An independent reader re-parses the GLB from disk, runs CPU forward
            kinematics and linear-blend skinning against the real mesh, and checks ten
            properties. This loop is the single biggest addition over the original
            document — and these two numbers are why it matters.
          </p>
        </div>

        {/* the climax: world-space ground contact, before and after the solver */}
        <div className="solver">
          {solverDelta.map((d, i) => (
            <Reveal key={d.metric} delay={i * 0.1} className="solver__card panel panel--corner">
              <span className="mono-label">{d.metric}</span>
              <div className="solver__row">
                <div className="solver__side solver__side--before">
                  <span className="solver__tag danger">naïve joint-space</span>
                  <span className="solver__val danger">{d.before}</span>
                </div>
                <span className="solver__arrow">→</span>
                <div className="solver__side solver__side--after">
                  <span className="solver__tag">planted-foot solver</span>
                  <span className="solver__val">{d.after}</span>
                </div>
              </div>
              <span className="solver__limit mono-label">
                limit {d.limit} · {d.unit}
              </span>
            </Reveal>
          ))}
        </div>

        <Reveal className="solver__why lead">
          Ground contact is a <mark>world-space constraint</mark>; joint-space keyframes
          cannot promise it — only a gate can. The fix bisects each leg's lift angle
          (44 iterations) until its lowest skinned vertex, computed by exact FK, lands
          on the floor.
        </Reveal>

        {/* the ten-check ledger */}
        <div className="checks">
          <div className="checks__head">
            <span className="mono-label">validation gate</span>
            <span className="checks__score">
              {passed}/{checkRows.length} <i>pass · 0 warnings</i>
            </span>
          </div>
          <ul className="checks__list">
            {checkRows.map((c, i) => (
              <Reveal key={c.key} delay={Math.min(i * 0.04, 0.4)}>
                <li className="check">
                  <span className={`check__pill${c.pass ? "" : " is-fail"}`}>
                    {c.pass ? "pass" : "fail"}
                  </span>
                  <span className="check__label">{c.label}</span>
                  <span className="check__value">{c.value}</span>
                  <span className="check__limit mono-label">{c.limit}</span>
                </li>
              </Reveal>
            ))}
          </ul>
        </div>

        <Reveal className="verdict-band panel panel--corner">
          <span>
            overall <b className={report.overall_pass ? "" : "danger"}>{report.overall_pass ? "PASS" : "FAIL"}</b>
          </span>
          <span className="verdict-band__sep" />
          <span>
            khronos <b>{report.checks.khronos_gltf_conformance.validator}</b> — 0 errors,
            0 warnings, 0 infos, 0 hints
          </span>
        </Reveal>
      </div>
    </section>
  );
}
