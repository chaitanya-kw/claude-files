/**
 * Allocation sync — Google Apps Script for the capacity planning sheet.
 *
 * Keeps the "Allocation" tab in step with "Projects import", "Allocations import"
 * and "People" without retyping project or person names. Rows and columns are
 * keyed (project_id / person_name) and only ever inserted, never rebuilt, so the
 * What-if values you type stay attached to the right project and person.
 *
 * INSTALL
 *   1. In the sheet: Extensions → Apps Script. Paste this file into Code.gs and save.
 *   2. In the Apps Script editor: Services (+) → Drive API → Add. This is needed to read
 *      the timesheet xlsx files. Copies of the sheet keep this setting.
 *   3. Reload the sheet. A "Planning" menu appears.
 *   4. Planning → Set up sheet. Creates Summary, Settings, Projects import,
 *      Allocations import, Logged import and People. Safe to re-run: it only adds
 *      what is missing and never overwrites data.
 *   5. On Settings, paste the three Drive folder links (projects, allocations, timesheets).
 *   6. List the people you plan for on People (person_email helps match timesheet rows).
 *   7. Planning → Sync allocation.
 *
 * SHARING WITH OTHER PMs
 *   Set up a blank copy as a template. File → Make a copy duplicates this script
 *   and its Drive API setting, so each PM gets their own sheet and Planning menu.
 *   Each PM then fills in their own Settings folders.
 *
 * WEEKLY USE
 *   1. Run the project-snapshot and actuals-snapshot skills. They upload their CSVs
 *      to the projects and allocations folders.
 *   2. Upload the Monday timesheet xlsx to the timesheets folder. The name doesn't matter.
 *   3. Planning → Sync allocation. It loads the newest projects and allocations CSVs,
 *      reads any timesheet files it hasn't seen yet, rebuilds Logged import for the
 *      planning month, then syncs the grid.
 *   When the month in Summary!D1 changes, Sync asks before clearing the what-if values.
 *
 * HOW TIMESHEETS ARE COMBINED
 *   Each xlsx is read once; its entries are kept in the hidden "_timesheet_log" tab.
 *   Files are identified by their contents, not their names: if two files contain
 *   the same day, that day's entries come from the file exported most recently
 *   (export time from the xlsx metadata, else its Drive upload time). Entries with an
 *   approval status containing "reject" are ignored. "_timesheet_files" lists every
 *   file read and the dates it covered; delete a row there to make Sync re-read that file.
 *
 * IMPORT REQUIREMENT (only when pasting CSVs by hand)
 *   project_id must be stored as text. It is an 18-digit number and Sheets silently
 *   rounds numbers that long. Untick "Convert text to numbers, dates, and formulas"
 *   when importing, or format the column as Plain text first. Sync stops with an
 *   error if it finds numbers. Imports from Drive handle this automatically.
 *
 * LAYOUT ("Allocation" tab — created and maintained by this script)
 *   Row 1 (hidden)  keys: person_name over each column pair, T:* over the totals block,
 *                   B1 = month the grid was last synced for
 *   Row 2           title
 *   Row 3           person name, merged across that person's pair
 *   Row 4           "Actual" | "What-if"
 *   Rows 5..        one row per project. A (hidden) = project_id, B = name, C = active|gone.
 *                   Sync keeps them ordered: other projects, presales, T&M, then gone —
 *                   alphabetical within each group (whole rows move, What-if values with them)
 *   Footer row      per-column totals over active projects (A = __TOTAL__)
 *   Capacity row    each person's effective_capacity_hrs from People (A = __CAPACITY__).
 *                   On People, effective_capacity_hrs = monthly_capacity_hrs − leave_hr_mgmt_hrs_mtd
 *                   (hours off for leave, management or HR — not allocations)
 *   Remaining row   capacity minus the Actual / What-if totals, red when over (A = __REMAINING__)
 *
 * SUMMARY CAPACITY CHECK (Summary!C3:D12, rewritten by every Sync)
 *   Total capacity, total budget (active projects), capacity − budget, team
 *   allocation (actual / what-if, excluding people not on People), spare capacity,
 *   hours allocated to people not on People, and active projects with no budget
 *   (T&M and presales projects often have none, so capacity − budget can look
 *   better than it is).
 *
 * WHAT-IF RULE
 *   A blank What-if cell means "no change" (the Actual value is used).
 *   Type 0 to plan someone off a project. Total what-if and the footer under
 *   each What-if column follow this rule.
 *
 * ACTUAL VALUES ARE WRITTEN BY SYNC, NOT BY FORMULAS
 *   Matching on 18-digit IDs must be done as text, which Sheets formulas can't
 *   do reliably. Actual cells therefore only change when Sync runs.
 *
 * READING PLANNED TOTALS FROM OTHER TABS (e.g. Capacity, person name in A3)
 *   What-if total: =INDEX(Allocation!$1:$2000, MATCH("__TOTAL__", Allocation!$A:$A, 0), MATCH($A3, Allocation!$1:$1, 0) + 1)
 *   Actual total:  same formula with + 0 instead of + 1
 */

const CONFIG = {
  ALLOC_SHEET: 'Allocation',
  PROJECTS_SHEET: 'Projects import',
  ALLOCATIONS_SHEET: 'Allocations import',
  LOGGED_SHEET: 'Logged import',
  PEOPLE_SHEET: 'People',
  SETTINGS_SHEET: 'Settings',
  TS_LOG_SHEET: '_timesheet_log',
  TS_FILES_SHEET: '_timesheet_files',
  MONTH_CELL: 'Summary!D1',
};

const ROW_KEY = 1;
const ROW_TITLE = 2;
const ROW_PERSON = 3;
const ROW_KIND = 4;
const FIRST_DATA_ROW = 5;
const COL_KEY = 1;
const COL_PROJECT = 2;
const COL_STATUS = 3;
const FIRST_PERSON_COL = 4;
const MONTH_KEY_CELL = 'B1';

const KIND_ACTUAL = 'Actual';
const KIND_WHATIF = 'What-if';
const FOOTER_KEY = '__TOTAL__';
const CAPACITY_KEY = '__CAPACITY__';   // row under the footer: effective capacity per person
const REMAINING_KEY = '__REMAINING__'; // row under that: capacity minus allocation
const CAPACITY_HEADER = 'effective_capacity_hrs'; // People column read for capacity
const MONTHLY_HEADER = 'monthly_capacity_hrs';
// Hours taken off a person's capacity for leave, management or HR work. They are
// not allocations; they only reduce effective capacity.
const DEDUCTION_HEADER = 'leave_hr_mgmt_hrs_mtd';
const OLD_DEDUCTION_HEADERS = ['leave_taken_hrs_mtd']; // renamed to DEDUCTION_HEADER on setup/sync
const SUMMARY_FIRST_ROW = 3; // Summary!C3:D12 holds the capacity check block
const STATUS_ACTIVE = 'active';
const STATUS_GONE = 'gone';

// Allocation rows are grouped in this order, alphabetical within each group.
// Gone projects (no longer in Projects import) sort after all of them.
const CATEGORY = { OTHER: 0, PRESALES: 1, TM: 2, GONE: 3 };

// Offsets into the totals block, which sits to the right of the person pairs.
const T = { OTHER: 0, ACT: 1, WIF: 2, BUD: 3, REM_A: 4, REM_W: 5 };
const TOTAL_COLS = [
  { key: 'T:OTHER', label: 'Other (not in People)' },
  { key: 'T:ACT', label: 'Total actual' },
  { key: 'T:WIF', label: 'Total what-if' },
  { key: 'T:BUD', label: 'Budget (hrs)' },
  { key: 'T:REM_A', label: 'Remaining (actual)' },
  { key: 'T:REM_W', label: 'Remaining (what-if)' },
];

