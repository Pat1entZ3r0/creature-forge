import { Reveal } from "../ui/Reveal";
import { licenseTable, hardwareTable, limitations } from "../data/content";
import { spec } from "../data";

export function Verdict() {
  return (
    <section className="section" id="verdict">
      <span className="section__index">06</span>
      <div className="wrap">
        <div className="section__head">
          <span className="kicker">the honest verdict</span>
          <h2>Realistic — but not as written.</h2>
          <p className="lead">
            The pipeline is realistic in a constrained form, and stages 1, 5, 6, 7 and 8
            were proven here end to end. Stage 3 ran in its deterministic fallback tier;
            nothing in the remaining ML tiers changes a single downstream contract. Here
            is the part most pitch decks leave out.
          </p>
        </div>

        <div className="verdict-cols">
          <Reveal className="verdict-col">
            <h3 className="verdict-col__h">License reality check</h3>
            <span className="mono-label">verified june 2026</span>
            <ul className="lic">
              {licenseTable.map((r) => (
                <li key={r.component} className="lic__row">
                  <span className={`lic__dot${r.ok ? "" : " is-warn"}`} />
                  <div className="lic__main">
                    <span className="lic__name">{r.component}</span>
                    <span className="mono-label">
                      {r.role} · {r.license}
                    </span>
                    <span className={`lic__catch${r.ok ? "" : " danger"}`}>{r.catch}</span>
                  </div>
                </li>
              ))}
            </ul>
          </Reveal>

          <div className="verdict-col">
            <Reveal>
              <h3 className="verdict-col__h">Hardware budget</h3>
              <span className="mono-label">one 24 gb consumer gpu, sequential</span>
              <ul className="hw">
                {hardwareTable.map((r) => (
                  <li key={r.stage} className="hw__row">
                    <span className="hw__vram">{r.vram}</span>
                    <div className="hw__main">
                      <span className="hw__stage">{r.stage}</span>
                      <span className="mono-label">{r.note}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </Reveal>

            <Reveal delay={0.1}>
              <h3 className="verdict-col__h verdict-col__h--mt">Honest limitations</h3>
              <ul className="limits">
                {limitations.map((l, i) => (
                  <li key={i} className="limits__row">
                    <span className="limits__n">{String(i + 1).padStart(2, "0")}</span>
                    {l}
                  </li>
                ))}
              </ul>
            </Reveal>
          </div>
        </div>

        <Reveal className="proven panel panel--corner">
          <span className="kicker">what was actually proven</span>
          <p>
            A {spec.scale_hint.body_length_m}m, 288-triangle, 22-joint, 7-clip spider
            alien whose GLB passes the official Khronos validator at 0/0/0/0 and a
            ten-check semantic gate at 10/10, whose engine speeds are measured rather
            than asserted, and whose Godot integration is written against the exact APIs
            it names. The hard, differentiating layers — rig, animate, package, validate,
            integrate — are the real thing, not mockups.
          </p>
        </Reveal>
      </div>

      <footer className="footer wrap">
        <div className="footer__brand">
          <span className="hero__brand">creature&#8209;forge</span>
          <span className="mono-label">v0.1 · arachnid archetype · seed {spec.seed}</span>
        </div>
        <div className="footer__meta mono-label">
          <span>“{spec.prompt}”</span>
          <span>→ playable godot enemy</span>
        </div>
      </footer>
    </section>
  );
}
