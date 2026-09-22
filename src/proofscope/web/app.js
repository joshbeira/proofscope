"use strict";
const $ = (id) => document.getElementById(id);
const editor = $("source");
const storageKey = "proofscope.source.v1";
let result = null;
let revision = 0;
let selected = null;
let lastSource = "";
let examples = [];
const symbol = (value) =>
  (value || "")
    .replace(/\bAND\b/g, "∧")
    .replace(/\bOR\b/g, "∨")
    .replace(/\bIMP\b/g, "→")
    .replace(/\bNOT\b/g, "¬")
    .replace(/\bFALSE\b/g, "⊥");
function node(tag, text, className) {
  const item = document.createElement(tag);
  if (text !== undefined) item.textContent = text;
  if (className) item.className = className;
  return item;
}
function status(text, state = "neutral") {
  $("status").textContent = text;
  $("status").className = `status ${state}`;
}
function save() {
  try {
    localStorage.setItem(storageKey, editor.value);
  } catch {
    /* Storage is optional. */
  }
}
function updateLines() {
  $("line-numbers").textContent = editor.value
    .split("\n")
    .map((_, i) => i + 1)
    .join("\n");
  $("line-numbers").scrollTop = editor.scrollTop;
}
function resetResults() {
  result = null;
  selected = null;
  $("trace").replaceChildren();
  $("diagnostics").replaceChildren();
  $("truth-table").replaceChildren();
  $("countermodel").replaceChildren();
  $("model-summary").textContent =
    "Verify this revision to analyze its premises and goal.";
  $("selection-note").textContent = "";
  $("scrubber").hidden = true;
  for (const key of ["inferences", "premises", "max_depth", "models"])
    $(`metric-${key}`).textContent = "—";
}
function changed() {
  revision += 1;
  resetResults();
  updateLines();
  save();
  status("Edited · verify to check this revision");
}
editor.addEventListener("input", changed);
editor.addEventListener("scroll", () => {
  $("line-numbers").scrollTop = editor.scrollTop;
});
editor.addEventListener("keydown", (event) => {
  if (event.key === "Tab") {
    event.preventDefault();
    editor.setRangeText(
      "    ",
      editor.selectionStart,
      editor.selectionEnd,
      "end",
    );
    changed();
  }
});
document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    if (!$("verify").disabled) verify();
  }
});
function selectTab(name) {
  document.querySelectorAll("[data-tab]").forEach((tab) => {
    const active = tab.dataset.tab === name;
    tab.setAttribute("aria-selected", String(active));
    tab.tabIndex = active ? 0 : -1;
    $(`${tab.dataset.tab}-panel`).hidden = !active;
  });
}
document.querySelectorAll("[data-tab]").forEach((tab, index, tabs) => {
  tab.addEventListener("click", () => selectTab(tab.dataset.tab));
  tab.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const next =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? tabs.length - 1
          : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) %
            tabs.length;
    selectTab(tabs[next].dataset.tab);
    tabs[next].focus();
  });
});
function renderTrace() {
  if (!result) return;
  const scrollTop = $("trace").scrollTop;
  const restoreFocus = document.activeElement?.classList.contains("trace-row");
  const limit = Number($("step").value);
  const active = result.trace.find((event) => event.id === selected);
  const dependencies = new Set(active?.dependencies || []);
  $("trace").replaceChildren();
  for (const event of result.trace.slice(0, limit)) {
    const row = node("button", undefined, "trace-row");
    row.type = "button";
    row.dataset.eventId = String(event.id);
    row.setAttribute(
      "aria-label",
      `Step ${event.id}, ${event.rule || event.kind}, ${event.formula || ""}, line ${event.line}`,
    );
    row.setAttribute("aria-pressed", String(selected === event.id));
    if (event.id === selected) row.classList.add("selected");
    if (dependencies.has(event.id)) row.classList.add("dependency");
    if (event.kind === "DERIVE") row.classList.add("goal");
    const body = node(
      "span",
      undefined,
      `event-body${event.depth ? " nested" : ""}`,
    );
    body.append(node("span", symbol(event.formula) || "—", "event-formula"));
    const detail = node("span", event.rule || event.kind, "event-rule");
    detail.append(
      node(
        "small",
        `L${event.line}${event.depth ? ` · scope ${event.scope}` : ""}`,
      ),
    );
    row.append(
      node("span", String(event.id).padStart(2, "0"), "event-id"),
      body,
      detail,
    );
    row.addEventListener("click", () => {
      selected = event.id;
      $("selection-note").textContent =
        `Step ${event.id} · line ${event.line} · ` +
        (event.dependencies.length
          ? `depends on ${event.dependencies.join(", ")} (highlighted)`
          : "no inference dependencies");
      renderTrace();
      const start = lastSource
        .split("\n")
        .slice(0, event.line - 1)
        .reduce((n, line) => n + line.length + 1, 0);
      editor.setSelectionRange(
        start,
        start + (lastSource.split("\n")[event.line - 1] || "").length,
      );
    });
    $("trace").append(row);
  }
  $("trace").scrollTop = scrollTop;
  if (restoreFocus && selected !== null) {
    $("trace")
      .querySelector(`[data-event-id="${selected}"]`)
      ?.focus({ preventScroll: true });
  }
  $("step-label").textContent = `${limit} / ${result.trace.length}`;
}
$("step").addEventListener("input", () => {
  selected = null;
  $("selection-note").textContent = "";
  renderTrace();
});
function renderModels(semantics) {
  $("truth-table").replaceChildren();
  $("countermodel").replaceChildren();
  if (!semantics) {
    $("model-summary").textContent =
      "Resolve the syntax error before checking the sequent.";
    return;
  }
  if (semantics.status === "limit") {
    $("model-summary").textContent =
      `${semantics.message} No semantic verdict was produced.`;
    return;
  }
  $("model-summary").textContent = semantics.entailed
    ? `The premises entail the goal. All ${semantics.assignments_checked} truth assignments were checked.` +
      (semantics.vacuous
        ? " The premises are inconsistent, so this entailment is vacuous."
        : "") +
      (!result.valid
        ? " Your submitted proof still contains an invalid or missing step."
        : "")
    : "A counterexample exists: the premises can all be true while the goal is false.";
  if (semantics.countermodel !== null) {
    const card = node("div", "COUNTERMODEL", "counterexample-card");
    card.append(
      node(
        "code",
        Object.entries(semantics.countermodel)
          .map(([name, value]) => `${name} = ${value ? "true" : "false"}`)
          .join("  ·  ") || "No atoms: the goal is false.",
      ),
    );
    $("countermodel").append(card);
  }
  const table = node("table");
  table.append(
    node(
      "caption",
      `Truth table${semantics.table_truncated ? " (first 64 assignments)" : ""}`,
      "sr-only",
    ),
  );
  const head = node("thead"),
    headings = node("tr");
  [...semantics.atoms, "Premises", "Goal"].forEach((text) => {
    const th = node("th", text);
    th.scope = "col";
    headings.append(th);
  });
  head.append(headings);
  table.append(head);
  const body = node("tbody");
  for (const row of semantics.rows) {
    const tr = node("tr", undefined, row.counterexample ? "counter" : "");
    [
      ...semantics.atoms.map((name) => row.assignment[name]),
      row.premises_hold,
      row.goal_holds,
    ].forEach((value) => tr.append(node("td", value ? "T" : "F")));
    body.append(tr);
  }
  table.append(body);
  $("truth-table").append(table);
  if (semantics.table_truncated)
    $("model-summary").append(" Table preview shows the first 64 assignments.");
}
async function verify() {
  const version = revision;
  const source = editor.value;
  $("verify").disabled = true;
  status("Checking proof steps and truth assignments…");
  try {
    const response = await fetch("/api/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source }),
    });
    const data = await response.json();
    if (version !== revision) return;
    if (!response.ok) throw new Error(data.error || "Verification failed.");
    result = data;
    lastSource = source;
    selected = null;
    status(
      data.valid
        ? "✓ Proof verified · goal established in global scope"
        : "Proof rejected · see Proof trace for details",
      data.valid ? "good" : "bad",
    );
    $("diagnostics").replaceChildren();
    for (const diagnostic of data.diagnostics) {
      const item = node("div", undefined, "diagnostic");
      item.append(
        node(
          "strong",
          `${diagnostic.code} · line ${diagnostic.line}:${diagnostic.column}`,
        ),
        node("span", diagnostic.message),
      );
      if (diagnostic.hint) item.append(node("p", diagnostic.hint));
      $("diagnostics").append(item);
    }
    $("step").max = String(Math.max(1, data.trace.length));
    $("step").value = $("step").max;
    $("scrubber").hidden = !data.trace.length;
    $("selection-note").textContent = "";
    for (const key of ["inferences", "premises", "max_depth"])
      $(`metric-${key}`).textContent = data.statistics[key];
    $("metric-models").textContent = data.semantics?.assignments_checked ?? "—";
    renderTrace();
    renderModels(data.semantics);
  } catch (error) {
    if (version === revision)
      status(`Unable to verify: ${error.message}`, "bad");
  } finally {
    $("verify").disabled = false;
  }
}
$("verify").addEventListener("click", verify);
$("new").addEventListener("click", () => {
  editor.value =
    "DERIVE A -> A\n\nASSUME A\nEND\nAPPLY IMP_INTRO A, A\nCONCLUDE\n";
  $("filename").textContent = "untitled.proof";
  $("examples").value = "";
  changed();
  editor.focus();
});
$("download").addEventListener("click", () => {
  const url = URL.createObjectURL(
    new Blob([editor.value], { type: "text/plain;charset=utf-8" }),
  );
  const link = node("a");
  link.href = url;
  link.download = $("filename").textContent;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
$("examples").addEventListener("change", () => {
  const example = examples.find((item) => item.name === $("examples").value);
  if (!example) return;
  editor.value = example.source;
  $("filename").textContent = `${example.name.replace(/^\d+-/, "")}.proof`;
  changed();
  selectTab("trace");
  verify();
});
const rulebook = [
  ["AND_INTRO A, B", "Both available → A ∧ B."],
  [
    "AND_ELIM A AND B, A",
    "Select the desired conjunct; only the conjunction must be available.",
  ],
  ["OR_INTRO A, B", "Either available → A ∨ B."],
  [
    "OR_ELIM A OR B, NOT A",
    "Disjunctive syllogism → B. Both inputs must be available.",
  ],
  [
    "OR_CASES A OR B, C",
    "Available disjunction + closed sibling subproofs A ⊢ C and B ⊢ C → C.",
  ],
  [
    "IMP_INTRO A, B",
    "Closed subproof A ⊢ B → A → B. Also allowed if B is already available.",
  ],
  ["IMP_ELIM A IMP B, A", "Modus ponens → B. Arguments may be reversed."],
  ["NOT_INTRO A", "Closed subproof A ⊢ ⊥ → ¬A."],
  ["NOT_ELIM A, NOT A", "Both available → ⊥."],
  ["DNE NOT NOT A", "Explicit classical double-negation elimination → A."],
  ["EXPLOSION FALSE, A", "Available contradiction → any target A."],
  ["REITERATE A", "Record an already available formula."],
];
for (const [usage, description] of rulebook) {
  const card = node("div", undefined, "rule-card");
  card.append(node("code", usage), node("p", description));
  $("rules").append(card);
}
async function initialize() {
  try {
    const response = await fetch("/api/examples");
    if (!response.ok) throw new Error("Example library is unavailable.");
    examples = await response.json();
    examples.forEach((example) => {
      const option = node(
        "option",
        example.name.replace(/^\d+-/, "").replaceAll("-", " "),
      );
      option.value = example.name;
      $("examples").append(option);
    });
    let saved = null;
    try {
      saved = localStorage.getItem(storageKey);
    } catch {
      /* Storage is optional. */
    }
    editor.value =
      saved ??
      examples.find((example) => example.name.includes("contraposition"))
        .source;
    if (saved !== null) $("filename").textContent = "saved-session.proof";
    updateLines();
    await verify();
  } catch (error) {
    status(error.message, "bad");
  }
}
initialize();