// Headers written by setupSheet(). Sync only reads the columns it needs by name,
// so the full export headers are listed here just to match what gets pasted.
const PROJECTS_HEADERS = [
  'project_id', 'project_name', 'project_key', 'status', 'status_label', 'stage',
  'engagement_model', 'skills_required', 'client_name', 'account_manager',
  'invoicing_type', 'priced_by_finance', 'start_date', 'end_date', 'estimated_hours',
  'ballpark_hours', 'monthly_budget', 'percent_complete', 'csat', 'assigned_to',
  'project_folder', 'url_live', 'url_staging', 'git_hub', 'project_manager',
  'description', 'risk_category', 'seo', 'sold_hours', 'contract', 'delivery_tier',
  'roas', 'quality', 'design_adherence', 'sm_engagement', 'uat_report',
  're_allocation_note', 'internal_delivery_date', 'uat_date', 'designers',
  'completed_time', 'hsid',
];
const ALLOCATIONS_HEADERS = [
  'project_id', 'project_name', 'person_name', 'person_zpuid', 'person_email',
  'allocated_hours', 'export_month',
];
const LOGGED_HEADERS = [
  'project_id', 'project_name', 'person_name', 'person_email', 'logged_hours', 'export_month',
];
const PEOPLE_HEADERS = [
  'person_name', 'person_email', 'monthly_capacity_hrs', 'leave_hr_mgmt_hrs_mtd',
  'effective_capacity_hrs', 'notes',
];

const SETTINGS = [
  ['projects_folder', 'Drive folder (link or ID) the project-snapshot skill uploads to'],
  ['allocations_folder', 'Drive folder (link or ID) the actuals-snapshot skill uploads to'],
  ['timesheets_folder', 'Drive folder (link or ID) where the weekly timesheet xlsx files go'],
];
const TS_LOG_HEADERS = ['file_id', 'exported_at', 'date', 'project_key', 'email', 'user', 'hours'];
const TS_FILES_HEADERS = ['file_id', 'file_name', 'exported_at', 'first_date', 'last_date', 'entries', 'read_at'];
const TS_COLS = {
  date: 'Date',
  projectKey: 'Project ID',
  email: 'Log User Mailid',
  user: 'User',
  hours: 'Hours(For Calculation)',
  approval: 'Approval Status',
};

const NUM_FMT = '0.00;-0.00;"-"';
const DIFF_FMT = '0.00;[Red]-0.00;"-"'; // capacity gaps: negatives in red
const CAPACITY_BG = '#e8f0fe';
const WHATIF_BG = '#fff8e1';
const GONE_BG = '#eeeeee';
const GONE_FONT = '#999999';

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Planning')
    .addItem('Set up sheet', 'setupSheet')
    .addSeparator()
    .addItem('Sync allocation', 'syncAllocation')
    .addItem('Prune gone projects/people…', 'pruneGone')
    .addToUi();
}

// ─── Menu actions ────────────────────────────────────────────────────────────

function setupSheet() {
  const ss = SpreadsheetApp.getActive();
  const ui = SpreadsheetApp.getUi();
  const notes = [];

  // Summary: planning month in MONTH_CELL, stored as text so it stays YYYY-MM.
  const [summaryName, monthA1] = CONFIG.MONTH_CELL.split('!');
  const summary = getOrCreateSheet_(ss, summaryName, notes);
  const monthCell = summary.getRange(monthA1);
  monthCell.setNumberFormat('@');
  if (monthCell.getValue() === '') {
    monthCell.setValue(Utilities.formatDate(new Date(), ss.getSpreadsheetTimeZone(), 'yyyy-MM'));
    notes.push(`Set ${CONFIG.MONTH_CELL} to this month. Change it to plan another month.`);
  }
  const label = monthCell.offset(0, -1);
  if (label.getValue() === '') label.setValue('Planning month (YYYY-MM):').setFontWeight('bold');

  ensureSettings_(ss, notes);

  [
    [CONFIG.PROJECTS_SHEET, PROJECTS_HEADERS, ['project_id'],
      ['project_id', 'project_name', 'project_key', 'monthly_budget']],
    [CONFIG.ALLOCATIONS_SHEET, ALLOCATIONS_HEADERS, ['project_id', 'person_zpuid', 'export_month'],
      ['project_id', 'project_name', 'person_name', 'allocated_hours', 'export_month']],
    [CONFIG.LOGGED_SHEET, LOGGED_HEADERS, ['project_id', 'export_month'], LOGGED_HEADERS],
    [CONFIG.PEOPLE_SHEET, PEOPLE_HEADERS, [], ['person_name']],
  ].forEach(([name, headers, textCols, required]) => {
    const sh = getOrCreateSheet_(ss, name, notes);
    ensureHeaders_(sh, headers, required, notes);
    const header = sh.getRange(1, 1, 1, Math.max(1, sh.getLastColumn())).getValues()[0].map(h => String(h).trim());
    textCols.forEach(col => {
      const c = header.indexOf(col) + 1;
      if (!c) return;
      const column = sh.getRange(1, c, sh.getMaxRows(), 1);
      column.setNumberFormat('@');
      if (column.getValues().some(([v]) => typeof v === 'number')) {
        notes.push(`"${name}" has ${col} values stored as numbers, which Sheets has already rounded. Re-paste that tab.`);
      }
    });
  });

  ensurePeopleCapacity_(ss, notes);

  // If the grid already exists, add the capacity rows and Summary block now
  // rather than waiting for the next Sync.
  const alloc = ss.getSheetByName(CONFIG.ALLOC_SHEET);
  if (alloc && String(alloc.getRange(ROW_KEY, COL_KEY).getValue()) === 'key') {
    ensureCapacityRows_(alloc);
    const grid = readGrid_(alloc);
    writeCapacity_(alloc, grid);
    writeSummary_(ss, grid);
    notes.push('Added the capacity rows to Allocation and the capacity check to Summary.');
  }

  // A brand-new spreadsheet starts with an empty "Sheet1"; drop it once the real tabs exist.
  const blank = ss.getSheetByName('Sheet1');
  if (blank && ss.getSheets().length > 1 && blank.getLastRow() === 0) {
    ss.deleteSheet(blank);
    notes.push('Removed the empty "Sheet1".');
  }

  ui.alert('Sheet set up', [
    ...(notes.length ? notes : ['Everything was already in place.']),
    '',
    `Next: paste the three Drive folder links on "${CONFIG.SETTINGS_SHEET}",`,
    `list the people you plan for on "${CONFIG.PEOPLE_SHEET}", then run Planning → Sync allocation.`,
  ].join('\n'), ui.ButtonSet.OK);
}

function syncAllocation() {
  const ss = SpreadsheetApp.getActive();
  const ui = SpreadsheetApp.getUi();
  const imported = [];
  ensurePeopleCapacity_(ss, imported);
  imported.push(...importFromDrive_(ss));
  const src = loadSource_(ss);
  imported.push(...writeLogged_(ss, src.month));
  const sh = ensureAllocSheet_(ss, ui);
  if (!sh) return;

  if (!confirmMonthChange_(sh, src.month, ui)) return;

  const added = { projects: [], people: [] };

  const havePeople = new Set(readGrid_(sh).persons.map(p => p.name));
  [...src.team]
    .filter(name => !havePeople.has(name))
    .sort(cmp_)
    .forEach(name => {
      insertPerson_(sh, name);
      added.people.push(name);
    });

  const haveProjects = new Set(readGrid_(sh).projects.map(p => p.id));
  [...src.projects.entries()]
    .filter(([id]) => !haveProjects.has(id))
    .sort((a, b) => cmp_(a[1].name, b[1].name))
    .forEach(([id, p]) => {
      insertProject_(sh, id, p.name);
      added.projects.push(p.name);
    });

  const moved = sortProjects_(sh, src);
  ensureCapacityRows_(sh);
  const grid = readGrid_(sh);
  writeData_(sh, grid, src);
  writeFormulas_(sh, grid);
  formatGrid_(sh, grid, src);
  writeCapacity_(sh, grid);
  writeSummary_(ss, grid);
  sh.getRange(MONTH_KEY_CELL).setNumberFormat('@').setValue(src.month);
  sh.getRange(ROW_TITLE, COL_PROJECT).setValue(`ALLOCATION MATRIX — ${src.month}`);

  const report = report_(grid, src, added) + (moved ? `\n\nRe-sorted ${moved} project row(s).` : '');
  const text = [...imported, ...(imported.length ? [''] : []), report].join('\n');
  ui.alert('Allocation synced', text, ui.ButtonSet.OK);
}

