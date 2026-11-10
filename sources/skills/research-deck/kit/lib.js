// research-deck kit: visual grammar for research talks. Every helper draws editable PPT shapes.
// Default look = the user's reference deck (Lato, one gold accent). build/theme.json, written by
// template.py from a .pptx/.potx template, overrides colors and fonts and adds the template's
// background and decorations as slide masters.
const path = require("path");
const fs = require("fs");

const FIG = path.join(__dirname, "..", "figures");
const T = {
  font: "Lato",
  ink: "000000",
  gray: "595959",
  past: "44546A",      // labels of steps already shown
  faint: "BFBFBF",
  accent: "A87712",    // the one highlight color (gold by default)
  accentPale: "F6EBD3",
  accent2: "2F4A6D",   // second series in charts
  titleColor: "000000",
  base: "A6A6A6",      // baseline bars
  W: 13.333, H: 7.5, X: 0.45,
};
const THEME = path.join(__dirname, "theme.json");
const TPL = fs.existsSync(THEME) ? JSON.parse(fs.readFileSync(THEME, "utf8")) : null;
if (TPL) Object.assign(T, TPL.T);

// ---------- deck assembly: specs first, so breadcrumbs know "k/n" ----------
const specs = [];
let SECTION = {};
// build.js calls section() before each section file, so every build knows its file and session.
function section(name, session) { SECTION = { section: name, session }; }
// spec: {id?, crumb:[q, part] | null, cite, title, draw(slide, ctx), notes, session?}
function add(spec) { specs.push({ ...SECTION, ...spec }); }

// Stable key per build: <section>/<slug of id|title|crumb>#<n-th build with that slug>.
// Script files are keyed by it, so adding a slide elsewhere does not shift the scripts.
const slug = (t) => t.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 48) || "slide";
function assignKeys() {
  const seen = {};
  specs.forEach((s) => {
    const base = `${s.section}/${slug(s.id || s.title || (s.crumb || []).join(" "))}`;
    seen[base] = (seen[base] || 0) + 1;
    s.key = `${base}#${seen[base]}`;
  });
}

// Template masters: image paths in theme.json are relative to build/.
function defineMasters(pptx) {
  const abs = (o) => {
    const [kind, v] = Object.entries(o)[0];
    return { [kind]: v.path ? { ...v, path: path.join(__dirname, v.path) } : v };
  };
  Object.entries(TPL.masters).forEach(([title, m]) => pptx.defineSlideMaster({
    title, background: m.background.path ? { path: path.join(__dirname, m.background.path) } : m.background, objects: m.objects.map(abs),
  }));
}

