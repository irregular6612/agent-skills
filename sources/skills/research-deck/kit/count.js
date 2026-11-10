// node build/count.js <section> [lang]   e.g. node build/count.js s2_q1
// Speaking time of one section's script against its target, per build. Reads out/manifest.json
// (run build.js once first) so it never touches the pptx.
const fs = require("fs");
const path = require("path");
const { speechUnits, RATE, CLICK, mmss } = require("./lib");
const TALK = require("./talk");

const [sec, lang = "ko"] = process.argv.slice(2);
const file = path.join(__dirname, "script", lang, `${sec}.md`);
const body = {};
let key = null;
fs.readFileSync(file, "utf8").replace(/<!--[\s\S]*?-->/g, "").split("\n").forEach((l) => {
  const m = l.match(/^## (\S+)/);
  if (m) { key = m[1]; body[key] = ""; } else if (key) body[key] += l + "\n";
});
const builds = JSON.parse(fs.readFileSync(path.join(__dirname, "out", "manifest.json"), "utf8")).filter((b) => b.section === sec);
let total = 0;
builds.forEach((b) => {
  const t = (body[b.key] || "").trim();
  const s = Math.round(t ? (speechUnits(t, lang) / RATE[lang]) * 60 + CLICK : CLICK);
  if (b.session === TALK.sections[sec].session) total += s;
  console.log(`${String(b.n).padStart(3)}  ${String(s).padStart(3)}s  ${t ? "" : "MISSING "}${b.key}`);
});
const extra = Object.keys(body).filter((k) => !builds.some((b) => b.key === k));
if (extra.length) console.log("unknown keys:", extra.join(", "));
const target = TALK.sections[sec].min * 60;
console.log(`total ${mmss(total)} / target ${mmss(target)}  (${total > target ? "over" : "under"} by ${mmss(Math.abs(total - target))})`);
