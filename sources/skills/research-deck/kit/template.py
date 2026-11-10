#!/usr/bin/env python3
"""Read a .pptx/.potx template into build/theme.json + build/template/ for the research-deck kit.

usage: python3 template.py <template.pptx|.potx> <talk>/build

What it keeps: slide size (16:9 only, scaled to 13.333 x 7.5 in), theme colors and fonts,
the background and the non-placeholder pictures/shapes/text of the master and of two layouts
(TITLE for the title slide, CONTENT for everything else), the title placeholder box and color.
What it drops: placeholders other than the title, effects, gradients, unsupported shapes
(listed under "warnings"). Standard library only.
"""
import colorsys, json, posixpath, sys, zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
EMU, W0, H0 = 914400, 13.333, 7.5
RID = "{%s}embed" % NS["r"]
warnings = []


def rels(z, part):
    d, f = posixpath.split(part)
    rp = f"{d}/_rels/{f}.rels"
    if rp not in z.namelist():
        return {}
    out = {}
    for r in ET.fromstring(z.read(rp)):
        t = r.get("Target")
        out[r.get("Id")] = (t if r.get("TargetMode") == "External" else posixpath.normpath(posixpath.join(d, t)), r.get("Type").rsplit("/", 1)[1])
    return out


def scheme_colors(theme):
    out = {}
    for el in theme.find(".//a:clrScheme", NS):
        name = el.tag.split("}")[1]
        c = el[0]
        out[name] = c.get("val") if c.tag.endswith("srgbClr") else c.get("lastClr", "000000")
    for k, v in {"bg1": "lt1", "tx1": "dk1", "bg2": "lt2", "tx2": "dk2"}.items():
        out[k] = out.get(v)
    return out


def adjust(hexc, el):
    """Apply lumMod/lumOff/tint/shade children of a color element (approximate)."""
    r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    for m in el:
        v = int(m.get("val", "100000")) / 100000
        tag = m.tag.split("}")[1]
        if tag == "lumMod": l *= v
        elif tag == "lumOff": l += v
        elif tag == "tint": l = l + (1 - l) * (1 - v)
        elif tag == "shade": l *= v
    r, g, b = colorsys.hls_to_rgb(h, min(max(l, 0), 1), s)
    return "%02X%02X%02X" % tuple(round(x * 255) for x in (r, g, b))


def color_of(fill_parent, scheme):
    """Color of the first srgbClr/schemeClr/sysClr under an element (solidFill, bgRef, ...)."""
    if fill_parent is None:
        return None
    for el in fill_parent.iter():
        tag = el.tag.split("}")[1]
        if tag == "srgbClr": return adjust(el.get("val"), el)
        if tag == "schemeClr" and scheme.get(el.get("val")): return adjust(scheme[el.get("val")], el)
        if tag == "sysClr": return el.get("lastClr")
    return None