function pruneGone() {
  const ss = SpreadsheetApp.getActive();
  const ui = SpreadsheetApp.getUi();
  const src = loadSource_(ss);
  const sh = ensureAllocSheet_(ss, ui);
  if (!sh) return;
  const grid = readGrid_(sh);

  const goneRows = grid.projects.filter(p => p.id && !src.projects.has(p.id));
  const gonePeople = grid.persons.filter(p => !src.team.has(p.name));
  if (!goneRows.length && !gonePeople.length) {
    ui.alert('Nothing to prune.');
    return;
  }

  const lost = countWhatIf_(sh, grid, goneRows, gonePeople);
  const msg = [
    `Remove ${goneRows.length} gone project row(s) and ${gonePeople.length} person column pair(s)?`,
    ...goneRows.map(p => `  • ${p.name}`),
    ...gonePeople.map(p => `  • ${p.name}`),
    '',
    lost
      ? `${lost} what-if value(s) in them will be deleted.`
      : 'No what-if values will be lost.',
  ].join('\n');
  if (ui.alert('Prune', msg, ui.ButtonSet.YES_NO) !== ui.Button.YES) return;

  // Bottom-up / right-to-left so earlier deletions don't shift later targets.
  goneRows.map(p => p.row).sort((a, b) => b - a).forEach(r => sh.deleteRow(r));
  gonePeople.map(p => p.col).sort((a, b) => b - a).forEach(c => sh.deleteColumns(c, 2));

  // Deleted cells leave #REF! in the totals formulas; sync rewrites them.
  syncAllocation();
}

// ─── Source data ─────────────────────────────────────────────────────────────

function loadSource_(ss) {
  const month = normMonth_(ss.getRange(CONFIG.MONTH_CELL).getValue());
  if (!/^\d{4}-\d{2}$/.test(month)) {
    throw new Error(`${CONFIG.MONTH_CELL} must hold a month as YYYY-MM; found "${month}".`);
  }

  const P = readTable_(ss, CONFIG.PROJECTS_SHEET);
  const pId = col_(P, 'project_id');
  const pName = col_(P, 'project_name');
  const pBudget = col_(P, 'monthly_budget');
  const projects = new Map();
  P.rows.forEach(r => {
    const budget = r[pBudget];
    projects.set(idString_(r[pId], P, 'project_id'), {
      name: String(r[pName]).trim(),
      budget: budget === '' ? '' : Number(budget),
      category: projectCategory_(r[P.idx.engagement_model], r[P.idx.stage]),
    });
  });

  const People = readTable_(ss, CONFIG.PEOPLE_SHEET);
  const peName = col_(People, 'person_name');
  const team = new Set(People.rows.map(r => String(r[peName]).trim()).filter(Boolean));

  const A = readTable_(ss, CONFIG.ALLOCATIONS_SHEET);
  const aId = col_(A, 'project_id');
  const aProject = col_(A, 'project_name');
  const aPerson = col_(A, 'person_name');
  const aAllocated = col_(A, 'allocated_hours');
  const aMonth = col_(A, 'export_month');

  const actual = new Map(); // `${project_id}|${person_name}` → hours
  const other = new Map(); // project_id → hours from people not on the People tab
  const otherPeople = new Set();
  const unknownProjects = new Set();
  let actualRows = 0;

  A.rows.forEach(r => {
    if (normMonth_(r[aMonth]) !== month) return;
    actualRows++;
    const pid = idString_(r[aId], A, 'project_id');
    if (!projects.has(pid)) {
      unknownProjects.add(String(r[aProject]).trim());
      return;
    }
    const person = String(r[aPerson]).trim();
    const hours = Number(r[aAllocated]) || 0;
    if (team.has(person)) {
      const k = key_(pid, person);
      actual.set(k, (actual.get(k) || 0) + hours);
    } else {
      other.set(pid, (other.get(pid) || 0) + hours);
      otherPeople.add(person);
    }
  });

  return { month, projects, team, actual, other, otherPeople, unknownProjects, actualRows };
}

function readTable_(ss, name) {
  const sh = ss.getSheetByName(name);
  if (!sh) throw new Error(`Tab "${name}" not found.`);
  const values = sh.getDataRange().getValues();
  const idx = {};
  values[0].forEach((h, i) => { idx[String(h).trim()] = i; });
  return { name, idx, rows: values.slice(1).filter(r => r.some(c => c !== '')) };
}

function col_(table, header) {
  if (!(header in table.idx)) throw new Error(`Tab "${table.name}" has no "${header}" column.`);
  return table.idx[header];
}

function idString_(v, table, field) {
  if (typeof v === 'number') {
    throw new Error(
      `"${table.name}" stores ${field} as a number (${v}), which Sheets rounds. ` +
      'Re-import with "Convert text to numbers, dates, and formulas" unticked, ' +
      'or format the column as Plain text before pasting.');
  }
  return String(v).trim();
}

// ─── People capacity ─────────────────────────────────────────────────────────

/**
 * Keeps People's capacity columns in shape:
 *  - renames the old leave column to leave_hr_mgmt_hrs_mtd;
 *  - makes effective_capacity_hrs a single ARRAYFORMULA in its header cell:
 *    monthly_capacity_hrs − leave_hr_mgmt_hrs_mtd for every named person.
 * Typed effective capacities are only replaced when every one of them already
 * equals monthly − deduction (or is blank), so nothing entered by hand is lost.
 */
function ensurePeopleCapacity_(ss, notes) {
  const sh = ss.getSheetByName(CONFIG.PEOPLE_SHEET);
  if (!sh || !sh.getLastColumn()) return;
  const width = sh.getLastColumn();
  const header = sh.getRange(1, 1, 1, width).getValues()[0].map(h => String(h).trim());

  OLD_DEDUCTION_HEADERS.forEach(old => {
    const i = header.indexOf(old);
    if (i < 0 || header.includes(DEDUCTION_HEADER)) return;
    sh.getRange(1, i + 1).setValue(DEDUCTION_HEADER);
    header[i] = DEDUCTION_HEADER;
    notes.push(`Renamed People column "${old}" to "${DEDUCTION_HEADER}".`);
  });

  const L = c => colA1_(c + 1);
  const [name, monthly, deduct, effective] =
    ['person_name', MONTHLY_HEADER, DEDUCTION_HEADER, CAPACITY_HEADER].map(h => header.indexOf(h));
  if (effective < 0) return; // capacity check not set up on this sheet
  if ([name, monthly, deduct].some(i => i < 0)) {
    notes.push(`People needs person_name, ${MONTHLY_HEADER} and ${DEDUCTION_HEADER} columns ` +
      `to calculate ${CAPACITY_HEADER}; it was left as typed.`);
    return;
  }

  const formula = `={"${CAPACITY_HEADER}";ARRAYFORMULA(IF(${L(name)}2:${L(name)}="","",` +
    `${L(monthly)}2:${L(monthly)}-${L(deduct)}2:${L(deduct)}))}`;
  const top = sh.getRange(1, effective + 1);
  if (top.getFormula().replace(/\s+/g, '') === formula.replace(/\s+/g, '')) return;

  const lastRow = Math.max(sh.getLastRow(), 2);
  const rows = sh.getRange(2, 1, lastRow - 1, width).getValues();
  const differs = rows.filter(r => String(r[name]).trim() && r[effective] !== '' &&
    Math.abs(Number(r[effective]) - ((Number(r[monthly]) || 0) - (Number(r[deduct]) || 0))) > 0.001);
  if (differs.length) {
    notes.push(`${CAPACITY_HEADER} on People was not changed: ${differs.length} row(s) differ from ` +
      `${MONTHLY_HEADER} − ${DEDUCTION_HEADER} (${differs.map(r => r[name]).join(', ')}). ` +
      `Move those hours into ${DEDUCTION_HEADER}, clear ${CAPACITY_HEADER} below the header, then run Sync again.`);
    return;
  }
  sh.getRange(2, effective + 1, lastRow - 1, 1).clearContent();
  top.setFormula(formula);
  notes.push(`${CAPACITY_HEADER} on People is now calculated as ${MONTHLY_HEADER} − ${DEDUCTION_HEADER}.`);
}

