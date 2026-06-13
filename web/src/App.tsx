import "./acts.css";
import { Atmosphere } from "./ui/Atmosphere";
import { Hero } from "./acts/Hero";
import { PromptSpec } from "./acts/PromptSpec";
import { Pipeline } from "./acts/Pipeline";
import { Specimen } from "./acts/Specimen";
import { Validation } from "./acts/Validation";
import { Contract } from "./acts/Contract";
import { Verdict } from "./acts/Verdict";

const rail = [
  ["spec", "01 · spec"],
  ["pipeline", "02 · pipeline"],
  ["specimen", "03 · specimen"],
  ["validation", "04 · validation"],
  ["contract", "05 · contract"],
  ["verdict", "06 · verdict"],
];

export default function App() {
  return (
    <>
      <Atmosphere />

      <nav className="rail" aria-label="sections">
        {rail.map(([id, label]) => (
          <a key={id} href={`#${id}`} className="rail__link">
            <span className="rail__dot" />
            <span className="rail__label">{label}</span>
          </a>
        ))}
      </nav>

      <main>
        <Hero />
        <PromptSpec />
        <Pipeline />
        <Specimen />
        <Validation />
        <Contract />
        <Verdict />
      </main>
    </>
  );
}