class Reader:
    def __init__(self, z, scheme, scale, outdir):
        self.z, self.scheme, self.s, self.outdir = z, scheme, scale, outdir

    def media(self, part, rid):
        target = rels(self.z, part).get(rid, (None,))[0]
        if not target or target not in self.z.namelist():
            warnings.append(f"{part}: image {rid} not found"); return None
        name = posixpath.basename(target)
        (self.outdir / name).write_bytes(self.z.read(target))
        return f"template/{name}"

    def background(self, part, root):
        bg = root.find("p:cSld/p:bg", NS)
        if bg is None:
            return None
        blip = bg.find(".//a:blip", NS)
        if blip is not None:
            p = self.media(part, blip.get(RID))
            return {"path": p} if p else None
        c = color_of(bg, self.scheme)
        return {"color": c} if c else None

    def box(self, xfrm, tf):
        off, ext = xfrm.find("a:off", NS), xfrm.find("a:ext", NS)
        x, y = tf(int(off.get("x")), int(off.get("y")))
        x2, y2 = tf(int(off.get("x")) + int(ext.get("cx")), int(off.get("y")) + int(ext.get("cy")))
        k = self.s / EMU
        return {"x": round(x * k, 3), "y": round(y * k, 3), "w": round((x2 - x) * k, 3), "h": round((y2 - y) * k, 3)}

    def shapes(self, part, tree, tf=lambda x, y: (x, y)):
        out = []
        for el in tree:
            tag = el.tag.split("}")[1]
            xfrm = el.find("p:spPr/a:xfrm", NS) if tag != "grpSp" else el.find("p:grpSpPr/a:xfrm", NS)
            if tag == "grpSp" and xfrm is not None:
                o, e = xfrm.find("a:off", NS), xfrm.find("a:ext", NS)
                co, ce = xfrm.find("a:chOff", NS), xfrm.find("a:chExt", NS)
                sx = int(e.get("cx")) / max(int(ce.get("cx")), 1); sy = int(e.get("cy")) / max(int(ce.get("cy")), 1)
                inner = (lambda o, co, sx, sy: lambda x, y: tf(int(o.get("x")) + (x - int(co.get("x"))) * sx, int(o.get("y")) + (y - int(co.get("y"))) * sy))(o, co, sx, sy)
                out += self.shapes(part, el, inner)
                continue
            if xfrm is None or el.find(".//p:nvPr/p:ph", NS) is not None:
                continue
            b = self.box(xfrm, tf)
            if tag == "pic":
                blip = el.find(".//a:blip", NS)
                p = blip is not None and self.media(part, blip.get(RID))
                if p: out.append({"image": {**b, "path": p}})
            elif tag in ("sp", "cxnSp"):
                geom = el.find("p:spPr/a:prstGeom", NS)
                prst = geom.get("prst") if geom is not None else "custom"
                sp = el.find("p:spPr", NS)
                fill = None if sp.find("a:noFill", NS) is not None else color_of(sp.find("a:solidFill", NS), self.scheme)
                ln = sp.find("a:ln", NS)
                line = color_of(ln.find("a:solidFill", NS), self.scheme) if ln is not None else None
                text = "".join(t.text or "" for t in el.iter("{%s}t" % NS["a"])).strip()
                if prst in ("line", "straightConnector1") or tag == "cxnSp":
                    out.append({"line": {**b, "line": {"color": line or "000000", "width": 1}}})
                elif text:
                    rpr = el.find(".//a:rPr", NS)
                    size = int(rpr.get("sz")) / 100 * self.s if rpr is not None and rpr.get("sz") else 12
                    out.append({"text": {"text": text, "options": {**b, "fontSize": round(size, 1), "color": color_of(rpr, self.scheme) if rpr is not None else None, "fill": {"color": fill} if fill else None, "margin": 0}}})
                elif fill:
                    if prst != "rect":
                        warnings.append(f"{part}: '{prst}' shape drawn as a rectangle")
                    out.append({"rect": {**b, "fill": {"color": fill}, **({"line": {"color": line}} if line else {})}})
                elif prst != "rect" or line:
                    warnings.append(f"{part}: skipped unfilled '{prst}' shape")
        return out


def placeholder(root, kinds):
    for sp in root.iter("{%s}sp" % NS["p"]):
        ph = sp.find("p:nvSpPr/p:nvPr/p:ph", NS)
        if ph is not None and ph.get("type") in kinds:
            return sp
    return None


