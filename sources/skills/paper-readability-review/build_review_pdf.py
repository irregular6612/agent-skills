#!/usr/bin/env python3
"""build_review_pdf.py — Paper Review PDF builder (readability + venue-specific quality review).

Usage:
    python3 build_review_pdf.py \
        --input paper.pdf \
        --readability readability.json \
        --quality quality.json [quality_venue2.json ...] \
        --output paper_review.pdf

Schemas: agents/readability.md, agents/quality.md.
"""
from __future__ import annotations

import argparse
import html
import io
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("ERROR: PyMuPDF not installed. Run: pip install pymupdf")


# Constants
MARGIN_W = 340
PAGE_W_ORIG = 612
PAGE_H = 792
TOP_Y = 56
BOTTOM_Y = 770

DEFAULT_FONTFILE = os.path.expanduser("~/.fonts/NanumGothic.ttf")
NANUMGOTHIC_URL = (
    "https://github.com/google/fonts/raw/main/ofl/nanumgothic/"
    "NanumGothic-Regular.ttf"
)
FONT_ALIAS = "kor"

COLORS: dict[str, dict[str, Any]] = {
    "logic":  {"hl": (0.55, 0.80, 1.00), "fill": (0.90, 0.95, 1.00), "label": "논리·구조"},
    "recall": {"hl": (1.00, 0.65, 0.65), "fill": (1.00, 0.93, 0.93), "label": "질문 회수"},
    "flow":   {"hl": (1.00, 0.88, 0.40), "fill": (1.00, 0.97, 0.82), "label": "읽힘"},
    "ai":     {"hl": (0.80, 0.70, 1.00), "fill": (0.96, 0.93, 1.00), "label": "AI 문체"},
}

# id -> (short name, color group). Mirrors the table in agents/readability.md.
CRITERIA: dict[int, tuple[str, str]] = {
    1: ("논리성", "logic"),
    2: ("두괄식", "logic"),
    3: ("비전문가 접근성", "flow"),
    4: ("단어 선택", "flow"),
    5: ("AI 문체", "ai"),
    6: ("압축도", "flow"),
    7: ("연결성", "flow"),
    8: ("절 내부 흐름", "logic"),
    9: ("질문 회수", "recall"),
    10: ("기여–결과 대응", "recall"),
}


def crit_label(cid: int) -> str:
    return f"C{cid} {CRITERIA[cid][0]}"

PRIORITY_LABEL = {"highest": "★ 최우선", "high": "▲ 중요", "normal": None}
PRIORITY_COLOR = {
    "highest": (0.85, 0.15, 0.15),
    "high":    (0.85, 0.45, 0.05),
    "normal":  (0.5, 0.5, 0.5),
}
PRIORITY_RANK = {"highest": 0, "high": 1, "normal": 2}


def ensure_font(fontfile: str) -> str:
    if fontfile and Path(fontfile).is_file():
        return fontfile
    target = Path(DEFAULT_FONTFILE)
    if target.is_file():
        return str(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"[font] downloading NanumGothic → {target}")
    urllib.request.urlretrieve(NANUMGOTHIC_URL, target)
    return str(target)


