import { motion } from "motion/react";
import { SpiderCanvas } from "../scene/SpiderViewer";
import { spec, metrics, khronosReport } from "../data";

const item = {
  hidden: { opacity: 0, y: 26 },
  show: { opacity: 1, y: 0 },
};

export function Hero() {
  return (
    <header className="hero" id="top">
      <SpiderCanvas clip="idle-loop" autoRotate className="hero__canvas" />
      <div className="hero__scrim" aria-hidden />

      <div className="hero__top wrap">
        <span className="hero__brand">creature&#8209;forge</span>
        <span className="mono-label">proof of concept · 2026</span>
      </div>

      <motion.div
        className="hero__content wrap"
        initial="hidden"
        animate="show"
        transition={{ staggerChildren: 0.12, delayChildren: 0.15 }}
      >
        <motion.span variants={item} transition={{ duration: 0.6 }} className="kicker">
          prompt → playable godot enemy
        </motion.span>

        <motion.h1 variants={item} transition={{ duration: 0.7 }} className="display hero__title">
          One prompt.
          <br />
          A <mark>rigged,</mark>
          <br />
          validated
          <br />
          specimen.
        </motion.h1>

        <motion.p variants={item} transition={{ duration: 0.7 }} className="lead hero__lead">
          An AI pipeline that compiles a sentence into a fully-rigged, animated,
          engine-ready game enemy — and then <em>proves</em> it with a closed
          validation loop. This is the spider it forged.
        </motion.p>

        <motion.div variants={item} transition={{ duration: 0.7 }} className="hero__prompt">
          <span className="mono-label">test prompt</span>
          <p>“{spec.prompt}”</p>
        </motion.div>

        <motion.div variants={item} transition={{ duration: 0.7 }} className="hero__stats">
          <Stat v={`${metrics.triangles}`} l="triangles" sub={`budget ${spec.mesh_budget_tris}`} />
          <Stat v={`${metrics.joints}`} l="joints" sub={`${spec.limbs} legs`} />
          <Stat v={`${khronosReport.info.animationCount}`} l="clips" sub="all in-place" />
          <Stat v="0/0/0/0" l="khronos" sub="err/warn/info/hint" accent />
        </motion.div>
      </motion.div>

      <a href="#spec" className="hero__scroll" aria-label="scroll">
        <span className="mono-label">scroll</span>
        <span className="hero__scroll-line" />
      </a>
    </header>
  );
}

function Stat({ v, l, sub, accent }: { v: string; l: string; sub?: string; accent?: boolean }) {
  return (
    <div className="stat">
      <span className={`stat__v${accent ? " stat__v--accent" : ""}`}>{v}</span>
      <span className="stat__l">{l}</span>
      {sub && <span className="stat__sub">{sub}</span>}
    </div>
  );
}