def main(src, build):
    build = Path(build)
    outdir = build / "template"
    outdir.mkdir(parents=True, exist_ok=True)
    z = zipfile.ZipFile(src)
    pres = ET.fromstring(z.read("ppt/presentation.xml"))
    sz = pres.find("p:sldSz", NS)
    W, H = int(sz.get("cx")) / EMU, int(sz.get("cy")) / EMU
    if abs(W / H - 16 / 9) > 0.02:
        sys.exit(f"template is {W:.2f} x {H:.2f} in (not 16:9). The kit lays out 16:9 only; ask the user for a 16:9 version.")
    scale = W0 / W

    master = next(n for n in z.namelist() if n.startswith("ppt/slideMasters/slideMaster") and n.endswith(".xml"))
    mroot = ET.fromstring(z.read(master))
    mrels = rels(z, master)
    theme = next(t for t, k in mrels.values() if k == "theme")
    troot = ET.fromstring(z.read(theme))
    scheme = scheme_colors(troot)
    fonts = {k: troot.find(f".//a:fontScheme/a:{k}Font/a:latin", NS).get("typeface") for k in ("major", "minor")}
    rd = Reader(z, scheme, scale, outdir)

    layouts = {}
    for target, kind in mrels.values():
        if kind == "slideLayout":
            layouts.setdefault(ET.fromstring(z.read(target)).get("type", "cust"), target)
    pick = {"TITLE": ["title", "ctrTitle"], "CONTENT": ["titleOnly", "obj", "tx"]}
    masters, title_box, title_color = {}, None, None
    mbg = rd.background(master, mroot)
    mshapes = rd.shapes(master, mroot.find("p:cSld/p:spTree", NS))
    for name, prefs in pick.items():
        part = next((layouts[t] for t in prefs if t in layouts), None)
        objs, bg = list(mshapes), mbg
        if part:
            lroot = ET.fromstring(z.read(part))
            if lroot.get("showMasterSp") == "0":
                objs = []
            bg = rd.background(part, lroot) or mbg
            objs += rd.shapes(part, lroot.find("p:cSld/p:spTree", NS))
        else:
            warnings.append(f"no {name} layout; using the master alone")
        masters[name] = {"background": bg or {"color": scheme.get("lt1", "FFFFFF")}, "objects": objs}
        if name == "CONTENT":
            for root in ([ET.fromstring(z.read(part))] if part else []) + [mroot]:
                sp = placeholder(root, ("title",))
                if sp is not None and title_box is None and sp.find("p:spPr/a:xfrm", NS) is not None:
                    title_box = rd.box(sp.find("p:spPr/a:xfrm", NS), lambda x, y: (x, y))
                if sp is not None and title_color is None:
                    title_color = color_of(sp.find(".//a:defRPr", NS), scheme)
    title_color = title_color or color_of(mroot.find("p:txStyles/p:titleStyle/a:lvl1pPr/a:defRPr", NS), scheme) or scheme.get("dk1")

    def lum(c):
        ch = [int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        ch = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in ch]
        return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]
    contrast = lambda a, b: (max(lum(a), lum(b)) + 0.05) / (min(lum(a), lum(b)) + 0.05)
    bg = (masters["CONTENT"]["background"] or {}).get("color", scheme.get("lt1", "FFFFFF"))
    accents = [scheme[f"accent{i}"] for i in range(1, 7) if scheme.get(f"accent{i}")]
    readable = [c for c in accents if contrast(c, bg) >= 3] or ["A87712"]
    if readable[0] != accents[0]:
        warnings.append(f"accent1 {accents[0]} is hard to read on {bg}; using {readable[0]}")
    pale = adjust(readable[0], ET.fromstring('<x xmlns="%s"><tint val="20000"/></x>' % NS["a"]))
    if title_box and title_box["y"] + title_box["h"] > 1.35:
        warnings.append(f"title area ends at y={title_box['y'] + title_box['h']:.2f} in; kit content starts at 1.3–1.6 in. Check the render for overlap.")

    out = {
        "source": str(Path(src).resolve()), "size_in": [round(W, 3), round(H, 3)], "scale": round(scale, 4),
        "T": {"font": fonts["minor"], "fontHead": fonts["major"], "ink": scheme.get("dk1", "000000"),
              "accent": readable[0], "accentPale": pale, "accent2": (readable[1:] or [scheme.get("dk2", "2F4A6D")])[0],
              "titleColor": title_color, "bg": bg},
        "titleBox": title_box, "masters": masters, "colors": scheme, "warnings": warnings,
    }
    (build / "theme.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"theme.json: font {fonts['minor']} / {fonts['major']}, accent {readable[0]}, "
          f"TITLE {len(masters['TITLE']['objects'])} objects, CONTENT {len(masters['CONTENT']['objects'])} objects, scale {scale:.3f}")
    for w in warnings:
        print("warning:", w)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