// ─── Settings and Drive import ───────────────────────────────────────────────

function ensureSettings_(ss, notes) {
  const sh = getOrCreateSheet_(ss, CONFIG.SETTINGS_SHEET, notes);
  if (sh.getLastRow() === 0) {
    sh.getRange(1, 1, 1, 3).setValues([['setting', 'value', 'description']]).setFontWeight('bold');
    sh.setFrozenRows(1);
  }
  const have = new Set(readRows_(sh).map(r => String(r[0]).trim()));
  SETTINGS.filter(([key]) => !have.has(key)).forEach(([key, description]) => {
    sh.appendRow([key, '', description]);
    notes.push(`Added "${key}" to ${CONFIG.SETTINGS_SHEET}. Paste the folder link in column B.`);
  });
}

function readSettings_(ss) {
  const sh = ss.getSheetByName(CONFIG.SETTINGS_SHEET);
  const out = {};
  if (!sh) return out;
  readRows_(sh).forEach(([k, v]) => {
    const key = String(k).trim();
    const value = String(v).trim();
    if (key && value) out[key] = value;
  });
  return out;
}

/** Accepts a Drive folder link or a bare ID. */
function folderId_(value) {
  const m = value.match(/folders\/([\w-]+)/) || value.match(/[?&]id=([\w-]+)/);
  return m ? m[1] : value;
}

/**
 * Loads the newest projects and allocations CSVs and any unread timesheets from
 * the folders on Settings. Tabs whose folder isn't set are left as they are, so
 * pasting CSVs by hand still works. Returns report lines.
 */
function importFromDrive_(ss) {
  const settings = readSettings_(ss);
  const lines = [];
  [
    ['projects_folder', /_projects\.csv$/i, CONFIG.PROJECTS_SHEET, ['project_id'], 'Projects'],
    ['allocations_folder', /_allocations\.csv$/i, CONFIG.ALLOCATIONS_SHEET,
      ['project_id', 'person_zpuid', 'export_month'], 'Allocations'],
  ].forEach(([key, pattern, tab, textCols, label]) => {
    if (!settings[key]) return;
    const file = newestByName_(folderId_(settings[key]), pattern);
    if (!file) {
      lines.push(`${label}: no matching CSV in the folder; "${tab}" left unchanged.`);
      return;
    }
    const rows = Utilities.parseCsv(file.getBlob().getDataAsString('UTF-8'));
    writeTable_(ss, tab, rows, textCols);
    lines.push(`${label}: ${file.getName()}`);
  });
  if (settings.timesheets_folder) lines.push(...ingestTimesheets_(ss, folderId_(settings.timesheets_folder)));
  return lines;
}

/** Export filenames start with a YYYY_MM_DD_HHMM timestamp, so name order is run order. */
function newestByName_(folderId, pattern) {
  const files = DriveApp.getFolderById(folderId).getFiles();
  let best = null;
  while (files.hasNext()) {
    const f = files.next();
    if (pattern.test(f.getName()) && (!best || f.getName() > best.getName())) best = f;
  }
  return best;
}

/**
 * Replaces a tab's contents with `rows` (first row = headers). Columns in
 * `textCols` are stored as plain text; other numeric strings become numbers so
 * formulas on other tabs can sum them.
 */
function writeTable_(ss, name, rows, textCols) {
  if (!rows.length) throw new Error(`No rows to write to "${name}".`);
  const width = Math.max(...rows.map(r => r.length));
  const header = rows[0].map(h => String(h).trim());
  const textIdx = new Set(textCols.map(c => header.indexOf(c)).filter(i => i >= 0));
  const values = rows.map((r, ri) => {
    const row = r.concat(Array(width - r.length).fill(''));
    if (ri === 0) return row;
    return row.map((v, ci) => (!textIdx.has(ci) && /^-?\d{1,15}(\.\d+)?$/.test(v) ? Number(v) : v));
  });

  const sh = ss.getSheetByName(name) || ss.insertSheet(name);
  sh.clear();
  ensureSize_(sh, values.length, width);
  textIdx.forEach(ci => sh.getRange(1, ci + 1, values.length, 1).setNumberFormat('@'));
  sh.getRange(1, 1, values.length, width).setValues(values);
  sh.getRange(1, 1, 1, width).setFontWeight('bold');
  sh.setFrozenRows(1);
}

function ensureSize_(sh, rows, cols) {
  if (sh.getMaxRows() < rows) sh.insertRowsAfter(sh.getMaxRows(), rows - sh.getMaxRows());
  if (sh.getMaxColumns() < cols) sh.insertColumnsAfter(sh.getMaxColumns(), cols - sh.getMaxColumns());
}

function readRows_(sh) {
  if (!sh || sh.getLastRow() < 2) return [];
  return sh.getRange(2, 1, sh.getLastRow() - 1, Math.max(1, sh.getLastColumn())).getValues();
}

function hiddenTab_(ss, name, headers) {
  let sh = ss.getSheetByName(name);
  if (sh) return sh;
  sh = ss.insertSheet(name);
  sh.getRange(1, 1, sh.getMaxRows(), headers.length).setNumberFormat('@');
  sh.getRange(1, 1, 1, headers.length).setValues([headers]).setFontWeight('bold');
  sh.hideSheet();
  return sh;
}

// ─── Timesheets ──────────────────────────────────────────────────────────────

/**
 * Reads timesheet xlsx files not yet listed on _timesheet_files and merges them
 * into _timesheet_log. Per day, entries from the most recently exported file win.
 */