def estimate_text_lines(text: str, fontsize: float, body_width: float) -> int:
    char_w = fontsize * 0.95
    chars_per_line = max(1, int(body_width / char_w))
    n = 0
    for line in (text or "").split("\n"):
        n += max(1, (len(line) + chars_per_line - 1) // chars_per_line)
    return n


def card_height(diagnosis: str, alt: str, fontsize: float, body_width: float) -> float:
    line_h = fontsize * 1.32
    n_lines = (
        estimate_text_lines(diagnosis, fontsize, body_width)
        + 1
        + estimate_text_lines("→ 수정: " + alt, fontsize, body_width)
    )
    pad = 5
    header = 18
    return header + 2 + n_lines * line_h + 2 * pad


def fit_card_to_slot(diagnosis: str, alt: str, slot_h: float,
                     body_width: float = 290.0,
                     base_fontsize: float = 8.0) -> tuple[float, float]:
    for fs in [base_fontsize, 7.5, 7.0, 6.5]:
        h = card_height(diagnosis, alt, fs, body_width)
        if h <= slot_h - 4:
            return fs, h
    return 6.5, card_height(diagnosis, alt, 6.5, body_width)


def draw_card(page, y_top: float, height: float, fontsize: float,
              cid: int, priority: str,
              diagnosis: str, alt: str, font: str, fontfile: str) -> None:
    color = COLORS[CRITERIA[cid][1]]
    label = crit_label(cid)
    fill = color["fill"]
    hl = color["hl"]

    x0 = PAGE_W_ORIG + 12
    x1 = PAGE_W_ORIG + MARGIN_W - 12

    label_rect = fitz.Rect(x0, y_top, x0 + 92, y_top + 16)
    page.draw_rect(label_rect, color=hl, fill=hl, width=0)
    page.insert_textbox(label_rect, label, fontsize=9.0, color=(0, 0, 0),
                        align=fitz.TEXT_ALIGN_CENTER,
                        fontname=font, fontfile=fontfile)

    pri_label = PRIORITY_LABEL.get(priority)
    if pri_label:
        pri_rect = fitz.Rect(x0 + 96, y_top, x1, y_top + 16)
        page.insert_textbox(pri_rect, pri_label, fontsize=8.5,
                            color=PRIORITY_COLOR[priority],
                            align=fitz.TEXT_ALIGN_LEFT,
                            fontname=font, fontfile=fontfile)

    body_top = y_top + 18
    body_rect = fitz.Rect(x0, body_top, x1, y_top + height)
    page.draw_rect(body_rect, color=hl, fill=fill, width=0.6)

    pad = 5
    text_rect = fitz.Rect(x0 + pad, body_top + pad,
                          x1 - pad, y_top + height - pad)
    body_text = f"{diagnosis}\n\n→ 수정: {alt}"
    page.insert_textbox(text_rect, body_text, fontsize=fontsize,
                        color=(0.05, 0.05, 0.05),
                        fontname=font, fontfile=fontfile,
                        align=fitz.TEXT_ALIGN_LEFT)


# ---------------------------------------------------------------------------
# HTML-rendered pages (cover, scorecard, venue review). fitz.Story handles
# wrapping and pagination, which hand-placed insert_textbox cannot.
# No background-color in CSS: Story repaints every background on every page,
# so a filled cell on page 1 bleeds onto page 2+. Use borders/text color.
# ---------------------------------------------------------------------------

def e(x: Any) -> str:
    return html.escape(str(x if x is not None else ""))


CSS = """
@font-face { font-family: kor; src: url(%s); }
* { font-family: kor; }
body { font-size: 9.5pt; line-height: 1.45; color: #111; }
h1 { font-size: 19pt; margin: 0 0 4pt 0; }
h2 { font-size: 13.5pt; margin: 14pt 0 5pt 0; padding-bottom: 2pt; border-bottom: 1px solid #999; }
h3 { font-size: 11pt; margin: 9pt 0 3pt 0; }
p { margin: 2pt 0 5pt 0; }
.sub { color: #666; font-size: 10pt; }
.box { border: 1px solid #999; padding: 7pt; margin: 6pt 0; }
.big { font-size: 22pt; font-weight: bold; }
.muted { color: #666; }
table { border-collapse: collapse; width: 100%%; margin: 4pt 0 8pt 0; }
th { font-weight: bold; text-align: left; padding: 3pt; border: 1px solid #999; border-bottom: 2px solid #555; font-size: 8.8pt; }
td { padding: 3pt; border: 1px solid #ccc; vertical-align: top; font-size: 8.8pt; }
.fatal { color: #c01818; font-weight: bold; }
.major { color: #c86000; font-weight: bold; }
.minor { color: #777; }
.good { color: #1a7a1a; font-weight: bold; }
.mid { color: #b07000; font-weight: bold; }
.bad { color: #c01818; font-weight: bold; }
ul { margin: 2pt 0 5pt 0; }
li { margin-bottom: 2pt; }
"""


def html_to_doc(body: str, fontfile: str) -> "fitz.Document":
    """Render an HTML body to a Letter-size PDF (multi-page as needed)."""
    archive = fitz.Archive(os.path.dirname(fontfile))
    css = CSS % os.path.basename(fontfile)
    story = fitz.Story(html=body, user_css=css, archive=archive)
    buf = io.BytesIO()
    writer = fitz.DocumentWriter(buf)
    mediabox = fitz.Rect(0, 0, PAGE_W_ORIG, PAGE_H)
    where = mediabox + (54, 54, -54, -54)
    more = 1
    while more:
        dev = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()
    return fitz.open("pdf", buf.getvalue())


def score_class(v: float) -> str:
    return "good" if v >= 75 else "mid" if v >= 60 else "bad"


def overall_score(scores: list[dict]) -> float:
    """Readability total out of 100 from the 10 per-criterion scores."""
    return sum(x["score"] for x in scores) / len(scores)


def venue_of(qd: dict) -> str:
    return qd.get("venue") or "ICML"


def b_labels(qds: list[dict]) -> list[str]:
    """'B' for a single venue review, 'B-1', 'B-2', ... for several."""
    return ["B"] if len(qds) == 1 else [f"B-{i}" for i in range(1, len(qds) + 1)]


def front_matter_html(title: str, rd: dict, qds: list[dict], n_cards: int) -> str:
    total = overall_score(rd["scores"])
    labels = b_labels(qds)
    b_names = " · ".join(f"{lab}. {e(venue_of(qd))} 리뷰" for lab, qd in zip(labels, qds))

    h = [f"<h1>{e(title)}</h1>",
         f'<p class="sub">Paper Review · A. 가독성 (10개 기준) · {b_names} — 각 평가는 서로 맥락을 공유하지 않는 독립 에이전트가 작성</p>']

    h.append('<div class="box"><h3>A. 가독성</h3>'
             f'<p><span class="big {score_class(total)}">{total:.0f}</span> / 100 (10개 기준 평균)</p>'
             f'<p>{e(rd.get("one_line_diagnosis"))}</p></div>')

    for lab, qd in zip(labels, qds):
        fatal = [x for x in qd.get("ac_priorities", []) if x.get("severity") == "fatal"]
        top3 = sorted(qd.get("ac_priorities", []), key=lambda x: x.get("rank", 99))[:3]
        h.append(f'<div class="box"><h3>{lab}. {e(venue_of(qd))} 리뷰</h3>'
                 f'<p><b>{e(qd.get("verdict_one_line"))}</b></p>'
                 f'<p class="muted">fatal {len(fatal)}건 · 우선순위 상위 3:</p><ul>')
        for x in top3:
            sev = e(x.get("severity", ""))
            h.append(f'<li><span class="{sev}">[{sev}]</span> {e(x.get("weakness"))}</li>')
        h.append("</ul></div>")

    h.append("<h2>목차</h2><ul>"
             "<li>A-1. 가독성 점수표와 질문 회수표</li>"
             f"<li>A-2. 원문 위 부분 피드백 카드 ({n_cards}건, 우측 마진)</li>"
             "<li>A-3. 수정 로드맵 (우선순위순)</li>"
             + "".join(f"<li>{lab}. {e(venue_of(qd))} 리뷰: 구성 평가 · 핵심 claim ↔ evidence · 반례 질문 · 결정권자 우선순위 · 표현 vs 구조</li>"
                       for lab, qd in zip(labels, qds))
             + "</ul>")

    h.append("<h2>카드 범례</h2><table><tr><th>색</th><th>기준</th></tr>")
    for g, col in COLORS.items():
        rgb = "#%02x%02x%02x" % tuple(int(c * 255) for c in col["hl"])
        ids = ", ".join(crit_label(i) for i, (_, gg) in CRITERIA.items() if gg == g)
        h.append(f'<tr><td><span style="color:{rgb}">■</span> {e(col["label"])}</td><td>{e(ids)}</td></tr>')
    h.append("</table><p class=\"muted\">★ 최우선 = 글 전체 이해를 막음 · ▲ 중요 = 해당 절 이해를 막음 · 뱃지 없음 = 다듬으면 좋음</p>")

    # A-1 scorecard (new page)
    h.append('<h2 style="page-break-before: always">A-1. 가독성 점수표</h2>'
             '<p class="muted">모든 점수는 높을수록 좋음. 90+ 손볼 곳 거의 없음 · 75–89 국소 수정 · 60–74 문단 재작성 · 40–59 절 재구성 · &lt;40 구조 재작성</p>'
             "<table><tr><th>기준</th><th>점수</th><th>핵심</th></tr>")
    for x in sorted(rd["scores"], key=lambda x: x["id"]):
        v = x["score"]
        h.append(f'<tr><td>{e(crit_label(x["id"]))}</td><td class="{score_class(v)}">{v}</td>'
                 f'<td>{e(x.get("verdict"))}</td></tr>')
    h.append(f'<tr><td><b>총점</b></td><td class="{score_class(total)}"><b>{total:.0f}</b></td><td>10개 기준 평균</td></tr></table>')

    h.append("<h3>기준별 근거와 가장 효과 큰 수정</h3>")
    for x in sorted(rd["scores"], key=lambda x: x["score"]):
        h.append(f'<p><b>{e(crit_label(x["id"]))} ({x["score"]})</b> — {e(x.get("evidence"))}<br/>'
                 f'→ {e(x.get("top_fix"))}</p>')

    qm = rd.get("question_map", [])
    if qm:
        mark = {"answered": ('good', '회수'), "partial": ('mid', '부분'), "missing": ('bad', '미회수')}
        h.append("<h3>질문 회수표 (C9·C10)</h3><table><tr><th>던진 질문 / 기여</th><th>위치</th><th>답한 곳</th><th>상태</th></tr>")
        for q in qm:
            cls, lab = mark.get(q.get("status"), ("minor", e(q.get("status"))))
            h.append(f'<tr><td>{e(q.get("question"))}</td><td>{e(q.get("source"))}</td>'
                     f'<td>{e(q.get("answered_in"))}</td><td class="{cls}">{lab}</td></tr>')
        h.append("</table>")
    return "".join(h)


def quality_html(qd: dict, label: str = "B") -> str:
    h = [f'<h1>{label}. {e(venue_of(qd))} 리뷰</h1>',
         '<p class="sub">가독성 평가와 맥락을 공유하지 않는 독립 리뷰어 작성</p>',
         f'<p class="muted">심사 기준: {e(qd.get("venue_basis") or "내장 프로필")}</p>',
         f'<div class="box"><p><b>{e(qd.get("verdict_one_line"))}</b></p>'
         f'<p class="muted">리뷰어가 이해한 논문: {e(qd.get("summary"))}</p></div>']

    org = qd.get("organization", {})
    h.append(f"<h2>1. 핵심 약점 기준 구성 평가</h2><p>{e(org.get('assessment'))}</p><table>"
             "<tr><th>#</th><th>약점</th><th>위치</th><th>구성과의 관계</th></tr>")
    for w in org.get("weaknesses", []):
        h.append(f"<tr><td>{e(w.get('rank'))}</td><td>{e(w.get('title'))}</td>"
                 f"<td>{e(w.get('where'))}</td><td>{e(w.get('why'))}</td></tr>")
    h.append("</table>")

    h.append("<h2>2. 핵심 claim 3개와 필요한 evidence</h2>")
    for c in qd.get("claims", []):
        req = "".join(f"<li>{e(r)}</li>" for r in c.get("required_evidence", []))
        h.append(f"<h3>{e(c.get('id'))}. {e(c.get('claim'))}</h3>"
                 f"<p class=\"muted\">{e(c.get('where'))}</p>"
                 # Stacked, not a 3-column table: evidence lists run long and
                 # narrow columns wrap them one word per line.
                 f"<p><b>필요한 evidence</b></p><ul>{req}</ul>"
                 f"<p><b>제시된 evidence</b> — {e(c.get('provided_evidence'))}</p>"
                 f"<p><b>gap</b> — <span class=\"bad\">{e(c.get('gap'))}</span></p>")

    h.append("<h2>3. Soundness를 흔드는 반례 질문</h2><ol>")
    for q in qd.get("soundness_questions", []):
        h.append(f"<li><b>[{e(q.get('targets'))}]</b> {e(q.get('question'))}<br/>"
                 f"<span class=\"muted\">답하지 못하면: {e(q.get('if_unanswered'))}</span></li>")
    h.append("</ol>")

    h.append("<h2>4. 결정권자(AC·편집자) 관점 치명적 약점 (우선순위순)</h2><table>"
             "<tr><th>#</th><th>심각도</th><th>약점</th><th>결정권자가 보는 이유</th><th>최소 처방</th></tr>")
    for x in sorted(qd.get("ac_priorities", []), key=lambda x: x.get("rank", 99)):
        sev = e(x.get("severity", ""))
        h.append(f"<tr><td>{e(x.get('rank'))}</td><td class=\"{sev}\">{sev}</td>"
                 f"<td>{e(x.get('weakness'))}</td><td>{e(x.get('why_ac_cares'))}</td>"
                 f"<td>{e(x.get('minimal_fix'))}</td></tr>")
    h.append("</table>")

    h.append("<h2>5. 표현 지적 vs reject 근거가 될 구조적 약점</h2>"
             "<h3>5-a. 구조적 약점 (reject 근거)</h3><table>"
             "<tr><th>위치</th><th>약점</th><th>reject 근거인 이유</th><th>처방</th></tr>")
    for x in qd.get("structural_weaknesses", []):
        h.append(f"<tr><td>{e(x.get('where'))}</td><td>{e(x.get('issue'))}</td>"
                 f"<td>{e(x.get('why_reject'))}</td><td>{e(x.get('fix'))}</td></tr>")
    h.append("</table><h3>5-b. 표현 지적 (reject 근거 아님)</h3><table>"
             "<tr><th>위치</th><th>문제</th><th>제안</th></tr>")
    for x in qd.get("presentation_issues", []):
        h.append(f"<tr><td>{e(x.get('where'))}</td><td>{e(x.get('issue'))}</td>"
                 f"<td>{e(x.get('suggestion'))}</td></tr>")
    h.append("</table>")
    return "".join(h)


def add_roadmap_page(doc, annotations: list[dict],
                     font: str, fontfile: str) -> None:
    ranked = sorted(
        enumerate(annotations, 1),
        key=lambda x: PRIORITY_RANK.get(x[1].get("priority", "normal"), 2)
    )
    page = doc.new_page(width=952, height=PAGE_H)
    page.insert_textbox(fitz.Rect(60, 60, 892, 100),
                        "A-3. 수정 로드맵 — 우선순위 순서",
                        fontsize=20, color=(0, 0, 0),
                        fontname=font, fontfile=fontfile)
    page.insert_textbox(fitz.Rect(60, 105, 892, 130),
                        "위에서 아래로 작업하면 가독성 개선 효과가 가장 큽니다.",
                        fontsize=11, color=(0.4, 0.4, 0.4),
                        fontname=font, fontfile=fontfile)
    y = 140
    h = 60
    for i, (orig_idx, ann) in enumerate(ranked, 1):
        if y + h > 770:
            page = doc.new_page(width=952, height=PAGE_H)
            page.insert_textbox(fitz.Rect(60, 60, 892, 100),
                                "수정 로드맵 (cont'd)",
                                fontsize=16, color=(0, 0, 0),
                                fontname=font, fontfile=fontfile)
            y = 110
        cid = ann["criterion"]
        pri = ann.get("priority", "normal")
        c = COLORS[CRITERIA[cid][1]]
        rect = fitz.Rect(60, y, 892, y + h)
        page.draw_rect(rect, color=c["hl"], fill=c["fill"], width=0.5)
        page.draw_rect(fitz.Rect(60, y, 150, y + h),
                       color=c["hl"], fill=c["hl"], width=0)
        page.insert_textbox(fitz.Rect(60, y + h/2 - 8, 150, y + h/2 + 8),
                            crit_label(cid), fontsize=9, color=(0, 0, 0),
                            fontname=font, fontfile=fontfile,
                            align=fitz.TEXT_ALIGN_CENTER)
        phrase = ann["phrase"]
        header = f"#{i:02d}  ·  p.{ann['page']}  ·  '{phrase[:60]}{'...' if len(phrase) > 60 else ''}'"
        if PRIORITY_LABEL.get(pri):
            header += f"   {PRIORITY_LABEL[pri]}"
        page.insert_textbox(fitz.Rect(160, y + 4, 882, y + 18),
                            header, fontsize=9.5, color=(0.15, 0.15, 0.15),
                            fontname=font, fontfile=fontfile)
        diag = ann["diagnosis"]
        alt = ann["rewrite"]
        body = (
            f"{diag[:130]}{'...' if len(diag) > 130 else ''}\n"
            f"→ 수정: {alt[:160]}{'...' if len(alt) > 160 else ''}"
        )
        # insert_textbox is all-or-nothing: on overflow it returns a negative
        # value and writes NOTHING. Korean full-width glyphs wrap to ~4 lines
        # here, so shrink the font until the body actually fits the slot.
        body_rect = fitz.Rect(160, y + 19, 882, y + h - 4)
        for bfs in (8.0, 7.5, 7.0, 6.5, 6.0):
            rc = page.insert_textbox(body_rect, body, fontsize=bfs,
                                     color=(0, 0, 0),
                                     fontname=font, fontfile=fontfile)
            if rc >= 0:
                break
        y += h + 4


def validate(rd: dict, qds: list[dict]) -> None:
    ids = sorted(x["id"] for x in rd["scores"])
    if ids != list(range(1, 11)):
        sys.exit(f"ERROR: readability scores must cover ids 1-10, got {ids}")
    for x in rd["scores"]:
        if not 0 <= x["score"] <= 100:
            sys.exit(f"ERROR: score out of range for C{x['id']}: {x['score']}")
    for a in rd["annotations"]:
        if a.get("criterion") not in CRITERIA:
            sys.exit(f"ERROR: unknown criterion {a.get('criterion')!r} in card '{a.get('phrase', '')[:40]}'")
    for qd in qds:
        if len(qd.get("claims", [])) != 3:
            print(f"  [WARN] {venue_of(qd)}: expected 3 claims, got {len(qd.get('claims', []))}")


def build(input_pdf: str, readability_json: str, quality_jsons: list[str],
          output_pdf: str, fontfile: str = DEFAULT_FONTFILE) -> None:
    rd = json.loads(Path(readability_json).read_text(encoding="utf-8"))
    qds = [json.loads(Path(q).read_text(encoding="utf-8")) for q in quality_jsons]
    validate(rd, qds)
    annotations = rd["annotations"]
    fontfile = ensure_font(fontfile)

    title = (rd.get("paper_title") or qds[0].get("paper_title")
             or Path(input_pdf).stem.replace("_", " "))

    doc = fitz.open(input_pdf)

    for page in doc:
        old = page.rect
        new = fitz.Rect(0, 0, old.width + MARGIN_W, old.height)
        page.set_mediabox(new)
        page.set_cropbox(new)

    by_page: dict[int, list[dict]] = {}
    for ann in annotations:
        page_idx = ann["page"] - 1
        by_page.setdefault(page_idx, []).append(ann)

    body_width = (PAGE_W_ORIG + MARGIN_W - 12) - (PAGE_W_ORIG + 12) - 10

    n_warnings = 0
    for page_idx, anns in by_page.items():
        if page_idx >= len(doc):
            print(f"  [WARN] page {page_idx + 1} out of range")
            continue
        page = doc[page_idx]
        n = len(anns)
        available = BOTTOM_Y - TOP_Y
        gap = 4
        slot_h = (available - (n - 1) * gap) / n

        for i, ann in enumerate(anns):
            phrase = ann["phrase"]
            cid = ann["criterion"]
            pri = ann.get("priority", "normal")
            diag = ann["diagnosis"]
            alt = ann["rewrite"]

            hits = page.search_for(phrase)
            if not hits:
                print(f"  [WARN] page {page_idx + 1}: phrase not found: '{phrase[:50]}'")
                n_warnings += 1
                continue
            # search_for() splits a matched phrase into per-word fragments
            # (one Rect per word, possibly across lines). Highlight ALL of
            # them — using only hits[0] colors just the first word — and union
            # them into hl_rect so the connector line anchors to the full span.
            color = COLORS[CRITERIA[cid][1]]

            highlight = page.add_highlight_annot(hits)
            highlight.set_colors(stroke=color["hl"])
            pri_tag = f"[{PRIORITY_LABEL[pri]}] " if PRIORITY_LABEL.get(pri) else ""
            highlight.set_info(content=f"{pri_tag}[{crit_label(cid)}] {diag}\n\n→ 수정: {alt}")
            highlight.update()

            hl_rect = hits[0]
            for h in hits[1:]:
                hl_rect = hl_rect | h

            target_y = TOP_Y + i * (slot_h + gap)
            fontsize, ch = fit_card_to_slot(diag, alt, slot_h, body_width=body_width)
            draw_card(page, target_y, ch, fontsize, cid, pri,
                      diag, alt, FONT_ALIAS, fontfile)

            line_y_src = (hl_rect.y0 + hl_rect.y1) / 2
            line_y_dst = target_y + 8
            page.draw_line(
                fitz.Point(hl_rect.x1 + 2, line_y_src),
                fitz.Point(PAGE_W_ORIG + 12, line_y_dst),
                color=(0.5, 0.5, 0.5), width=0.5
            )
            print(f"  ✓ p{page_idx + 1} [{crit_label(cid)}|fs={fontsize}|"
                  f"h={ch:.0f}/slot={slot_h:.0f}] {phrase[:40]}")

    add_roadmap_page(doc, annotations, FONT_ALIAS, fontfile)
    for lab, qd in zip(b_labels(qds), qds):
        doc.insert_pdf(html_to_doc(quality_html(qd, lab), fontfile))
    doc.insert_pdf(html_to_doc(front_matter_html(title, rd, qds, len(annotations)), fontfile),
                   start_at=0)

    doc.save(output_pdf, garbage=4, deflate=True)
    doc.close()

    sz = os.path.getsize(output_pdf)
    print(f"\n저장: {output_pdf} ({sz / 1024:.1f} KB)")
    if n_warnings:
        print(f"⚠ {n_warnings} warning(s) — check phrase matching")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a paper review PDF (readability + venue quality review)")
    ap.add_argument("--input", "-i", required=True, help="Input paper PDF")
    ap.add_argument("--readability", "-r", required=True,
                    help="Readability agent JSON (agents/readability.md)")
    ap.add_argument("--quality", "-q", required=True, nargs="+",
                    help="Quality agent JSON(s), one per venue (agents/quality.md)")
    ap.add_argument("--output", "-o", required=True, help="Output review PDF")
    ap.add_argument("--fontfile", default=DEFAULT_FONTFILE, help="CJK TTF path")
    args = ap.parse_args()
    build(args.input, args.readability, args.quality, args.output, args.fontfile)


if __name__ == "__main__":
    main()