function render(pptx, { script = {}, timing = null } = {}) {
  assignKeys();
  if (TPL) defineMasters(pptx);
  // the template's title box, kept inside the band above the content (content starts at y ≈ 1.3)
  const TB = TPL && TPL.titleBox ? { x: TPL.titleBox.x, y: TPL.titleBox.y, w: TPL.titleBox.w, h: Math.min(TPL.titleBox.h, 1.25 - TPL.titleBox.y) } : { x: T.X, y: 0.38, w: 12.45, h: 0.75 };
  const key = (s) => (s.crumb ? s.crumb.join(" · ") : null);
  const totals = {};
  specs.forEach((s) => { const k = key(s); if (k) totals[k] = (totals[k] || 0) + 1; });
  const seen = {};
  specs.forEach((s) => {
    const slide = TPL ? pptx.addSlide({ masterName: s.title ? "CONTENT" : "TITLE" }) : pptx.addSlide();
    if (!TPL) slide.background = { color: "FFFFFF" };
    const k = key(s);
    if (k) {
      seen[k] = (seen[k] || 0) + 1;
      slide.addText(`${k} · ${seen[k]}/${totals[k]}`, {
        x: 7.3, y: 0.1, w: 5.75, h: 0.3, fontFace: T.font, fontSize: 12, color: TPL ? T.titleColor : T.gray, align: "right", margin: 0,
      });
    }
    if (s.title) {
      const size = s.title.length <= 52 ? 30 : s.title.length <= 62 ? 26 : 24;
      slide.addText(s.title, {
        ...TB, fontFace: T.fontHead || T.font, fontSize: size, bold: true, color: T.titleColor, margin: 0, valign: "middle", fit: "none",
      });
    }
    if (s.cite) {
      slide.addText(s.cite, { x: 0.3, y: 7.02, w: 11.9, h: 0.33, fontFace: T.font, fontSize: s.cite.length > 150 ? 10 : 12, color: T.gray, margin: 0, valign: "middle" });
    }
    if (s.number !== false) {
      slide.slideNumber = { x: 12.45, y: 7.02, w: 0.6, h: 0.33, fontFace: T.font, fontSize: 10, color: T.gray, align: "right" };
    }
    s.draw && s.draw(slide, pptx);
    s.onSlide = slideText(slide);
    const body = script[s.key] ?? s.notes;
    const clock = timing && timing.byKey[s.key];
    const notes = [body, clock && `[⏱ ${clock.sec}s · ${mmss(clock.cum)} / ${clock.budget}:00]`].filter(Boolean).join("\n\n");
    if (notes) slide.addNotes(notes);
  });
}

// Visible text of a built slide (for the manifest that script writers read).
function slideText(slide) {
  const flat = (t) => (Array.isArray(t) ? t.map((r) => (typeof r === "string" ? r : r.text || "")).join("") : String(t || ""));
  return (slide._slideObjects || []).flatMap((o) => {
    if (o._type === "text" && o.text) return [flat(o.text)];
    if (o._type === "table" && o.arrTabRows) return o.arrTabRows.map((row) => row.map((c) => flat(c.text)).join(" | "));
    return [];
  }).map((t) => t.trim()).filter(Boolean);
}

// pptxgenjs writes a multi-line note as one <a:t> with raw newlines, which PowerPoint shows as one line.
// Split every notes run into real paragraphs. buf: the .pptx as a Buffer; returns a Buffer.
async function splitNoteParagraphs(buf) {
  const JSZip = require("jszip");
  const zip = await JSZip.loadAsync(buf);
  const names = Object.keys(zip.files).filter((n) => /^ppt\/notesSlides\/notesSlide\d+\.xml$/.test(n));
  for (const n of names) {
    const xml = await zip.file(n).async("string");
    const out = xml.replace(/<a:p><a:r>(<a:rPr[^>]*\/>)<a:t>([^<]*\n[^<]*)<\/a:t><\/a:r>/g, (_, rpr, t) =>
      t.split(/[\r\n]+/).filter(Boolean).map((line, i, all) => `<a:p><a:r>${rpr}<a:t>${line}</a:t></a:r>${i < all.length - 1 ? "</a:p>" : ""}`).join(""));
    zip.file(n, out);
  }
  return zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" });
}

