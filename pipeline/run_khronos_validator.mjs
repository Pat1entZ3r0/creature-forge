// Stage-8b: official Khronos glTF 2.0 conformance check (third-party referee).
import { validateBytes } from 'gltf-validator';
import { readFileSync, writeFileSync } from 'fs';

const bytes = new Uint8Array(readFileSync('out/spider_alien.glb'));
const report = await validateBytes(bytes, { uri: 'spider_alien.glb' });
writeFileSync('out/khronos_report.json', JSON.stringify(report, null, 2));
const { errors, warnings, infos, hints } = report.issues;
console.log(`Khronos glTF validator ${report.validatorVersion}`);
console.log(`errors=${errors} warnings=${warnings} infos=${infos} hints=${hints}`);
for (const m of report.issues.messages.slice(0, 12))
  console.log(` [${m.severity}] ${m.code} ${m.pointer ?? ''} ${m.message}`);
