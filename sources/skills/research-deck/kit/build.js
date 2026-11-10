// node build/build.js [--lang ko|en] [section ...]
// Writes out/<deck>.pptx, out/manifest.json (every build: key, visible text, notes, script) and out/timing.md.
const fs = require("fs");
const path = require("path");
const PptxGenJS = require("pptxgenjs");
const { render, section, specs, splitNoteParagraphs, loadScript, timing } = require("./lib");
const TALK = require("./talk");

const args = process.argv.slice(2);
const li = args.indexOf("--lang");
const lang = li >= 0 ? args.splice(li, 2)[1] : TALK.scriptLang;
const only = args;
const sections = only.length ? only : Object.keys(TALK.sections);
sections.forEach((s) => { section(s, TALK.sections[s].session); require(`./${s}`)(); });

const script = loadScript(path.join(__dirname, "script", lang));
const clock = timing(script, lang, TALK);

const pptx = new PptxGenJS();
pptx.layout = "LAYOUT_WIDE";
pptx.title = TALK.title;
pptx.author = TALK.author;
render(pptx, { script, timing: clock });

const OUT = path.join(__dirname, "out");
fs.mkdirSync(OUT, { recursive: true });
const known = new Set(specs.map((s) => s.key));
const stale = Object.keys(script).filter((k) => !known.has(k));
fs.writeFileSync(path.join(OUT, "manifest.json"), JSON.stringify(specs.map((s, i) => ({
  n: i + 1, key: s.key, session: s.session, section: s.section, title: s.title || null,
  crumb: s.crumb || null, cite: s.cite || null, onSlide: s.onSlide, notes: s.notes || null, script: script[s.key] || null,
})), null, 1));
fs.writeFileSync(path.join(OUT, "timing.md"), `# Timing (${lang})\n\n${clock.report}\n`);
console.log(clock.report.split("\n").filter((l) => l.startsWith("- ")).join("\n"));
if (stale.length) console.warn(`script keys with no slide (${stale.length}):`, stale.join(", "));
if (clock.over) console.warn("over budget: cut builds from the storyline's cut list, or shorten the script");

const name = only.length ? `draft-${only.join("+")}` : "deck";
const out = path.join(OUT, `${name}.pptx`);
pptx.write({ outputType: "nodebuffer" }).then(splitNoteParagraphs).then((b) => { fs.writeFileSync(out, b); console.log("wrote", out); });