// ---------- spoken script and timing ----------
// Script files: build/script/<lang>/*.md, one "## <key>" heading per build, body = what to say.
function loadScript(dir) {
  const out = {};
  if (!fs.existsSync(dir)) return out;
  fs.readdirSync(dir).filter((f) => f.endsWith(".md")).sort().forEach((f) => {
    let key = null;
    fs.readFileSync(path.join(dir, f), "utf8").replace(/<!--[\s\S]*?-->/g, "").split("\n").forEach((line) => {
      const m = line.match(/^## (\S+)/);
      if (m) { key = m[1]; out[key] = ""; } else if (key) out[key] += line + "\n";
    });
  });
  Object.keys(out).forEach((k) => { out[k] = out[k].trim(); if (!out[k]) delete out[k]; });
  return out;
}

// Speaking-time estimate. ko: Hangul syllables + 1.5 per Latin word + 2 per number, at RATE.ko per minute.
const RATE = { ko: 280, en: 140 };       // ko: syllable units/min, en: words/min (presentation pace)
const CLICK = 1.5;                        // seconds per build for the click and the glance
function speechUnits(t, lang) {
  if (lang === "en") return (t.match(/\S+/g) || []).length;
  return (t.match(/[가-힣]/g) || []).length + 1.5 * (t.match(/[A-Za-z]+/g) || []).length + 2 * (t.match(/\d+(?:[.,]\d+)*/g) || []).length;
}
const mmss = (sec) => `${Math.floor(sec / 60)}:${String(Math.round(sec % 60)).padStart(2, "0")}`;

// talk.sessions: {A: 30, B: 30} minutes; talk.sections: {name: {min}}. A session with no budget
// (e.g. Discussion) is reported but not checked.
function timing(script, lang, { sessions: budgets, sections: targets = {} }) {
  assignKeys();
  const byKey = {}, cum = {}, sum = {};
  specs.forEach((s) => {
    const text = script[s.key] || "";
    const sec = Math.round(text ? (speechUnits(text, lang) / RATE[lang]) * 60 + CLICK : CLICK);
    cum[s.session] = (cum[s.session] || 0) + sec;
    const k = `${s.session}|${s.section}`;
    sum[k] = sum[k] || { session: s.session, section: s.section, builds: 0, scripted: 0, sec: 0 };
    sum[k].builds++; sum[k].sec += sec; if (text) sum[k].scripted++;
    byKey[s.key] = { sec, cum: cum[s.session], budget: budgets[s.session] || "–" };
  });
  const rows = Object.values(sum);
  const lines = ["| session | section | builds | scripted | time | target |", "|---|---|---:|---:|---:|---:|"];
  rows.forEach((r) => {
    const t = budgets[r.session] && targets[r.section] && targets[r.section].min;
    lines.push(`| ${r.session} | ${r.section} | ${r.builds} | ${r.scripted} | ${mmss(r.sec)} | ${t ? mmss(t * 60) : "–"} |`);
  });
  lines.push("");
  Object.entries(cum).forEach(([ss, sec]) => {
    const b = budgets[ss];
    lines.push(b ? `- Session ${ss}: ${mmss(sec)} / ${b}:00 ${sec > b * 60 ? `**over by ${mmss(sec - b * 60)}**` : `(${mmss(b * 60 - sec)} spare)`}` : `- ${ss}: ${mmss(sec)} (no budget)`);
  });
  return { byKey, report: lines.join("\n"), over: Object.entries(cum).some(([ss, sec]) => budgets[ss] && sec > budgets[ss] * 60) };
}

// ---------- images, highlight and dim ----------
function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}

// Fit an image inside box; align "left" | "center". Returns the drawn rect.
function image(slide, name, box, align = "center") {
  const file = path.join(FIG, name);
  const { w, h } = pngSize(file);
  const s = Math.min(box.w / w, box.h / h);
  const r = { w: w * s, h: h * s, y: box.y };
  r.x = align === "left" ? box.x : box.x + (box.w - r.w) / 2;
  slide.addImage({ path: file, ...r });
  return r;
}

const fracToAbs = (r, b, pad = 0.05) => {
  const x0 = Math.max(r.x, r.x + b[0] * r.w - pad), y0 = Math.max(r.y, r.y + b[1] * r.h - pad);
  const x1 = Math.min(r.x + r.w, r.x + b[2] * r.w + pad), y1 = Math.min(r.y + r.h, r.y + b[3] * r.h + pad);
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
};

