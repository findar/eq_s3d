// feedback.ts — the Feedback section in the side panel (zone-generator-edits
// Req 4): a text field and Apply (Enter applies too), what the edit route said
// under it, and Undo / Redo through the zone's versions.
//
// Apply sends the text against the version on screen (POST /api/edit, through
// the host: main.ts owns the busy state and opening versions). An accepted
// edit opens the new version and tints its Affected_Set rooms; one that isn't
// keeps the open version and says why. Undo opens the open version's parent,
// Redo the newest version whose parent is the open one (decision 2: parent
// links from the versions listing, no server call).
//
// The section lives inside #panel-body, so it shows only while a build is
// open. Its field is an <input>, which controls.ts already keeps the movement
// keys out of; main.ts stops them on the section's buttons.

import type { EditResult, ZoneVersionEntry } from "./api";

export interface FeedbackHost {
  /** Send the edit against the open version; resolves with the route's answer
   *  (the new version already open when it applied). Rejects with the error's words. */
  edit: (text: string) => Promise<EditResult>;
  /** Open version `n` of the open zone. */
  open: (n: number) => void;
}

const $ = (id: string) => document.getElementById(id)!;
const textEl = $("feedback-text") as HTMLInputElement;
const applyBtn = $("feedback-apply") as HTMLButtonElement;
const undoBtn = $("feedback-undo") as HTMLButtonElement;
const redoBtn = $("feedback-redo") as HTMLButtonElement;
const msgEl = $("feedback-msg");

let host: FeedbackHost | null = null;
let open: number | null = null;
let versions: ZoneVersionEntry[] = [];
let parentOfOpen: number | null = null;
let busy = false;        // any request of the page (Generate, a rebuild, opening a version)
let sending = false;     // this section's edit

/** The version Undo opens: the open one's parent, when the zone still has it. */
function undoTarget(): number | null {
  if (parentOfOpen == null) return null;
  return versions.some((v) => v.n === parentOfOpen) ? parentOfOpen : null;
}

/** The version Redo opens: the newest whose parent is the open one. */
function redoTarget(): number | null {
  const kids = versions.filter((v) => v.parent === open).map((v) => v.n);
  return kids.length ? Math.max(...kids) : null;
}

function sync(): void {
  const idle = !busy && !sending && open !== null;
  applyBtn.disabled = !idle || textEl.value.trim() === "";
  applyBtn.textContent = sending ? "Applying…" : "Apply";
  applyBtn.setAttribute("aria-busy", String(sending));
  const u = undoTarget(), r = redoTarget();
  undoBtn.disabled = !idle || u === null;
  redoBtn.disabled = !idle || r === null;
  undoBtn.title = u === null ? "No earlier version this one came from" : `Open v${u}, the version this one came from`;
  redoBtn.title = r === null ? "No version was made from this one" : `Open v${r}, the newest version made from this one`;
}

function opWords(op: unknown): string {
  if (op && typeof op === "object" && "op" in op) {
    const o = op as { op: unknown; target?: unknown };
    return o.target ? `${String(o.op)} ${String(o.target)}` : String(o.op);
  }
  return typeof op === "string" ? op : JSON.stringify(op);
}

function addLine(text: string, cls = ""): void {
  const li = document.createElement("li");
  li.textContent = text;
  if (cls) li.className = cls;
  msgEl.appendChild(li);
}

function clearMsg(): void {
  msgEl.innerHTML = "";
  msgEl.className = "";
}

/** The route's answer: its notes, then why nothing was built when nothing was. */
function showResult(res: EditResult): void {
  clearMsg();
  if (res.applied) {
    addLine(`v${res.parent} → v${res.version}` + (res.how ? ` (${res.how} rebuild)` : ""), "head");
  } else {
    msgEl.className = "warn";
    addLine(`Not applied: v${res.parent} stays open.`, "head");
  }
  for (const n of res.notes) addLine(n);
  for (const r of res.invalid) addLine(`Invalid: ${opWords(r.op)}: ${r.reason}`, "refusal");
  // A rejected op's reason is often its note already: say it once.
  for (const r of res.rejected) {
    if (!res.notes.includes(r.reason)) addLine(`Rejected: ${opWords(r.op)}: ${r.reason}`, "refusal");
  }
  if (!res.applied && res.diagnostics.length) {
    const checks = [...new Set(res.diagnostics.flatMap((d) => d.checks))];
    addLine(`Every build failed the checks${checks.length ? ` (${checks.join(", ")})` : ""}.`, "refusal");
  }
  if (res.help) addLine(res.help, "help");
}

async function apply(): Promise<void> {
  const text = textEl.value.trim();
  if (!host || busy || sending || open === null || text === "") return;
  console.log(`[input] feedback: v${open} "${text}"`);
  sending = true;
  sync();
  clearMsg();
  addLine("Applying…", "head");
  try {
    const res = await host.edit(text);
    showResult(res);
    if (res.applied) textEl.value = "";
  } catch (err) {
    clearMsg();
    msgEl.className = "error";
    addLine(String((err as Error)?.message ?? err));
  } finally {
    sending = false;
    sync();
  }
}

function step(target: () => number | null, what: string): void {
  const n = target();
  if (!host || busy || sending || n === null) return;
  console.log(`[input] ${what}: v${open} -> v${n}`);
  clearMsg();
  host.open(n);
}

/** Wire the section to the page. */
export function initFeedback(h: FeedbackHost): void {
  host = h;
  sync();
}

/** The open version, its parent and the zone's versions changed (or a new zone opened). */
export function setFeedbackBuild(n: number | null, parent: number | null, list: ZoneVersionEntry[],
                                 zoneChanged: boolean): void {
  if (zoneChanged) clearMsg();
  open = n;
  parentOfOpen = parent;
  versions = list;
  sync();
}

/** A request of the page started or ended: Apply, Undo and Redo wait for it. */
export function setFeedbackBusy(on: boolean): void {
  busy = on;
  sync();
}

textEl.addEventListener("input", sync);
textEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    apply();
  }
});
applyBtn.addEventListener("click", () => apply());
undoBtn.addEventListener("click", () => step(undoTarget, "undo"));
redoBtn.addEventListener("click", () => step(redoTarget, "redo"));
sync();