function ingestTimesheets_(ss, folderId) {
  const filesSh = hiddenTab_(ss, CONFIG.TS_FILES_SHEET, TS_FILES_HEADERS);
  const logSh = hiddenTab_(ss, CONFIG.TS_LOG_SHEET, TS_LOG_HEADERS);
  const known = new Set(readRows_(filesSh).map(r => String(r[0])));

  const fresh = [];
  const it = DriveApp.getFolderById(folderId).getFiles();
  while (it.hasNext()) {
    const f = it.next();
    if (/\.xlsx$/i.test(f.getName()) && !known.has(f.getId())) fresh.push(f);
  }
  if (!fresh.length) return ['Timesheets: no new files.'];
  if (typeof Drive === 'undefined') {
    throw new Error('Reading timesheet xlsx files needs the Drive API service: ' +
      'Extensions → Apps Script → Services (+) → Drive API → Add, then run Sync again.');
  }

  // date → { fileId, exportedAt, entries[] }
  const byDate = new Map();
  readRows_(logSh).forEach(([fileId, exportedAt, date, key, email, user, hours]) => {
    const d = String(date);
    if (!byDate.has(d)) byDate.set(d, { fileId: String(fileId), exportedAt: String(exportedAt), entries: [] });
    byDate.get(d).entries.push({ key: String(key), email: String(email), user: String(user), hours: Number(hours) || 0 });
  });

  const lines = [];
  fresh.forEach(file => {
    const { entries, exportedAt, convertedDates } = readTimesheet_(file);
    const days = new Map();
    entries.forEach(e => {
      if (!days.has(e.date)) days.set(e.date, []);
      days.get(e.date).push(e);
    });
    const dates = [...days.keys()].sort();
    let used = 0;
    days.forEach((dayEntries, date) => {
      const cur = byDate.get(date);
      if (cur && cur.exportedAt > exportedAt) return; // a later export already covers this day
      byDate.set(date, { fileId: file.getId(), exportedAt, entries: dayEntries });
      used++;
    });
    filesSh.appendRow([file.getId(), file.getName(), exportedAt, dates[0] || '', dates.at(-1) || '',
      entries.length, new Date().toISOString()]);
    const range = dates.length ? `${dates[0]} → ${dates.at(-1)}` : 'no dated entries';
    const superseded = dates.length - used;
    lines.push(`Timesheet read: ${file.getName()} (${range}, ${entries.length} entries` +
      (superseded ? `, ${superseded} day(s) already covered by a later export` : '') + ')');
    if (convertedDates) {
      lines.push(`  Warning: ${convertedDates} date(s) in ${file.getName()} were stored as dates, not ` +
        'text, and may have day and month swapped. Check them against the file.');
    }
  });

  const out = [];
  [...byDate.keys()].sort().forEach(date => {
    const day = byDate.get(date);
    day.entries.forEach(e => out.push([day.fileId, day.exportedAt, date, e.key, e.email, e.user, e.hours]));
  });
  if (logSh.getLastRow() > 1) logSh.getRange(2, 1, logSh.getLastRow() - 1, TS_LOG_HEADERS.length).clearContent();
  ensureSize_(logSh, out.length + 1, TS_LOG_HEADERS.length);
  if (out.length) {
    logSh.getRange(2, 1, out.length, TS_LOG_HEADERS.length - 1).setNumberFormat('@');
    logSh.getRange(2, 1, out.length, TS_LOG_HEADERS.length).setValues(out);
  }
  return lines;
}

/** Converts the xlsx to a temporary Google Sheet, reads its entries, then trashes the copy. */
function readTimesheet_(file) {
  const exportedAt = xlsxCreated_(file) || file.getDateCreated().toISOString();
  const tmpId = convertToSheet_(file);
  try {
    const values = SpreadsheetApp.openById(tmpId).getSheets()[0].getDataRange().getValues();
    const idx = {};
    values[0].forEach((h, i) => { idx[String(h).trim()] = i; });
    ['date', 'projectKey', 'email', 'user', 'hours'].forEach(k => {
      if (!(TS_COLS[k] in idx)) throw new Error(`${file.getName()} has no "${TS_COLS[k]}" column.`);
    });
    let convertedDates = 0;
    const entries = [];
    values.slice(1).forEach(r => {
      const raw = r[idx[TS_COLS.date]];
      if (raw instanceof Date) convertedDates++;
      const date = timesheetDate_(raw);
      if (!date) return;
      if (TS_COLS.approval in idx && /reject/i.test(String(r[idx[TS_COLS.approval]]))) return;
      entries.push({
        date,
        key: String(r[idx[TS_COLS.projectKey]]).trim(),
        email: String(r[idx[TS_COLS.email]]).trim().toLowerCase(),
        user: String(r[idx[TS_COLS.user]]).trim(),
        hours: Number(r[idx[TS_COLS.hours]]) || 0,
      });
    });
    return { entries, exportedAt, convertedDates };
  } finally {
    DriveApp.getFileById(tmpId).setTrashed(true);
  }
}

function convertToSheet_(file) {
  const blob = file.getBlob();
  const name = `tmp-convert ${file.getName()}`;
  const created = Drive.Files.create // Drive API v3; v2 uses insert/title
    ? Drive.Files.create({ name, mimeType: MimeType.GOOGLE_SHEETS }, blob)
    : Drive.Files.insert({ title: name, mimeType: MimeType.GOOGLE_SHEETS }, blob);
  return created.id;
}

/** Export time from the xlsx's own metadata (docProps/core.xml), or '' if unavailable. */
function xlsxCreated_(file) {
  try {
    const parts = Utilities.unzip(file.getBlob().copyBlob().setContentType('application/zip'));
    const core = parts.find(b => b.getName() === 'docProps/core.xml');
    const m = core && core.getDataAsString().match(/<dcterms:created[^>]*>([^<]+)</);
    return m ? new Date(m[1]).toISOString() : '';
  } catch (e) {
    return '';
  }
}

/** Timesheet dates are DD-MM-YYYY text; returns YYYY-MM-DD or ''. */
function timesheetDate_(v) {
  if (v instanceof Date) return Utilities.formatDate(v, Session.getScriptTimeZone(), 'yyyy-MM-dd');
  const m = String(v).trim().match(/^(\d{2})-(\d{2})-(\d{4})$/);
  return m ? `${m[3]}-${m[2]}-${m[1]}` : '';
}

/**
 * Rebuilds "Logged import" for the planning month from _timesheet_log: one row
 * per project and person, for projects on Projects import. People are named
 * from People (person_email), else Allocations import, else the timesheet.
 */
function writeLogged_(ss, month) {
  const logSh = ss.getSheetByName(CONFIG.TS_LOG_SHEET);
  if (!logSh) return [];

  const P = readTable_(ss, CONFIG.PROJECTS_SHEET);
  const pKey = col_(P, 'project_key');
  const pId = col_(P, 'project_id');
  const pName = col_(P, 'project_name');
  const byKey = new Map(P.rows.map(r => [String(r[pKey]).trim(), {
    id: idString_(r[pId], P, 'project_id'),
    name: String(r[pName]).trim(),
  }]));

  const nameByEmail = new Map();
  const A = readTable_(ss, CONFIG.ALLOCATIONS_SHEET);
  if ('person_email' in A.idx) {
    A.rows.forEach(r => {
      const email = String(r[A.idx.person_email]).trim().toLowerCase();
      if (email) nameByEmail.set(email, String(r[A.idx.person_name]).trim());
    });
  }
  const People = readTable_(ss, CONFIG.PEOPLE_SHEET);
  if ('person_email' in People.idx) {
    People.rows.forEach(r => { // People wins over Allocations import
      const email = String(r[People.idx.person_email]).trim().toLowerCase();
      if (email) nameByEmail.set(email, String(r[People.idx.person_name]).trim());
    });
  }

  const agg = new Map(); // `${project_id}|${email}` → row
  let first = '';
  let last = '';
  let unnamed = 0;
  readRows_(logSh).forEach(([, , date, key, email, user, hours]) => {
    const d = String(date);
    if (!d.startsWith(`${month}-`)) return;
    first = !first || d < first ? d : first;
    last = d > last ? d : last;
    const project = byKey.get(String(key).trim());
    if (!project) return;
    const e = String(email);
    const k = `${project.id}|${e}`;
    if (!agg.has(k)) {
      const known = nameByEmail.get(e);
      if (!known) unnamed++;
      agg.set(k, [project.id, project.name, known || String(user), e, 0, month]);
    }
    agg.get(k)[4] += Number(hours) || 0;
  });

  const rows = [...agg.values()]
    .map(r => (r[4] = Math.round(r[4] * 100) / 100, r))
    .sort((a, b) => cmp_(a[1], b[1]) || cmp_(a[2], b[2]));
  writeTable_(ss, CONFIG.LOGGED_SHEET, [LOGGED_HEADERS, ...rows.map(r => r.map(String))],
    ['project_id', 'export_month']);

  const total = rows.reduce((t, r) => t + r[4], 0);
  const lines = [first
    ? `Logged ${month}: ${Math.round(total * 100) / 100} hrs on your projects, timesheet days ${first} → ${last}`
    : `Logged ${month}: no timesheet entries for this month yet.`];
  if (unnamed) lines.push(`  ${unnamed} person/project row(s) named from the timesheet; add person_email on People to match them.`);
  return lines;
}