// White veil over everything in r except the holes (vertical bands × free y-intervals).
function dim(slide, r, holes, opacity = 0.72) {
  const eps = 1e-4;
  const xs = [...new Set([r.x, r.x + r.w, ...holes.flatMap((h) => [h.x, h.x + h.w])])].sort((a, b) => a - b);
  for (let i = 0; i < xs.length - 1; i++) {
    const xa = xs[i], xb = xs[i + 1];
    if (xb - xa < eps) continue;
    const cut = holes.filter((h) => h.x < xb - eps && h.x + h.w > xa + eps).map((h) => [h.y, h.y + h.h]).sort((a, b) => a[0] - b[0]);
    let y = r.y;
    for (const [ya, yb] of [...cut, [r.y + r.h, r.y + r.h]]) {
      if (ya - y > eps) slide.addShape("rect", { x: xa, y, w: xb - xa, h: ya - y, fill: { color: "FFFFFF", transparency: Math.round((1 - opacity) * 100) }, line: { type: "none" } });
      y = Math.max(y, yb);
    }
  }
}

function accentBox(slide, a) {
  slide.addShape("roundRect", { ...a, rectRadius: 0.07, fill: { type: "none" }, line: { color: T.accent, width: 2.25 } });
}

// boxes: one [x0,y0,x1,y1] or a list of them (fractions of the image). null = whole figure, no dim.
function spotlight(slide, r, boxes, { veil = true } = {}) {
  if (!boxes) return;
  const list = Array.isArray(boxes[0]) ? boxes : [boxes];
  const holes = list.map((b) => fracToAbs(r, b));
  if (veil) dim(slide, r, holes);
  holes.forEach((h) => accentBox(slide, h));
}

// ---------- numbered steps ----------
// items: [{label, body}], cur: index shown in full. Past steps keep only the bold label.
function steps(slide, items, cur, box, { onlyCurrent = false, size = 19 } = {}) {
  const runs = [];
  items.forEach((it, i) => {
    if (i > cur || (onlyCurrent && i !== cur)) return;
    const now = i === cur;
    runs.push({ text: `${i + 1}  `, options: { bold: true, color: T.accent } });
    runs.push({ text: it.label, options: { bold: true, color: now ? T.ink : T.past, breakLine: !(now && it.body) } });
    if (now && it.body) runs.push({ text: " " + it.body, options: { color: T.ink, breakLine: true } });
  });
  if (!runs.length) return;
  slide.addText(runs, { ...box, fontFace: T.font, fontSize: size, valign: "top", margin: 0, paraSpaceAfter: 10, lineSpacingMultiple: 1.05 });
}

function remark(slide, text, box, size = 19) {
  slide.addText([
    { text: "Remark: ", options: { bold: true, italic: true } },
    { text, options: { italic: true } },
  ], { ...box, fontFace: T.font, fontSize: size, color: T.ink, valign: "top", margin: 0 });
}

// A figure walked through step by step. One slide per step, plus a Remark slide.
// layout "side": figure left, numbered list right.  "top": wide figure on top, current step below.
function figSeq({ crumb, cite, title, titles, fig, layout = "side", items, remark: rmk, notes = [], figBox, textBox, veil = true }) {
  const side = layout === "side";
  const FB = figBox || (side ? { x: T.X, y: 1.35, w: 7.4, h: 5.45 } : { x: T.X, y: 1.3, w: 12.45, h: 3.75 });
  const TB = textBox || (side ? { x: 8.2, y: 1.45, w: 4.7, h: 5.4 } : { x: T.X, y: 5.3, w: 12.45, h: 1.6 });
  const n = items.length + (rmk ? 1 : 0);
  for (let k = 0; k < n; k++) {
    const isRemark = k === items.length;
    add({
      crumb, cite, title: (titles && titles[k]) || title, notes: notes[k],
      draw: (s) => {
        const r = image(s, fig, FB, side ? "left" : "center");
        if (!isRemark) spotlight(s, r, items[k].box, { veil });
        if (side) {
          // on the Remark slide every step collapses to its label (cur past the end)
          steps(s, items, k, TB);
          if (isRemark) {
            const per = (TB.w * 72) / (19 * 0.5);   // rough chars per line at 19pt Lato
            const lines = items.reduce((n, it) => n + Math.ceil((it.label.length + 3) / per), 0);
            remark(s, rmk, { x: TB.x, y: TB.y + lines * 0.33 + items.length * 0.14 + 0.3, w: TB.w, h: 2.4 });
          }
        } else {
          // text sits right under the figure, not at a fixed y
          const tb = textBox ? TB : { ...TB, y: Math.min(r.y + r.h + 0.35, 5.3) };
          if (isRemark) remark(s, rmk, tb);
          else steps(s, items, k, tb, { onlyCurrent: true });
        }
      },
    });
  }
}

