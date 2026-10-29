# Report HTML Template

This is the canonical Kilowott monthly report template. Substitute placeholders before writing to disk.
The output must be a complete, self-contained HTML file — no external resource dependencies except Google Fonts.

Section numbering: 01 Summary, 02 Blockers, 03 Value Add, 04 Support Overview, 05 Maintenance Overview,
06 Support & Maintenance Updates, 07 Core Framework Updates (omit if no data), 08 Plugin & Package Updates
(omit if no data), then **one standalone section per qualifying scan category** (e.g. "Security Scan
Findings", "Uptime Scan Findings" — no overarching "Scan Findings" label), then finally Time & Materials
Updates (omit entirely if no T&M tasks). Renumber the visible section labels sequentially if any section
is omitted, so there are no gaps.

Every effort-related column header reads exactly **"Effort (Hr)"** — never "Effort", "Effort Spent", or
any other variant.

The `.card` max-width is generous (see template) so that on any reasonably sized screen the widest table
renders without a horizontal scrollbar. Tables still carry a `min-width` and sit inside a `.table-scroll`
wrapper, so a scrollbar only appears if the viewport itself is narrower than a table's natural width —
never as the default experience on a normal screen.

**Client-facing tone:** this report is read by the client. Never write "the client" or "they" to refer
to the client — anywhere in the document, not just the narrative sections. Use the client's name
directly, or phrase the sentence so no pronoun is needed (e.g. passive voice, or naming the platform/
site instead of the org).

**Gmail-safe rendering:** the intended workflow for sharing this report is opening the `.html` file in
a browser, copying the rendered content, and pasting it into a Gmail compose window. Gmail's compose
editor strips `<style>` blocks and CSS classes from pasted content — it keeps only inline `style`
attributes (and even then drops some properties like `position` and `float`). Flexbox and grid are not
supported in Gmail's rendering either way, so the template never uses them.

Consequence: **the `<style>` block in `<head>` must be treated as a browser/print-only enhancement
layer, never as the sole source of a layout-affecting rule.** Anything that affects spacing, sizing, or
structure has to be duplicated as an inline `style` attribute on the element itself, specifically:

- `margin:0` on every `<h1>` and `<p>` — otherwise default browser margins reappear and break the
  tight vertical rhythm once the `h1, h2, h3, p { margin:0; }` reset is stripped.
- `max-width:820px; width:100%; margin:0 auto; background:#ffffff;` inlined on the `.card` div —
  otherwise it loses its capped width and centering.
- `padding:32px 16px 48px;` inlined on the `.wrap` div — otherwise the outer padding disappears.
- `overflow-x:auto; -webkit-overflow-scrolling:touch;` inlined on every `.table-scroll` wrapper —
  otherwise horizontal scroll on narrow viewports is lost (minor, cosmetic-only fallback).
- `border-collapse:collapse` and `min-width` on every `<table>` — already inline (see below), so no
  action needed here, just don't remove it.

When adding new sections or elements to this template, always add layout-critical inline styles rather
than relying on the class-based rules in `<style>` — the CSS classes (`.wrap`, `.card`, `.table-scroll`)
and the `<style>` block's generic resets should be kept for browser preview and print/PDF fidelity, but
every element must render correctly with the `<style>` block hypothetically deleted.

---

## Full template

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<title>{{PROJECT_NAME}} — {{MONTH_YEAR}} Monthly Summary</title>
<style>
  *, *::before, *::after { box-sizing: border-box; }
  body { margin: 0; background: #f0ede8; font-family: 'DM Sans', Arial, sans-serif; color: #0b0f14; }
  .wrap { padding: 32px 16px 48px; }
  .card { max-width: 820px; width: 100%; margin: 0 auto; background: #ffffff; }
  table { border-collapse: collapse; }
  h1, h2, h3, p { margin: 0; }
  .table-scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }
  /* Real page margins, so every printed page gets top and bottom space, not just the first */
  @page { size: A4; margin: 16mm 14mm; }
  @media print {
    html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    body { background: #ffffff; }
    /* !important beats the inline padding kept for Gmail; print spacing comes from @page instead */
    .wrap, .card { padding: 0 !important; }
    thead { display: table-header-group; }
    tr { break-inside: avoid; }
  }
</style>
</head>
<body>
<div class="wrap" style="padding:32px 16px 48px;">
  <div class="card" style="max-width:820px; width:100%; margin:0 auto; background:#ffffff; padding:40px 40px;">

    <!-- Kilowott wordmark + red rule -->
    <div>
      <div style="padding: 0 0 6px 0;">
        <span style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; font-weight:700; letter-spacing:0.14em; text-transform:uppercase; color:#0b0f14;">KILOWOTT</span>
      </div>
      <div style="padding: 0 0 28px 0; border-bottom: 2px solid #e4022d;"></div>
    </div>

    <!-- Eyebrow + Title -->
    <div style="padding: 24px 0 4px 0;">
      <p style="margin:0; font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.16em; text-transform:uppercase; color:#5b6573;">MONTHLY SUMMARY · {{MONTH_YEAR}}</p>
    </div>
    <div style="padding: 0 0 32px 0;">
      <h1 style="margin:0; font-family:Georgia,'Times New Roman',serif; font-size:32px; font-style:italic; font-weight:400; color:#0b0f14; line-height:1.2;">{{PROJECT_NAME}}</h1>
    </div>

    <!-- ===================== 01 SUMMARY ===================== -->
    <div style="padding: 0 0 8px 0;">
      <p style="margin:0; font-family:'Courier New',Courier,monospace; font-size:10px; font-weight:700; letter-spacing:0.18em; text-transform:uppercase; color:#5b6573;">01 &nbsp;SUMMARY</p>
    </div>
    <div style="padding: 0 0 32px 0;">
      <p style="margin:0; font-family:'DM Sans',Arial,sans-serif; font-size:13px; line-height:1.6; color:#0b0f14;">{{SUMMARY_TEXT}}</p>
    </div>

    <!-- ===================== 02 BLOCKERS ===================== -->
    <div style="padding: 0 0 8px 0;">
      <p style="margin:0; font-family:'Courier New',Courier,monospace; font-size:10px; font-weight:700; letter-spacing:0.18em; text-transform:uppercase; color:#5b6573;">02 &nbsp;BLOCKERS</p>
    </div>
    <div style="padding: 0 0 32px 0;">
      <p style="margin:0; font-family:'DM Sans',Arial,sans-serif; font-size:13px; line-height:1.6; color:#0b0f14;">{{BLOCKERS_TEXT}}</p>
    </div>

    <!-- ===================== 03 VALUE ADD ===================== -->
    <div style="padding: 0 0 8px 0;">
      <p style="margin:0; font-family:'Courier New',Courier,monospace; font-size:10px; font-weight:700; letter-spacing:0.18em; text-transform:uppercase; color:#5b6573;">03 &nbsp;VALUE ADD</p>
    </div>
    <div style="padding: 0 0 32px 0;">
      <p style="margin:0; font-family:'DM Sans',Arial,sans-serif; font-size:13px; line-height:1.6; color:#0b0f14;">{{VALUE_ADD_TEXT}}</p>
    </div>

    <!-- ===================== 04 SUPPORT OVERVIEW ===================== -->
    <!-- Omit any category row with 0 tasks. Always end with a Total row. -->
    <div style="padding: 0 0 20px 0;">
      <p style="margin:0; font-family:'Courier New',Courier,monospace; font-size:10px; font-weight:700; letter-spacing:0.18em; text-transform:uppercase; color:#5b6573;">04 &nbsp;SUPPORT OVERVIEW</p>
    </div>
    <div style="padding:0 0 32px 0; overflow-x:auto; -webkit-overflow-scrolling:touch;" class="table-scroll">
      <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse; min-width:620px;">
        <thead>
          <tr style="border-bottom:2px solid #0b0f14;">
            <th align="left" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.06em; text-transform:uppercase; color:#0b0f14; padding:0 8px 8px 0;">Category</th>
            <th align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.06em; text-transform:uppercase; color:#0b0f14; padding:0 8px 8px;">Open</th>
            <th align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.06em; text-transform:uppercase; color:#0b0f14; padding:0 8px 8px;">In Progress</th>
            <th align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.06em; text-transform:uppercase; color:#0b0f14; padding:0 8px 8px;">Resolved</th>
            <th align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.06em; text-transform:uppercase; color:#0b0f14; padding:0 8px 8px;">Deployed</th>
            <th align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.06em; text-transform:uppercase; color:#0b0f14; padding:0 8px 8px;">Total</th>
            <th align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.06em; text-transform:uppercase; color:#0b0f14; padding:0 0 8px;">Effort (Hr)</th>
          </tr>
        </thead>
        <tbody>
          <!-- REPEAT for each Support category with >0 tasks -->
          <tr style="border-bottom:1px solid #e2ded6;">
            <td style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; color:#0b0f14; padding:10px 8px 10px 0;">{{CATEGORY_NAME}}</td>
            <td align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; color:#0b0f14; padding:10px 8px;">{{OPEN}}</td>
            <td align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; color:#0b0f14; padding:10px 8px;">{{IN_PROGRESS}}</td>
            <td align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; color:#0b0f14; padding:10px 8px;">{{RESOLVED}}</td>
            <td align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; color:#0b0f14; padding:10px 8px;">{{DEPLOYED}}</td>
            <td align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; color:#0b0f14; padding:10px 8px;">{{TOTAL}}</td>
            <td align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; color:#0b0f14; padding:10px 0;">{{EFFORT}}</td>
          </tr>
          <!-- TOTAL ROW (bold, always last) -->
          <tr>
            <td style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; font-weight:700; color:#0b0f14; padding:10px 8px 10px 0;">Total</td>
            <td align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; font-weight:700; color:#0b0f14; padding:10px 8px;">{{TOTAL_OPEN}}</td>
            <td align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; font-weight:700; color:#0b0f14; padding:10px 8px;">{{TOTAL_IN_PROGRESS}}</td>
            <td align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; font-weight:700; color:#0b0f14; padding:10px 8px;">{{TOTAL_RESOLVED}}</td>
            <td align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; font-weight:700; color:#0b0f14; padding:10px 8px;">{{TOTAL_DEPLOYED}}</td>
            <td align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; font-weight:700; color:#0b0f14; padding:10px 8px;">{{GRAND_TOTAL}}</td>
            <td align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; font-weight:700; color:#0b0f14; padding:10px 0;">{{GRAND_TOTAL_EFFORT}}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ===================== 05 MAINTENANCE OVERVIEW ===================== -->
    <!-- Omit any category row with 0 tasks. No Note column. Always end with a Total row (Effort (Hr) only). -->
    <div style="padding: 0 0 20px 0;">
      <p style="margin:0; font-family:'Courier New',Courier,monospace; font-size:10px; font-weight:700; letter-spacing:0.18em; text-transform:uppercase; color:#5b6573;">05 &nbsp;MAINTENANCE OVERVIEW</p>
    </div>
    <div style="padding:0 0 32px 0; overflow-x:auto; -webkit-overflow-scrolling:touch;" class="table-scroll">
      <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse; min-width:520px;">
        <thead>
          <tr style="border-bottom:2px solid #0b0f14;">
            <th align="left" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.06em; text-transform:uppercase; color:#0b0f14; padding:0 8px 8px 0;">Category</th>
            <th align="left" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.06em; text-transform:uppercase; color:#0b0f14; padding:0 8px 8px;">Frequency</th>
            <th align="left" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.06em; text-transform:uppercase; color:#0b0f14; padding:0 8px 8px;">Previous</th>
            <th align="left" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.06em; text-transform:uppercase; color:#0b0f14; padding:0 8px 8px;">Next</th>
            <th align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.06em; text-transform:uppercase; color:#0b0f14; padding:0 0 8px;">Effort (Hr)</th>
          </tr>
        </thead>
        <tbody>
          <!-- REPEAT for each Maintenance category with >0 tasks -->
          <tr style="border-bottom:1px solid #e2ded6;">
            <td style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; color:#0b0f14; padding:10px 8px 10px 0;">{{CATEGORY_NAME}}</td>
            <td style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; color:#0b0f14; padding:10px 8px;">{{FREQUENCY}}</td>
            <td style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; color:#0b0f14; padding:10px 8px; white-space:nowrap;">{{PREVIOUS}}</td>
            <td style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; color:#0b0f14; padding:10px 8px; white-space:nowrap;">{{NEXT}}</td>
            <td align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; color:#0b0f14; padding:10px 0;">{{EFFORT}}</td>
          </tr>
          <!-- TOTAL ROW (bold, always last; only the Effort (Hr) column sums) -->
          <tr>
            <td colspan="4" style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; font-weight:700; color:#0b0f14; padding:10px 8px 10px 0;">Total</td>
            <td align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; font-weight:700; color:#0b0f14; padding:10px 0;">{{TOTAL_EFFORT}}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ===================== 06 SUPPORT & MAINTENANCE UPDATES ===================== -->
    <div style="padding: 0 0 20px 0;">
      <p style="margin:0; font-family:'Courier New',Courier,monospace; font-size:10px; font-weight:700; letter-spacing:0.18em; text-transform:uppercase; color:#5b6573;">06 &nbsp;SUPPORT &amp; MAINTENANCE UPDATES</p>
    </div>
    <div style="padding:0 0 32px 0; overflow-x:auto; -webkit-overflow-scrolling:touch;" class="table-scroll">
      <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse; min-width:560px;">
        <thead>
          <tr style="border-bottom:2px solid #0b0f14;">
            <th align="left" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; color:#0b0f14; padding:0 12px 8px 0; width:60px;">Task ID</th>
            <th align="left" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; color:#0b0f14; padding:0 12px 8px;">Description</th>
            <th align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; color:#0b0f14; padding:0 12px 8px; width:82px;">Status</th>
            <th align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; color:#0b0f14; padding:0 12px 8px; width:64px;">Priority</th>
            <th align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; color:#0b0f14; padding:0 12px 8px; width:72px;">Effort (Hr)</th>
            <th align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; color:#0b0f14; padding:0 0 8px; width:100px;">Date Deployed</th>
          </tr>
        </thead>
        <tbody>
          <!-- REPEAT for each SM task. HIGH priority: color:#e4022d, weight:700. MEDIUM/LOW: color:#5b6573, weight:600. -->
          <!-- Date Deployed cell: show the date ONLY if status = Deployed. Otherwise show "-". -->
          <tr style="border-bottom:1px solid #e2ded6;">
            <td valign="top" style="font-family:'Courier New',Courier,monospace; font-size:12px; font-weight:600; color:#5b6573; padding:10px 12px 10px 0;">SM{{N}}</td>
            <td valign="top" style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; color:#0b0f14; padding:10px 12px; line-height:1.5;">{{DESCRIPTION}}</td>
            <td valign="top" align="center" style="padding:10px 12px;"><span style="display:inline-block; font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; color:#0b0f14; border-radius:2px; padding:2px 8px; letter-spacing:0.04em; white-space:nowrap;">{{STATUS}}</span></td>
            <td valign="top" align="center" style="padding:10px 12px;"><span style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:700; color:#e4022d; white-space:nowrap;">{{PRIORITY}}</span></td>
            <td valign="top" align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:12px; color:#0b0f14; padding:10px 12px; white-space:nowrap;">{{EFFORT}}</td>
            <td valign="top" align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:12px; color:#5b6573; padding:10px 0; white-space:nowrap;">{{DATE_DEPLOYED_OR_DASH}}</td>
          </tr>
          <!-- TOTAL ROW -->
          <tr>
            <td colspan="4" style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; font-weight:700; color:#0b0f14; padding:12px 12px 0 0;">Total Effort (Hr)</td>
            <td align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; font-weight:700; color:#0b0f14; padding:12px 12px 0;">{{SM_TOTAL_EFFORT}}</td>
            <td style="padding:12px 0 0;"></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ===================== 07 CORE FRAMEWORK UPDATES ===================== -->
    <!-- OMIT this entire block if no core framework data is available -->
    <div style="padding: 0 0 20px 0;">
      <p style="margin:0; font-family:'Courier New',Courier,monospace; font-size:10px; font-weight:700; letter-spacing:0.18em; text-transform:uppercase; color:#5b6573;">07 &nbsp;CORE FRAMEWORK UPDATES</p>
    </div>
    <div style="padding: 0 0 32px 0;">
      <p style="margin:0; font-family:'DM Sans',Arial,sans-serif; font-size:13px; line-height:1.6; color:#0b0f14;">{{CORE_FRAMEWORK_TEXT}}</p>
    </div>

    <!-- ===================== 08 PLUGIN & PACKAGE UPDATES ===================== -->
    <!-- OMIT this entire block if no plugin/package data is available -->
    <div style="padding: 0 0 20px 0;">
      <p style="margin:0; font-family:'Courier New',Courier,monospace; font-size:10px; font-weight:700; letter-spacing:0.18em; text-transform:uppercase; color:#5b6573;">08 &nbsp;PLUGIN &amp; PACKAGE UPDATES</p>
    </div>
    <div style="padding:0 0 32px 0; overflow-x:auto; -webkit-overflow-scrolling:touch;" class="table-scroll">
      <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse; min-width:420px;">
        <thead>
          <tr style="border-bottom:2px solid #0b0f14;">
            <th align="left" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.06em; text-transform:uppercase; color:#0b0f14; padding:0 8px 8px 0;">Package</th>
            <th align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.06em; text-transform:uppercase; color:#0b0f14; padding:0 8px 8px;">Installed</th>
            <th align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.06em; text-transform:uppercase; color:#0b0f14; padding:0 8px 8px;">Latest</th>
            <th align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.06em; text-transform:uppercase; color:#0b0f14; padding:0 0 8px;">Status</th>
          </tr>
        </thead>
        <tbody>
          <!-- REPEAT for each package. Status color: Updated=#0b0f14, Stable=#5b6573, Requires Update=#e4022d/700 -->
          <tr style="border-bottom:1px solid #e2ded6;">
            <td style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; color:#0b0f14; padding:10px 8px 10px 0;">{{PACKAGE_NAME}}</td>
            <td align="center" style="font-family:'Courier New',Courier,monospace; font-size:12px; color:#0b0f14; padding:10px 8px;">{{INSTALLED_VERSION}}</td>
            <td align="center" style="font-family:'Courier New',Courier,monospace; font-size:12px; color:#0b0f14; padding:10px 8px;">{{LATEST_VERSION}}</td>
            <td align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; padding:10px 0;">{{STATUS}}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ===================== 09+ SCAN FINDINGS — ONE STANDALONE SECTION PER QUALIFYING SCAN CATEGORY ===================== -->
    <!-- No overarching "Scan Findings" label. Each scan category present in the Maintenance Overview -->
    <!-- (Security Scan / Uptime Scan / Accessibility Scan) gets its own numbered section, titled -->
    <!-- "{{CATEGORY_NAME}} FINDINGS", e.g. "SECURITY SCAN FINDINGS". Omit any category with no findings -->
    <!-- unless the user has explicitly confirmed including it anyway (see SKILL.md Step 5). -->
    <!-- REPEAT this whole block for each qualifying scan category -->
    <div style="padding: 0 0 20px 0;">
      <p style="margin:0; font-family:'Courier New',Courier,monospace; font-size:10px; font-weight:700; letter-spacing:0.18em; text-transform:uppercase; color:#5b6573;">{{N}} &nbsp;{{SCAN_CATEGORY_NAME}} FINDINGS</p>
    </div>
    <div style="padding: 0 0 32px 0;">
      <ol style="margin:0; padding-left:18px; font-family:'DM Sans',Arial,sans-serif; font-size:13px; line-height:1.7; color:#0b0f14;">
        <!-- up to 10 <li> items -->
        <li>{{FINDING}}</li>
      </ol>
    </div>

    <!-- ===================== FINAL SECTION — TIME & MATERIALS UPDATES ===================== -->
    <!-- OMIT entirely if there are no T&M tasks -->
    <div style="padding: 0 0 20px 0;">
      <p style="margin:0; font-family:'Courier New',Courier,monospace; font-size:10px; font-weight:700; letter-spacing:0.18em; text-transform:uppercase; color:#5b6573;">{{N}} &nbsp;TIME &amp; MATERIALS UPDATES</p>
    </div>
    <div style="padding:0 0 40px 0; overflow-x:auto; -webkit-overflow-scrolling:touch;" class="table-scroll">
      <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse; min-width:560px;">
        <thead>
          <tr style="border-bottom:2px solid #0b0f14;">
            <th align="left" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; color:#0b0f14; padding:0 12px 8px 0; width:60px;">Task ID</th>
            <th align="left" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; color:#0b0f14; padding:0 12px 8px;">Description</th>
            <th align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; color:#0b0f14; padding:0 12px 8px; width:82px;">Status</th>
            <th align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; color:#0b0f14; padding:0 12px 8px; width:64px;">Priority</th>
            <th align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; color:#0b0f14; padding:0 12px 8px; width:72px;">Effort (Hr)</th>
            <th align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; color:#0b0f14; padding:0 0 8px; width:100px;">Date Deployed</th>
          </tr>
        </thead>
        <tbody>
          <!-- REPEAT for each TM task, same priority and Date Deployed rules as section 06 -->
          <tr style="border-bottom:1px solid #e2ded6;">
            <td valign="top" style="font-family:'Courier New',Courier,monospace; font-size:12px; font-weight:600; color:#5b6573; padding:10px 12px 10px 0;">TM{{N}}</td>
            <td valign="top" style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; color:#0b0f14; padding:10px 12px; line-height:1.5;">{{DESCRIPTION}}</td>
            <td valign="top" align="center" style="padding:10px 12px;"><span style="display:inline-block; font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:600; color:#0b0f14; border-radius:2px; padding:2px 8px; letter-spacing:0.04em; white-space:nowrap;">{{STATUS}}</span></td>
            <td valign="top" align="center" style="padding:10px 12px;"><span style="font-family:'DM Sans',Arial,sans-serif; font-size:11px; font-weight:700; color:#e4022d; white-space:nowrap;">{{PRIORITY}}</span></td>
            <td valign="top" align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:12px; color:#0b0f14; padding:10px 12px; white-space:nowrap;">{{EFFORT}}</td>
            <td valign="top" align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:12px; color:#5b6573; padding:10px 0; white-space:nowrap;">{{DATE_DEPLOYED_OR_DASH}}</td>
          </tr>
          <!-- TOTAL ROW -->
          <tr>
            <td colspan="4" style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; font-weight:700; color:#0b0f14; padding:12px 12px 0 0;">Total Effort (Hr)</td>
            <td align="center" style="font-family:'DM Sans',Arial,sans-serif; font-size:13px; font-weight:700; color:#0b0f14; padding:12px 12px 0;">{{TM_TOTAL_EFFORT}}</td>
            <td style="padding:12px 0 0;"></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ===================== FOOTER ===================== -->
    <div style="border-top:1px solid #0b0f14; padding-top:16px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="font-family:'DM Sans',Arial,sans-serif; font-size:12px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#0b0f14;">{{PROJECT_NAME}}</td>
          <td align="right" style="font-family:'DM Sans',Arial,sans-serif; font-size:12px; color:#5b6573;">{{MONTH_YEAR_TITLE}} &nbsp;·&nbsp; Generated by Kilowott</td>
        </tr>
      </table>
    </div>

  </div>
</div>
</body>
</html>
```

---

## Notes

- `{{MONTH_YEAR}}` in the eyebrow is uppercase: `JUNE 2026`
- `{{MONTH_YEAR_TITLE}}` in the footer is title case: `June 2026`
- Support category order: Functional Bugs → Performance Issues → Security Issues → Content Changes → Enhancement → Integration Error
- Maintenance category order: Core Updates → Plugin/Package Updates → Security Scan → Uptime Scan → Accessibility Scan
- Status badge background: leave transparent/white, text color `#0b0f14` regardless of value (Open/In Progress/Resolved/Deployed)
- Every effort column header is exactly `Effort (Hr)` — Support Overview, Maintenance Overview, S&M Updates, T&M Updates all use this wording
- "Date Deployed" columns (sections 06, 10) show the date only when `status = Deployed`; every other status shows `-`
- Maintenance Overview has no Note column; it ends in a Total row that sums only the Effort (Hr) column (other cells in that row are blank/colspan)
- Every table is wrapped in `<div class="table-scroll">` with an explicit `min-width` on the `<table>` so narrow viewports scroll horizontally instead of compressing columns
- All padding uses inline `style` attributes (no external CSS classes for table content, aside from `.table-scroll`) to preserve print fidelity
- **Every `<h1>`/`<p>` carries `margin:0` inline, and `.wrap`/`.card`/`.table-scroll` carry their layout-critical rules inline too** — this is required so the report still renders correctly when pasted into Gmail, which strips `<style>` blocks and classes on paste (see "Gmail-safe rendering" above)
- Section numbers are sequential with no gaps. 01–06 are fixed. From 07 onward, number whatever is actually present in order: Core Framework Updates (if any) → Plugin & Package Updates (if any) → one section per qualifying scan category (if any) → Time & Materials Updates (if any, always last). Skip a step in the numbering only by skipping the section entirely — never leave a gap.