// ─── Setup helpers ───────────────────────────────────────────────────────────

function getOrCreateSheet_(ss, name, notes) {
  const existing = ss.getSheetByName(name);
  if (existing) return existing;
  notes.push(`Created "${name}".`);
  return ss.insertSheet(name);
}

/** Writes headers into an empty row 1; on a populated tab only reports missing required ones. */
function ensureHeaders_(sh, headers, required, notes) {
  const lastCol = sh.getLastColumn();
  const current = lastCol
    ? sh.getRange(1, 1, 1, lastCol).getValues()[0].map(h => String(h).trim())
    : [];
  if (!current.some(Boolean)) {
    sh.getRange(1, 1, 1, headers.length).setValues([headers]).setFontWeight('bold');
    sh.setFrozenRows(1);
    return;
  }
  const missing = required.filter(h => !current.includes(h));
  if (missing.length) notes.push(`"${sh.getName()}" is missing required column(s): ${missing.join(', ')}.`);
}

// ─── Grid structure ──────────────────────────────────────────────────────────

/**
 * Returns the managed Allocation tab, creating it if missing. A tab with that
 * name that wasn't built by this script is cleared and rebuilt in place (after
 * confirmation), so formulas on other tabs that reference it keep working.
 * Returns null if the user declines.
 */
function ensureAllocSheet_(ss, ui) {
  let sh = ss.getSheetByName(CONFIG.ALLOC_SHEET);
  if (sh && String(sh.getRange(ROW_KEY, COL_KEY).getValue()) === 'key') return sh;

  if (sh) {
    const choice = ui.alert(
      'Rebuild Allocation tab',
      `The "${CONFIG.ALLOC_SHEET}" tab wasn't built by this script. ` +
      'Clear it and rebuild it as a synced grid? Everything on it, including what-if values, will be removed.',
      ui.ButtonSet.OK_CANCEL);
    if (choice !== ui.Button.OK) return null;
    sh.setFrozenRows(0);
    sh.setFrozenColumns(0);
    const all = sh.getRange(1, 1, sh.getMaxRows(), sh.getMaxColumns());
    all.breakApart().clearDataValidations();
    sh.clear();
    sh.clearConditionalFormatRules();
    sh.showRows(1, sh.getMaxRows());
    sh.showColumns(1, sh.getMaxColumns());
  } else {
    sh = ss.insertSheet(CONFIG.ALLOC_SHEET);
  }

  sh.getRange('A:A').setNumberFormat('@');
  sh.getRange(ROW_KEY, COL_KEY).setValue('key');
  sh.getRange(ROW_KEY, FIRST_PERSON_COL, 1, TOTAL_COLS.length).setValues([TOTAL_COLS.map(t => t.key)]);
  sh.getRange(FIRST_DATA_ROW, COL_KEY).setValue(FOOTER_KEY);
  sh.hideRows(ROW_KEY);
  sh.hideColumns(COL_KEY);
  sh.setFrozenRows(ROW_KIND);
  sh.setFrozenColumns(COL_STATUS);
  return sh;
}

function readGrid_(sh) {
  const lastCol = sh.getLastColumn();
  const keyRow = sh.getRange(ROW_KEY, 1, 1, lastCol).getValues()[0].map(String);
  const totalsStart = keyRow.indexOf(TOTAL_COLS[0].key) + 1;
  if (!totalsStart) throw new Error(`"${CONFIG.ALLOC_SHEET}" is missing its hidden key row. Was row 1 edited?`);

  const persons = [];
  for (let c = FIRST_PERSON_COL; c < totalsStart; c += 2) {
    persons.push({ name: keyRow[c - 1], col: c });
  }

  const left = sh.getRange(1, COL_KEY, sh.getLastRow(), 2).getValues();
  const footerRow = left.findIndex(r => String(r[0]) === FOOTER_KEY) + 1;
  if (!footerRow) throw new Error(`"${CONFIG.ALLOC_SHEET}" is missing its footer row (${FOOTER_KEY} in column A).`);

  const projects = [];
  for (let r = FIRST_DATA_ROW; r < footerRow; r++) {
    projects.push({ id: String(left[r - 1][0]).trim(), name: String(left[r - 1][1]).trim(), row: r });
  }

  return { persons, projects, totalsStart, footerRow, lastCol: totalsStart + TOTAL_COLS.length - 1 };
}

function insertPerson_(sh, name) {
  const grid = readGrid_(sh);
  const next = grid.persons.find(p => cmp_(p.name, name) > 0);
  const col = next ? next.col : grid.totalsStart;
  sh.insertColumnsBefore(col, 2);
  sh.getRange(1, col, sh.getMaxRows(), 2).clearFormat();
  sh.getRange(ROW_KEY, col, 1, 2).setValues([[name, name]]);
  sh.getRange(ROW_PERSON, col, 1, 2).merge().setValue(name);
  sh.getRange(ROW_KIND, col, 1, 2).setValues([[KIND_ACTUAL, KIND_WHATIF]]);
}

/**
 * Presales: engagement model PreSales, or stage Sales / Pre-Sales (the same rule
 * the project export uses). T&M: engagement model T&M. Anything else is "other".
 */
function projectCategory_(engagement, stage) {
  const e = String(engagement || '').replace(/\s+/g, '').toLowerCase();
  const st = String(stage || '').replace(/\s+/g, '').toLowerCase();
  if (e === 'presales' || st === 'sales' || st === 'pre-sales' || st === 'presales') return CATEGORY.PRESALES;
  if (e === 't&m') return CATEGORY.TM;
  return CATEGORY.OTHER;
}

/**
 * Orders project rows: other, presales, T&M, then gone, each alphabetical.
 * Whole rows are moved (moveRows), so typed What-if values move with their
 * project. Returns the number of rows moved.
 */
function sortProjects_(sh, src) {
  const rows = readGrid_(sh).projects;
  const info = p => {
    const live = src.projects.get(p.id);
    return live ? { cat: live.category, name: live.name } : { cat: CATEGORY.GONE, name: p.name };
  };
  const wanted = [...rows].sort((a, b) => {
    const x = info(a);
    const y = info(b);
    return x.cat - y.cat || cmp_(x.name, y.name);
  });

  // Fill positions top-down; the row needed next is always at or below its target.
  const current = [...rows];
  let moved = 0;
  wanted.forEach((p, i) => {
    const j = current.indexOf(p);
    if (j === i) return;
    const from = FIRST_DATA_ROW + j;
    sh.moveRows(sh.getRange(`${from}:${from}`), FIRST_DATA_ROW + i);
    current.splice(j, 1);
    current.splice(i, 0, p);
    moved++;
  });
  return moved;
}

/** Appends a project row above the footer; sortProjects_ then moves it into place. */
function insertProject_(sh, id, name) {
  const row = readGrid_(sh).footerRow;
  sh.insertRowsBefore(row, 1);
  sh.getRange(row, COL_KEY).setNumberFormat('@').setValue(id);
  sh.getRange(row, COL_PROJECT).setValue(name);
}

// ─── Writing values, formulas and formats ────────────────────────────────────