// ---------- charts drawn as shapes ----------
// Vertical bars. bars: [{label, value, color, note}]; reveal: how many are drawn (slots stay fixed).
function bars(slide, box, { bars: B, max, reveal = B.length, title, fmt = (v) => v.toFixed(1), current, labelSize = 14 }) {
  const top = title ? 0.45 : 0;
  if (title) slide.addText(title, { x: box.x, y: box.y, w: box.w, h: 0.4, fontFace: T.font, fontSize: 16, bold: true, color: T.ink, margin: 0, align: "center" });
  const plotY = box.y + top + 0.35, plotH = box.h - top - 0.35 - 0.75;
  const slot = box.w / B.length, bw = Math.min(1.1, slot * 0.6);
  slide.addShape("line", { x: box.x, y: plotY + plotH, w: box.w, h: 0, line: { color: T.gray, width: 1 } });
  B.forEach((b, i) => {
    const cx = box.x + slot * i + slot / 2;
    slide.addText(b.label, { x: cx - slot / 2, y: plotY + plotH + 0.06, w: slot, h: 0.65, fontFace: T.font, fontSize: labelSize, color: i < reveal ? T.ink : T.faint, align: "center", valign: "top", margin: 0 });
    if (i >= reveal) return;
    const h = Math.max(0.02, (b.value / max) * plotH);
    const color = b.color || T.accent2;
    slide.addShape("rect", { x: cx - bw / 2, y: plotY + plotH - h, w: bw, h, fill: { color }, line: { type: "none" } });
    slide.addText(fmt(b.value), { x: cx - slot / 2, y: plotY + plotH - h - 0.38, w: slot, h: 0.36, fontFace: T.font, fontSize: 16, bold: i === current, color: i === current ? T.accent : T.ink, align: "center", valign: "bottom", margin: 0 });
  });
}

// Points joined by a line over categorical x. reveal: number of points drawn.
function linePlot(slide, box, { xs, ys, yMin, yMax, reveal = xs.length, xLabel, yLabel, colors, highlight, fmt = (v) => v.toFixed(2) }) {
  const px = box.x + 0.7, pw = box.w - 0.9, py = box.y + 0.2, ph = box.h - 0.95;
  slide.addShape("line", { x: px, y: py + ph, w: pw, h: 0, line: { color: T.gray, width: 1 } });
  slide.addShape("line", { x: px, y: py, w: 0, h: ph, line: { color: T.gray, width: 1 } });
  const X = (i) => px + pw * (i + 0.5) / xs.length;
  const Y = (v) => py + ph * (1 - (v - yMin) / (yMax - yMin));
  [yMin, (yMin + yMax) / 2, yMax].forEach((v) => slide.addText(String(Math.round(v)), { x: px - 0.6, y: Y(v) - 0.15, w: 0.5, h: 0.3, fontFace: T.font, fontSize: 12, color: T.gray, align: "right", margin: 0 }));
  xs.forEach((x, i) => slide.addText(x, { x: X(i) - 0.6, y: py + ph + 0.08, w: 1.2, h: 0.3, fontFace: T.font, fontSize: 14, color: T.ink, align: "center", margin: 0 }));
  if (xLabel) slide.addText(xLabel, { x: px, y: py + ph + 0.4, w: pw, h: 0.3, fontFace: T.font, fontSize: 14, color: T.gray, align: "center", margin: 0 });
  if (yLabel) slide.addText(yLabel, { x: box.x - 0.2, y: py - 0.45, w: 3, h: 0.3, fontFace: T.font, fontSize: 14, color: T.gray, margin: 0 });
  for (let i = 0; i < Math.min(reveal, ys.length); i++) {
    if (i > 0) {
      const x0 = X(i - 1), y0 = Y(ys[i - 1]), x1 = X(i), y1 = Y(ys[i]);
      slide.addShape("line", { x: Math.min(x0, x1), y: Math.min(y0, y1), w: Math.abs(x1 - x0), h: Math.abs(y1 - y0) || 0.001, flipV: y1 < y0, line: { color: T.accent2, width: 2 } });
    }
    const c = (colors && colors[i]) || (i === highlight ? T.accent : T.accent2);
    slide.addShape("ellipse", { x: X(i) - 0.09, y: Y(ys[i]) - 0.09, w: 0.18, h: 0.18, fill: { color: c }, line: { type: "none" } });
    slide.addText(fmt(ys[i]), { x: i === 0 ? X(i) - 1.35 : X(i) - 0.6, y: i === 0 ? Y(ys[i]) - 0.16 : Y(ys[i]) - 0.48, w: 1.2, h: 0.32, fontFace: T.font, fontSize: 16, bold: i === highlight, color: i === highlight ? T.accent : T.ink, align: "center", margin: 0 });
  }
  return { X, Y };
}

