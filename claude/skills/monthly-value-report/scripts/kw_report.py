# Kilowott report styling (from the weekly hours report scripts), used by monthly_report.py, after the house style of the
# weekly-status-report and snm-tnm-monthly-report-generator skills (chaits-claude-files repo).
# Every layout rule is an inline style, so the same HTML prints to PDF and survives a paste into Gmail
# (Gmail drops <style> blocks and classes). The <style> block only adds print rules.
# Spacing is tighter than the originals so a week fits on one A4 page.
import html, os, re, subprocess, tempfile

INK, MUTED, RED, PAPER, RULE, CARD = "#0b0f14", "#5b6573", "#e4022d", "#f0ede8", "#e2ded6", "#ffffff"
SANS, SERIF, MONO = "'DM Sans',Arial,sans-serif", "Georgia,'Times New Roman',serif", "'Courier New',Courier,monospace"
# Label chips, from the weekly-status-report palette (background, text)
CHIPS = {"red": ("#fce5ea", "#8a021b"), "blue": ("#e8ebff", "#1a2f99"), "orange": ("#fef0e7", "#b84200"),
         "green": ("#e6f4ed", "#0b5c30"), "grey": (PAPER, MUTED)}
esc = html.escape

def chip(text, colour="grey"):
    bg, fg = CHIPS[colour]
    return (f'<span style="display:inline-block;font-family:{SANS};font-size:9px;font-weight:600;letter-spacing:0.04em;'
            f'background:{bg};color:{fg};border-radius:2px;padding:1px 6px;margin-left:4px;white-space:nowrap;">{esc(text)}</span>')

def para(text):
    return f'<p style="margin:0;font-family:{SANS};font-size:12px;line-height:1.5;color:{INK};">{esc(text)}</p>'

def bullets(items):
    lis = "".join(f'<li style="margin:0 0 2px 0;">{esc(i)}</li>' for i in items)
    return f'<ul style="margin:0;padding-left:18px;font-family:{SANS};font-size:12px;line-height:1.5;color:{INK};">{lis}</ul>'

def cards(items):
    # items: [(value, label)]; a table, not grid/flex, so it stays side by side in Gmail
    w = f"{100 / len(items):.2f}%"
    cells = "".join(
        f'<td style="width:{w};vertical-align:top;background:{CARD};padding:9px 12px;'
        f'{"border-right:1px solid " + RULE + ";" if i < len(items) - 1 else ""}">'
        f'<div style="font-family:{SERIF};font-style:italic;font-size:22px;color:{INK};line-height:1;">{esc(v)}</div>'
        f'<div style="font-family:{SANS};font-size:9px;color:{MUTED};text-transform:uppercase;letter-spacing:0.08em;margin-top:3px;">{esc(l)}</div></td>'
        for i, (v, l) in enumerate(items))
    return (f'<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation" '
            f'style="width:100%;border-collapse:collapse;border:1px solid {RULE};"><tr>{cells}</tr></table>')

def table(cols, rows, total=None):
    # cols: [(header, align, width or None)]; rows: [[cell html]]; total: optional bold last row of cell html
    def cell(c, i, bold=False, top=False):
        a, w = cols[i][1], cols[i][2]
        pad = "5px 8px 5px 0" if i == 0 else ("5px 0 5px 8px" if i == len(cols) - 1 else "5px 8px")
        return (f'<td valign="top" align="{a}" style="font-family:{SANS};font-size:12px;color:{INK};padding:{pad};'
                f'line-height:1.4;{"font-weight:700;" if bold else ""}{"width:" + w + ";" if w else ""}'
                f'{"font-variant-numeric:tabular-nums;" if a != "left" else ""}">{c}</td>')
    head = "".join(
        f'<th align="{a}" style="font-family:{SANS};font-size:10px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;'
        f'color:{INK};padding:{"0 8px 6px 0" if i == 0 else ("0 0 6px 8px" if i == len(cols) - 1 else "0 8px 6px")};'
        f'{"width:" + w + ";" if w else ""}">{esc(h)}</th>'
        for i, (h, a, w) in enumerate(cols))
    body = "".join(f'<tr style="border-bottom:1px solid {RULE};">' + "".join(cell(c, i) for i, c in enumerate(r)) + "</tr>"
                   for r in rows)
    if total:
        body += f'<tr style="border-top:1.5px solid {INK};">' + "".join(cell(c, i, True) for i, c in enumerate(total)) + "</tr>"
    return (f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%;border-collapse:collapse;">'
            f'<thead><tr style="border-bottom:2px solid {INK};">{head}</tr></thead><tbody>{body}</tbody></table>')