function writeData_(sh, grid, src) {
  const n = grid.projects.length;
  if (!n) return;

  sh.getRange(FIRST_DATA_ROW, COL_PROJECT, n, 2).setValues(grid.projects.map(p => {
    const live = src.projects.get(p.id);
    const status = !p.id ? '' : live ? STATUS_ACTIVE : STATUS_GONE;
    return [live ? live.name : p.name, status];
  }));

  grid.persons.forEach(per => {
    sh.getRange(FIRST_DATA_ROW, per.col, n, 1).setValues(
      grid.projects.map(p => [p.id ? src.actual.get(key_(p.id, per.name)) || 0 : '']));
  });

  const tc = grid.totalsStart;
  sh.getRange(FIRST_DATA_ROW, tc + T.OTHER, n, 1).setValues(
    grid.projects.map(p => [p.id ? src.other.get(p.id) || 0 : '']));
  sh.getRange(FIRST_DATA_ROW, tc + T.BUD, n, 1).setValues(
    grid.projects.map(p => [src.projects.has(p.id) ? src.projects.get(p.id).budget : '']));
}

function writeFormulas_(sh, grid) {
  const n = grid.projects.length;
  const tc = grid.totalsStart;
  const L = colA1_;
  const otherL = L(tc + T.OTHER);
  const actL = L(tc + T.ACT);
  const wifL = L(tc + T.WIF);
  const budL = L(tc + T.BUD);

  if (n) {
    sh.getRange(FIRST_DATA_ROW, tc + T.ACT, n, 2).setFormulas(grid.projects.map(({ row: r }) => {
      const act = grid.persons.map(p => `${L(p.col)}${r}`);
      const wif = grid.persons.map(p => {
        const a = `${L(p.col)}${r}`;
        const w = `${L(p.col + 1)}${r}`;
        return `IF(${w}="",${a},${w})`;
      });
      return [`=${[...act, `${otherL}${r}`].join('+')}`, `=${[...wif, `${otherL}${r}`].join('+')}`];
    }));
    sh.getRange(FIRST_DATA_ROW, tc + T.REM_A, n, 2).setFormulas(grid.projects.map(({ row: r }) => [
      `=IF(${budL}${r}="","",${budL}${r}-${actL}${r})`,
      `=IF(${budL}${r}="","",${budL}${r}-${wifL}${r})`,
    ]));
  }

  const a = FIRST_DATA_ROW;
  const b = grid.footerRow - 1;
  const status = `$${L(COL_STATUS)}$${a}:$${L(COL_STATUS)}$${b}`;
  const span = c => `${L(c)}${a}:${L(c)}${b}`;
  const sumActive = c => (n ? `=SUMIF(${status},"${STATUS_ACTIVE}",${span(c)})` : '');
  const sumActiveWhatIf = p => (n
    ? `=ARRAYFORMULA(SUM(IF(${status}="${STATUS_ACTIVE}",IF(${span(p.col + 1)}="",${span(p.col)},${span(p.col + 1)}),0)))`
    : '');

  const footer = [];
  grid.persons.forEach(p => footer.push(sumActive(p.col), sumActiveWhatIf(p)));
  TOTAL_COLS.forEach((_, i) => footer.push(sumActive(tc + i)));
  sh.getRange(grid.footerRow, FIRST_PERSON_COL, 1, footer.length).setFormulas([footer]);
}

function formatGrid_(sh, grid, src) {
  const n = grid.projects.length;
  const width = grid.lastCol - COL_PROJECT + 1;

  sh.getRange(ROW_TITLE, COL_PROJECT).setFontWeight('bold').setFontSize(12);
  sh.getRange(ROW_KIND, COL_PROJECT, 1, 2).setValues([['Project', 'Status']]);
  sh.getRange(ROW_PERSON, grid.totalsStart, 1, TOTAL_COLS.length).setValues([TOTAL_COLS.map(t => t.label)]);
  sh.getRange(ROW_PERSON, COL_PROJECT, 2, width)
    .setFontWeight('bold').setHorizontalAlignment('center').setBackground(null).setFontColor(null);

  // Number format covers the data rows plus the footer directly below them.
  sh.getRange(FIRST_DATA_ROW, FIRST_PERSON_COL, n + 1, grid.lastCol - FIRST_PERSON_COL + 1)
    .setNumberFormat(NUM_FMT);

  if (n) {
    sh.getRange(FIRST_DATA_ROW, COL_PROJECT, n, width)
      .setBackground(null).setFontColor(null).setFontWeight('normal');
    grid.persons.forEach(p => sh.getRange(FIRST_DATA_ROW, p.col + 1, n, 1).setBackground(WHATIF_BG));
    grid.projects
      .filter(p => p.id && !src.projects.has(p.id))
      .forEach(p => sh.getRange(p.row, COL_PROJECT, 1, width).setBackground(GONE_BG).setFontColor(GONE_FONT));
  }

  grid.persons.forEach(p => {
    const gone = !src.team.has(p.name);
    sh.getRange(ROW_PERSON, p.col).setValue(gone ? `${p.name} (not in People)` : p.name);
    if (!gone) return;
    sh.getRange(ROW_PERSON, p.col, 2, 2).setBackground(GONE_BG).setFontColor(GONE_FONT);
    if (n) sh.getRange(FIRST_DATA_ROW, p.col, n, 2).setFontColor(GONE_FONT);
  });

  sh.getRange(grid.footerRow, COL_PROJECT).setValue('Total (active)');
  sh.getRange(grid.footerRow, COL_PROJECT, 1, width).setFontWeight('bold');
}

// ─── Capacity rows and Summary ───────────────────────────────────────────────

/** Adds the capacity and remaining-capacity rows under the footer if missing. */
function ensureCapacityRows_(sh) {
  const { footerRow } = readGrid_(sh);
  const keys = sh.getRange(footerRow + 1, COL_KEY, 2, 1).getValues().map(r => String(r[0]));
  if (keys[0] === CAPACITY_KEY && keys[1] === REMAINING_KEY) return;
  sh.insertRowsAfter(footerRow, 2);
  sh.getRange(footerRow + 1, COL_KEY, 2, 1).setNumberFormat('@').setValues([[CAPACITY_KEY], [REMAINING_KEY]]);
}

function quoteSheet_(name) {
  return `'${name.replace(/'/g, "''")}'`;
}

/**
 * Capacity row: each person's effective capacity, looked up live from People by
 * the name in the hidden key row. Remaining row: capacity minus the footer's
 * Actual / What-if totals. In the totals block, "Total actual" / "Total what-if"
 * hold the team's capacity and its gap; "Other" hours are left out because
 * people not on People have no capacity.
 */