// ---------- tables ----------
// rows revealed one at a time; the current row is pale accent.
function table(slide, box, header, rows, { reveal = rows.length, current = -1, colW, size = 16 } = {}) {
  const cell = (t, o = {}) => ({ text: t, options: { fontFace: T.font, fontSize: size, color: T.ink, valign: "middle", margin: [4, 8, 4, 8], ...o } });
  const data = [header.map((h) => cell(h, { bold: true, color: T.ink, fill: { color: "F2F2F2" } }))];
  rows.slice(0, reveal).forEach((r, i) => data.push(r.map((c) => cell(c, i === current ? { fill: { color: T.accentPale } } : {}))));
  slide.addTable(data, { x: box.x, y: box.y, w: box.w, colW, border: { type: "solid", pt: 0.75, color: "D9D9D9" }, rowH: 0.45 });
}

// ---------- text slides ----------
function text(slide, t, box, o = {}) {
  slide.addText(t, { ...box, fontFace: T.font, fontSize: 19, color: T.ink, margin: 0, valign: "top", ...o });
}

// Q1..Q4 progress chips. state: {answered:[ids], current:id}
function ledger(slide, qs, { answered = [], current } = {}, y = 6.35) {
  const gap = 0.18, w = Math.min(2.9, (12.4 - gap * (qs.length - 1)) / qs.length), x0 = (T.W - (w * qs.length + gap * (qs.length - 1))) / 2;
  qs.forEach((q, i) => {
    const x = x0 + i * (w + gap);
    const isCur = q.id === current, done = answered.includes(q.id);
    slide.addShape("roundRect", { x, y, w, h: 0.5, rectRadius: 0.08, fill: isCur ? { color: T.accent } : { color: "FFFFFF" }, line: { color: isCur ? T.accent : done ? T.gray : T.faint, width: 1 } });
    slide.addText(`${done ? "✓ " : ""}${q.id}  ${q.short}`, { x, y, w, h: 0.5, fontFace: T.font, fontSize: 13, bold: isCur, color: isCur ? "FFFFFF" : done ? T.gray : T.faint, align: "center", valign: "middle", margin: 0 });
  });
}

module.exports = { T, add, section, render, specs, splitNoteParagraphs, loadScript, timing, speechUnits, RATE, CLICK, mmss, image, spotlight, dim, accentBox, fracToAbs, steps, remark, figSeq, bars, linePlot, table, text, ledger };