def cell_title(name, detail="", tags=""):
    # Bold first line plus a muted detail line, as in the weekly report's task column
    return (f'<div style="font-weight:600;">{esc(name)}{tags}</div>'
            + (f'<div style="font-size:10px;color:#4a5263;line-height:1.35;margin-top:1px;">{esc(detail)}</div>' if detail else ""))

def page(title, eyebrow, sections, footer_left, footer_right, banner=None):
    # sections: [(title, body html)], numbered 01, 02… in order; leave out empty ones before calling
    # A section given as (title, body, True) is kept on one page with its heading (for short tables)
    blocks = "".join(
        (f'<div style="break-inside:avoid;page-break-inside:avoid;">' if len(sec) > 2 and sec[2] else "<div>")
        + f'<div style="padding:0 0 6px 0;"><p style="margin:0;font-family:{MONO};font-size:9.5px;font-weight:700;'
        f'letter-spacing:0.18em;text-transform:uppercase;color:{MUTED};">{n:02d}&nbsp;&nbsp;{esc(sec[0].upper())}</p></div>'
        f'<div style="padding:0 0 18px 0;">{sec[1]}</div></div>'
        for n, sec in enumerate(sections, 1))
    ban = (f'<div style="background:#fce5ea;color:#8a021b;font-family:{SANS};font-size:11px;font-weight:600;padding:6px 10px;'
           f'border-left:3px solid {RED};margin:0 0 12px 0;">{esc(banner)}</div>') if banner else ""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<title>{esc(title)} · {esc(eyebrow.title())}</title>
<style>
@page {{ size: A4; margin: 12mm 14mm; }}
@media print {{
  html {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  body {{ background: {CARD} !important; }}
  .wrap, .card {{ padding: 0 !important; }}
  thead {{ display: table-header-group; }} tr {{ break-inside: avoid; }}
}}
</style></head>
<body style="margin:0;background:{PAPER};font-family:{SANS};color:{INK};">
<div class="wrap" style="padding:24px 16px 32px;">
<div class="card" style="max-width:820px;width:100%;margin:0 auto;background:{CARD};padding:28px 32px;">
<div style="padding:0 0 4px 0;"><span style="font-family:{SANS};font-size:12px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:{INK};">KILOWOTT</span></div>
<div style="padding:0 0 14px 0;border-bottom:2px solid {RED};"></div>
<div style="padding:14px 0 2px 0;"><p style="margin:0;font-family:{SANS};font-size:10px;font-weight:600;letter-spacing:0.16em;text-transform:uppercase;color:{MUTED};">{esc(eyebrow.upper())}</p></div>
<div style="padding:0 0 18px 0;"><h1 style="margin:0;font-family:{SERIF};font-size:26px;font-style:italic;font-weight:400;color:{INK};line-height:1.2;">{esc(title)}</h1></div>
{ban}{blocks}
<div style="border-top:1px solid {INK};padding-top:10px;">
<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
<td style="font-family:{SANS};font-size:11px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:{INK};">{esc(footer_left)}</td>
<td align="right" style="font-family:{SANS};font-size:11px;color:{MUTED};">{esc(footer_right)} &nbsp;·&nbsp; Generated by Kilowott</td>
</tr></table></div>
</div></div></body></html>"""

def write(doc, out, work, max_pages=1):
    # .pdf: print with headless Chrome and report the page count; .html: the Gmail-paste version
    out = os.path.abspath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if out.endswith(".html"):
        open(out, "w", encoding="utf-8").write(doc)
        print(f"{out}  (Gmail: open in Chrome, Ctrl+A, Ctrl+C, paste into the compose window)")
        return
    with tempfile.NamedTemporaryFile("w", suffix=".html", dir=work, delete=False, encoding="utf-8") as fh:
        fh.write(doc)
    subprocess.run(["google-chrome", "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={out}", f"file://{fh.name}"],
                   check=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    os.remove(fh.name)
    pages = int(re.search(r"Pages:\s+(\d+)", subprocess.check_output(["pdfinfo", out], text=True)).group(1))
    print(out)
    print(f"PAGES: {pages}" + (f"  << OVER {max_pages} PAGE(S): flag to the user and ask what to trim" if pages > max_pages else ""))