function writeCapacity_(sh, grid) {
  const L = colA1_;
  const f = grid.footerRow;
  const cap = f + 1;
  const rem = f + 2;
  const tc = grid.totalsStart;
  const P = quoteSheet_(CONFIG.PEOPLE_SHEET);
  const people = `${P}!$A$1:$ZZ$2000`;
  const lookup = c => `=IFERROR(INDEX(${people},` +
    `MATCH(${L(c)}$1,INDEX(${people},0,MATCH("person_name",${P}!$1:$1,0)),0),` +
    `MATCH("${CAPACITY_HEADER}",${P}!$1:$1,0)),"")`;
  const gap = (c, allocCol) => `=IF(${L(c)}${cap}="","",${L(c)}${cap}-${L(allocCol)}${f})`;

  const capRow = [];
  const remRow = [];
  grid.persons.forEach(p => {
    capRow.push(lookup(p.col), `=${L(p.col)}${cap}`);
    remRow.push(gap(p.col, p.col), gap(p.col + 1, p.col + 1));
  });

  const teamCap = grid.persons.length ? `=SUM(${grid.persons.map(p => `${L(p.col)}${cap}`).join(',')})` : '=0';
  const other = `${L(tc + T.OTHER)}${f}`;
  const totals = TOTAL_COLS.map(() => ['', '']);
  totals[T.ACT] = [teamCap, `=${L(tc + T.ACT)}${cap}-(${L(tc + T.ACT)}${f}-${other})`];
  totals[T.WIF] = [teamCap, `=${L(tc + T.WIF)}${cap}-(${L(tc + T.WIF)}${f}-${other})`];
  totals.forEach(([c, r]) => { capRow.push(c); remRow.push(r); });

  const width = grid.lastCol - FIRST_PERSON_COL + 1;
  sh.getRange(cap, FIRST_PERSON_COL, 2, width).setFormulas([capRow, remRow]);
  sh.getRange(cap, COL_PROJECT, 2, 1).setValues([['Effective capacity (hrs)'], ['Capacity - unallocated/T&D']]);

  const all = sh.getRange(cap, COL_PROJECT, 2, grid.lastCol - COL_PROJECT + 1);
  all.setFontWeight('bold').setFontColor(null).setBackground(null);
  sh.getRange(cap, COL_PROJECT, 1, grid.lastCol - COL_PROJECT + 1).setBackground(CAPACITY_BG);
  sh.getRange(cap, FIRST_PERSON_COL, 1, width).setNumberFormat(NUM_FMT);
  sh.getRange(rem, FIRST_PERSON_COL, 1, width).setNumberFormat(DIFF_FMT);
}

/**
 * Capacity check block on Summary (C3:D12), as live formulas pointing at the
 * Allocation tab. Rewritten on every sync, so don't put other content there.
 */
function writeSummary_(ss, grid) {
  const [summaryName] = CONFIG.MONTH_CELL.split('!');
  const sum = ss.getSheetByName(summaryName);
  if (!sum) return;

  const L = colA1_;
  const A = `${quoteSheet_(CONFIG.ALLOC_SHEET)}!`;
  const f = grid.footerRow;
  const tc = grid.totalsStart;
  const at = (col, row) => `${A}${L(col)}${row}`;
  const r0 = SUMMARY_FIRST_ROW;
  const d = i => `D${r0 + i}`; // value cell of block line i
  const n = grid.projects.length;
  const budCol = L(tc + T.BUD);
  const statusCol = L(COL_STATUS);

  const lines = [
    ['CAPACITY CHECK', ''],
    ['Total capacity (hrs)', `=${at(tc + T.ACT, f + 1)}`],
    ['Total budget (hrs)', `=${at(tc + T.BUD, f)}`],
    ['Capacity − budget (hrs)', `=${d(1)}-${d(2)}`],
    ['Team allocated — actual (hrs)', `=${at(tc + T.ACT, f)}-${at(tc + T.OTHER, f)}`],
    ['Team allocated — what-if (hrs)', `=${at(tc + T.WIF, f)}-${at(tc + T.OTHER, f)}`],
    ['Spare capacity — actual (hrs)', `=${d(1)}-${d(4)}`],
    ['Spare capacity — what-if (hrs)', `=${d(1)}-${d(5)}`],
    ['Allocated to people not on People (hrs)', `=${at(tc + T.OTHER, f)}`],
    ['Active projects without a budget', n
      ? `=COUNTIFS(${A}$${statusCol}$${FIRST_DATA_ROW}:$${statusCol}$${f - 1},"${STATUS_ACTIVE}",` +
        `${A}$${budCol}$${FIRST_DATA_ROW}:$${budCol}$${f - 1},"")`
      : '=0'],
  ];
  sum.getRange(r0, 3, lines.length, 1).setValues(lines.map(([label]) => [label]));
  sum.getRange(r0, 4, lines.length, 1).setFormulas(lines.map(([, formula]) => [formula]));
  sum.getRange(r0, 3).setFontWeight('bold');
  sum.getRange(r0 + 1, 4, lines.length - 2, 1).setNumberFormat(DIFF_FMT);
  sum.getRange(r0 + lines.length - 1, 4).setNumberFormat('0');
}

// ─── Month change, counting, report ──────────────────────────────────────────

/** What-if values belong to one month; moving to another month clears them. */
function confirmMonthChange_(sh, month, ui) {
  const prev = sh.getRange(MONTH_KEY_CELL).getDisplayValue().trim();
  if (!prev || prev === month) return true;
  const grid = readGrid_(sh);
  if (!countWhatIf_(sh, grid, grid.projects, [])) return true;

  const choice = ui.alert(
    'Planning month changed',
    `The what-if values were planned for ${prev}, but ${CONFIG.MONTH_CELL} now says ${month}.\n\n` +
    'OK clears them and syncs the new month. Cancel stops without changes.',
    ui.ButtonSet.OK_CANCEL);
  if (choice !== ui.Button.OK) return false;
  grid.persons.forEach(p => sh.getRange(FIRST_DATA_ROW, p.col + 1, grid.projects.length, 1).clearContent());
  return true;
}

/**
 * Counts non-blank What-if cells that lie in any of `rows` (across all people)
 * or in any of `people` (across all rows).
 */
function countWhatIf_(sh, grid, rows, people) {
  const n = grid.projects.length;
  if (!n) return 0;
  const vals = sh.getRange(FIRST_DATA_ROW, 1, n, grid.lastCol).getValues();
  const cells = new Set();
  const add = (row, person) => {
    if (vals[row - FIRST_DATA_ROW][person.col] !== '') cells.add(`${row}|${person.col}`);
  };
  rows.forEach(r => grid.persons.forEach(p => add(r.row, p)));
  people.forEach(p => grid.projects.forEach(r => add(r.row, p)));
  return cells.size;
}

function report_(grid, src, added) {
  const goneProjects = grid.projects.filter(p => p.id && !src.projects.has(p.id)).length;
  const gonePeople = grid.persons.filter(p => !src.team.has(p.name)).length;
  const lines = [
    `Month: ${src.month}`,
    `Projects: ${grid.projects.length} rows (${added.projects.length} added, ${goneProjects} gone)`,
    `People: ${grid.persons.length} (${added.people.length} added, ${gonePeople} not in People tab)`,
  ];
  if (added.projects.length) lines.push('', 'Added projects:', ...added.projects.map(n => `  • ${n}`));
  if (added.people.length) lines.push('', 'Added people:', ...added.people.map(n => `  • ${n}`));
  if (!src.actualRows) lines.push('', `Warning: "${CONFIG.ALLOCATIONS_SHEET}" has no rows for ${src.month}.`);
  if (src.otherPeople.size) {
    lines.push('', `Hours from people not on the People tab are in "Other": ${[...src.otherPeople].sort(cmp_).join(', ')}`);
  }
  if (src.unknownProjects.size) {
    lines.push('', `Ignored allocations for projects not in "${CONFIG.PROJECTS_SHEET}": ${[...src.unknownProjects].sort(cmp_).join(', ')}`);
  }
  if (goneProjects || gonePeople) lines.push('', 'Grey rows/columns are gone. Use Planning → Prune to remove them.');
  return lines.join('\n');
}

// ─── Small helpers ───────────────────────────────────────────────────────────

function normMonth_(v) {
  if (v instanceof Date) return Utilities.formatDate(v, Session.getScriptTimeZone(), 'yyyy-MM');
  return String(v).trim();
}

function key_(projectId, person) {
  return `${projectId}|${person}`;
}

function norm_(s) {
  return String(s).trim().toLowerCase();
}

function cmp_(a, b) {
  return a.localeCompare(b, undefined, { sensitivity: 'base' });
}

function colA1_(c) {
  let s = '';
  for (let n = c; n > 0; n = Math.floor((n - 1) / 26)) {
    s = String.fromCharCode(65 + ((n - 1) % 26)) + s;
  }
  return s;
}
