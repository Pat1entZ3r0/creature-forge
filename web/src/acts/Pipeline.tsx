import { Reveal } from "../ui/Reveal";
import { stages } from "../data/content";

export function Pipeline() {
  return (
    <section className="section" id="pipeline">
      <span className="section__index">02</span>
      <div className="wrap">
        <div className="section__head">
          <span className="kicker">the corrected architecture</span>
          <h2>Eight stages, end to end.</h2>
          <p className="lead">
            The original document was directionally right and specifically wrong. Each
            stage below carries the correction that keeps a naïve implementation from
            sinking. Five stages are real here; stage 3 runs in its deterministic
            fallback tier — the ML mesh-gen slots into the exact same socket.
          </p>
        </div>

        <ol className="stages">
          {stages.map((s, i) => (
            <Reveal key={s.n} delay={(i % 2) * 0.08} className="stage panel panel--corner">
              <div className="stage__rail">
                <span className="stage__n">{String(s.n).padStart(2, "0")}</span>
                <span className={`tag${s.status === "stub" ? " tag--stub" : ""}`}>
                  {s.status === "stub" ? "stubbed tier" : "real"}
                </span>
              </div>
              <div className="stage__body">
                <h3 className="stage__title">{s.title}</h3>
                <code className="stage__io">{s.io}</code>
                <p className="stage__desc">{s.body}</p>
                <p className="stage__correction">
                  <span className="mono-label">correction</span>
                  {s.correction}
                </p>
                <p className="stage__gate">
                  <span className="stage__gate-dot" /> gate · {s.gate}
                </p>
              </div>
            </Reveal>
          ))}
        </ol>
      </div>
    </section>
  );
}
