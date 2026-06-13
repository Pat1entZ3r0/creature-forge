import { Reveal } from "../ui/Reveal";
import { setup, locomotion } from "../data";

type AnimEvent = { t: number; type: string; hitbox: string };
type Anim = { name: string; events?: AnimEvent[] };

function windowFor(hitboxId: string) {
  for (const a of setup.animations as Anim[]) {
    const ev = a.events ?? [];
    const on = ev.find((e) => e.type === "hitbox_on" && e.hitbox === hitboxId);
    const off = ev.find((e) => e.type === "hitbox_off" && e.hitbox === hitboxId);
    if (on && off) return { clip: a.name, on: on.t, off: off.t };
  }
  return null;
}

export function Contract() {
  const states = Object.keys(setup.state_machine.states);

  return (
    <section className="section" id="contract">
      <span className="section__index">05</span>
      <div className="wrap">
        <div className="section__head">
          <span className="kicker">stage 7 — engine contract</span>
          <h2>The sidecar is the source of truth.</h2>
          <p className="lead">
            <code>godot_setup.json</code> is everything the engine needs and nothing it
            has to guess: collision volumes, bone-attached hitboxes with damage and
            active-time windows, a full animation state machine, and locomotion speeds
            that were <mark>measured from the mesh</mark>, not authored by hand.
          </p>
        </div>

        <div className="contract-grid">
          <Reveal className="card panel panel--corner card--speed">
            <span className="mono-label">measured locomotion · not asserted</span>
            <div className="speed">
              <div className="speed__item">
                <span className="speed__v">{locomotion.walk.recommended_speed_mps}</span>
                <span className="speed__u">m/s</span>
                <span className="speed__l">walk · {locomotion.walk.cycle_s.toFixed(2)}s cycle</span>
              </div>
              <div className="speed__item">
                <span className="speed__v">{locomotion.run.recommended_speed_mps}</span>
                <span className="speed__u">m/s</span>
                <span className="speed__l">run · {locomotion.run.cycle_s.toFixed(2)}s cycle</span>
              </div>
            </div>
            <p className="card__note mono-label">
              measured from foot cadence & stride by the validator, then written back into
              the contract — drift {locomotion.walk.in_place_drift_m} m.
            </p>
          </Reveal>

          <Reveal delay={0.08} className="card panel panel--corner card--vitals">
            <span className="mono-label">combat vitals</span>
            <dl className="kv">
              <div className="kv__row kv__row--hi">
                <dt>health</dt>
                <dd>{setup.health} hp</dd>
              </div>
              <div className="kv__row">
                <dt>collision</dt>
                <dd>
                  capsule r{setup.collision.radius} · h{setup.collision.height}
                </dd>
              </div>
              <div className="kv__row">
                <dt>hurtbox</dt>
                <dd>
                  capsule r{setup.hurtbox.radius} · h{setup.hurtbox.height}
                </dd>
              </div>
              <div className="kv__row">
                <dt>turn speed</dt>
                <dd>{setup.locomotion.turn_speed_dps}°/s</dd>
              </div>
            </dl>
          </Reveal>

          <Reveal delay={0.16} className="card panel panel--corner card--hitboxes">
            <span className="mono-label">bone-attached hitboxes</span>
            <div className="hitboxes">
              {setup.hitboxes.map((h) => {
                const w = windowFor(h.id);
                return (
                  <div key={h.id} className="hitbox">
                    <div className="hitbox__top">
                      <span className="hitbox__id">{h.id}</span>
                      <span className="hitbox__dmg">{h.damage} dmg</span>
                    </div>
                    <span className="mono-label">
                      on “{h.bone}” bone · {h.tags.join(" · ")}
                    </span>
                    {w && (
                      <div className="hitbox__win">
                        <span className="mono-label">
                          {w.clip} · active {w.on}s–{w.off}s
                        </span>
                        <div className="hitbox__bar">
                          <span
                            className="hitbox__bar-on"
                            style={{
                              left: `${(w.on / 0.6) * 100}%`,
                              width: `${((w.off - w.on) / 0.6) * 100}%`,
                            }}
                          />
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </Reveal>

          <Reveal delay={0.24} className="card panel panel--corner card--fsm">
            <span className="mono-label">animation state machine</span>
            <div className="fsm__states">
              {states.map((s) => (
                <span key={s} className={`fsm__state${s === setup.state_machine.start ? " is-start" : ""}${s === "death" ? " is-terminal" : ""}`}>
                  {s}
                </span>
              ))}
            </div>
            <div className="fsm__edges">
              {setup.state_machine.transitions.map(([from, to, x], i) => (
                <span key={i} className="fsm__edge">
                  {from}
                  <i>→</i>
                  {to}
                  <em>{x}s</em>
                </span>
              ))}
            </div>
            <p className="card__note mono-label">{setup.state_machine.note}</p>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
