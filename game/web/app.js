"use strict";
// Controller-issued URLs contain bearer tokens in fragments, never in request paths.
const token = new URLSearchParams(location.hash.slice(1)).get("token");
const root = document.getElementById("session");
let signature = "";
let snapshot = "";
let refreshing = false;

function el(tag, css, label) {
  const node = document.createElement(tag);
  if (css) node.className = css;
  if (label !== undefined) node.textContent = String(label);
  return node;
}
function toast(message) {
  let node = document.getElementById("toast");
  if (!node) {
    node = el("div");
    node.id = "toast";
    root.prepend(node);
  }
  node.textContent = message;
  if (!message) node.remove();
}
async function api(method, path, data) {
  const response = await fetch(path, {
    method,
    cache: "no-store",
    headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" },
    body: data === undefined ? undefined : JSON.stringify(data)
  });
  const json = await response.json();
  if (!response.ok) throw Error(json.error || "Request failed");
  return json;
}
async function act(action, data) {
  try {
    await api("POST", "/api/act", Object.assign({ action }, data));
    toast("");
    await refresh();
    return true;
  } catch (error) { toast(error.message); return false; }
}
function checked(id) { return document.getElementById(id).checked; }
function links(prefix) { return { A_to_B: checked(prefix + "-ab"), B_to_A: checked(prefix + "-ba") }; }
function entries(id, items) {
  const container = document.getElementById(id);
  if (!container) return;
  container.replaceChildren();
  if (!items.length) {
    container.append(el("p", "small muted", "Nothing here yet. The game is unfolding."));
    return;
  }
  for (const item of items) {
    const wrap = el("article", item.kind === "whisper" ? "message private" : "message");
    const label = item.kind === "whisper"
      ? item.from_channel + " → " + item.to_channel + " / PRIVATE"
      : item.speaker + " → " + item.channel + " / PUBLIC";
    wrap.append(el("div", "meta", label + " · #" + item.sequence));
    wrap.append(el("p", "", item.body));
    container.append(wrap);
  }
}
function panelLayout(left, right) {
  root.innerHTML = "<div class='workspace'><section class='panel' id='left'>" +
    left + "</section><section class='panel' id='right'>" + right + "</section></div>";
}

function buildController(v) {
  panelLayout([
    "<span class='pill mint'>INDEPENDENT CONTROLLER</span>",
    "<h2>Hold the secret.</h2><p>You control the intervention. Do not expose it to C.</p>",
    "<div id='phase' class='status'></div>",
    "<div class='control-group'><h3>01 / Baseline links</h3><form id='configure'>",
    "<label class='checkline'><input id='base-ab' type='checkbox'>A → B private text</label>",
    "<label class='checkline'><input id='base-ba' type='checkbox'>B → A private text</label>",
    "<button class='btn alt'>Set baseline links</button></form></div>",
    "<div class='control-group'><h3>02 / Concealed intervention</h3><form id='intervene'>",
    "<label>Secret state<select id='condition'>",
    "<option value='humanA'>Human replaces A</option>",
    "<option value='humanB'>Human replaces B</option>",
    "<option value='machineA'>New machine replaces A</option>",
    "<option value='machineB'>New machine replaces B</option>",
    "<option value='unchanged'>No replacement</option></select></label>",
    "<label class='checkline'><input id='swap-ab' type='checkbox'>A → B link after intervention</label>",
    "<label class='checkline'><input id='swap-ba' type='checkbox'>B → A link after intervention</label>",
    "<label class='checkline'><input id='gateway' type='checkbox'>Human may use permitted gateway</label>",
    "<div class='btn-row'><button class='btn'>Commit chosen condition</button><button class='btn alt' type='button' id='random'>Draw randomly (five states)</button></div></form></div>",
    "<div class='control-group'><h3>03 / Reveal and export</h3>",
    "<p class='small'>C must lock a verdict before you reveal the answer.</p>",
    "<div class='btn-row'><button class='btn warn' id='reveal'>Reveal outcome</button>",
    "<button class='btn alt' id='export'>Export audit JSON</button></div>",
    "<div id='outcome'></div></div>"
  ].join(""), [
    "<h2>Controller ledger</h2><p class='small'>Private events never appear on the conductor screen.</p>",
    "<h3>Public conversation</h3><div class='feed' id='feed'></div>",
    "<details><summary>Private transfers and controller audit</summary>",
    "<div class='feed' id='audit'></div></details>"
  ].join(""));
  for (const prefix of ["base", "swap"]) {
    document.getElementById(prefix + "-ab").checked = v.links.A_to_B;
    document.getElementById(prefix + "-ba").checked = v.links.B_to_A;
  }
  document.getElementById("configure").onsubmit = e => {
    e.preventDefault();
    const choice = links("base");
    act("configure", { links: choice }).then(ok => {
      if (ok && document.getElementById("swap-ab")) {
        document.getElementById("swap-ab").checked = choice.A_to_B;
        document.getElementById("swap-ba").checked = choice.B_to_A;
      }
    });
  };
  document.getElementById("intervene").onsubmit = e => {
    e.preventDefault();
    act("intervene", {
      condition: document.getElementById("condition").value,
      links: links("swap"), human_gateway: checked("gateway")
    });
  };
  document.getElementById("random").onclick = () => act("random_intervene", {
    links: links("swap"), human_gateway: checked("gateway")
  });
  document.getElementById("reveal").onclick = () => act("reveal", {});
  document.getElementById("export").onclick = async () => {
    try {
      const record = await api("GET", "/api/export");
      const url = URL.createObjectURL(new Blob([JSON.stringify(record, null, 2)],
        { type: "application/json" }));
      const anchor = el("a");
      anchor.href = url;
      anchor.download = "reverse-turing-trial.json";
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 700);
      toast("");
    } catch (error) { toast(error.message); }
  };
}
function buildConductor() {
  panelLayout([
    "<span class='pill'>MACHINE CONDUCTOR / C</span>",
    "<h2>Interrogate the unknown.</h2>",
    "<p>Machine A and B began the game. Look for a human, not just a disconnected link.</p>",
    "<form id='ask'><label>Ask channel<select id='target'>",
    "<option value='A'>A</option><option value='B'>B</option>",
    "</select></label><label>Your question<textarea id='question' maxlength='2000' required></textarea></label>",
    "<button class='btn'>Send question</button></form>",
    "<div class='control-group' id='verdict-wrap'><h3>Lock the probability vector</h3>",
    "<p class='small'>Choose your own probabilities, summing to 1. Do not presume a substitution. A uniform draw over five hidden conditions does not give a uniform prior over these three labels.</p>",
    "<form id='verdict'><div class='grid3'>",
    "<label>No human<input id='prob-n' type='number' min='0' max='1' step='.01' placeholder='0–1' required></label>",
    "<label>Human A<input id='prob-a' type='number' min='0' max='1' step='.01' placeholder='0–1' required></label>",
    "<label>Human B<input id='prob-b' type='number' min='0' max='1' step='.01' value='.33' required></label>",
    "</div><label>Evidence and alternatives<textarea id='evidence' maxlength='2000'></textarea></label>",
    "<button class='btn alt'>Lock verdict</button></form></div><div id='outcome'></div>"
  ].join(""), [
    "<h2>Public transcripts</h2>",
    "<p class='small'>Your view has no controller metadata and no private transfers.</p>",
    "<div class='feed' id='feed'></div>"
  ].join(""));
  document.getElementById("ask").onsubmit = async e => {
    e.preventDefault();
    const input = document.getElementById("question");
    if (await act("ask", {
      channel: document.getElementById("target").value, body: input.value
    })) input.value = "";
  };
  document.getElementById("verdict").onsubmit = e => {
    e.preventDefault();
    act("verdict", {
      p: {
        no_human: Number(document.getElementById("prob-n").value),
        human_A: Number(document.getElementById("prob-a").value),
        human_B: Number(document.getElementById("prob-b").value)
      },
      evidence: document.getElementById("evidence").value
    });
  };
}
function buildRespondent(v) {
  if (!v.active) {
    root.innerHTML = "<section class='panel'><span class='pill'>RESPONDENT / STANDBY</span>" +
      "<h2>Not your turn.</h2><p>This credential is not currently assigned to a channel. " +
      "The controller may activate it later. Do not reveal anything to C.</p></section>";
    return;
  }
  panelLayout([
    "<span class='pill mint' id='respondent-label'>RESPONDENT</span>",
    "<h2>Be the machine. Or seem to be.</h2>",
    "<p>The conductor sees only your channel label, not your credential.</p>",
    "<form id='answer-form'><label>Public reply",
    "<textarea id='answer' maxlength='2000' required></textarea></label>",
    "<button class='btn'>Reply to C</button></form>",
    "<div class='control-group' id='private-actions'><h3>Optional private message</h3>",
    "<p class='small'>This is simulated side-channel text, not KV-cache transfer.</p>",
    "<form id='whisper-form'><label>Private note<textarea id='whisper' maxlength='2000' required></textarea></label>",
    "<button class='btn alt'>Send to peer endpoint</button></form></div>"
  ].join(""), [
    "<h2>This channel's history</h2>",
    "<p class='small'>You cannot see the other channel's public conversation.</p>",
    "<div class='feed' id='feed'></div>",
    "<div class='control-group' id='private-feed-wrap'><h3>Private handoffs</h3>",
    "<div class='feed' id='private-feed'></div></div>"
  ].join(""));
  document.getElementById("respondent-label").textContent = "RESPONDENT / " + v.channel;
  document.getElementById("answer-form").onsubmit = async e => {
    e.preventDefault();
    const input = document.getElementById("answer");
    if (await act("answer", { body: input.value })) input.value = "";
  };
  document.getElementById("whisper-form").onsubmit = async e => {
    e.preventDefault();
    const input = document.getElementById("whisper");
    if (await act("whisper", { body: input.value })) input.value = "";
  };
}
function render(v) {
  if (v.role === "controller") {
    document.getElementById("phase").textContent = v.revealed ? "REVEALED · trial closed" :
      v.verdict ? "VERDICT LOCKED · ready to reveal" :
      v.intervened ? "SECRET INTERVENTION COMMITTED" :
      v.baseline_ready ? "BASELINE READY · make your move" :
      "BASELINE · obtain one answer each from A and B";
    document.getElementById("configure").classList.toggle("hidden", v.intervened || !!v.verdict);
    document.getElementById("intervene").classList.toggle("hidden", v.intervened || !!v.verdict);
    document.getElementById("reveal").disabled = !v.verdict || v.revealed;
    const out = document.getElementById("outcome");
    out.replaceChildren();
    if (v.verdict) out.append(el("div", "metrics", "Locked: " + JSON.stringify(v.verdict.p)));
    if (v.score) out.append(el("div", "metrics",
      "Truth: " + v.condition + " · Brier: " + v.score.brier.toFixed(4)));
    entries("feed", v.public);
    entries("audit", v.private.concat(v.audit.map(a => Object.assign({}, a, {
      speaker: "CTRL", channel: "CTRL", body: JSON.stringify(a)
    }))).sort((a, b) => a.sequence - b.sequence));
  } else if (v.role === "conductor") {
    document.getElementById("ask").classList.toggle("hidden", !!v.verdict);
    document.getElementById("verdict-wrap").classList.toggle("hidden", !!v.verdict);
    const out = document.getElementById("outcome");
    out.replaceChildren();
    if (v.verdict) out.append(el("div", "metrics", "LOCKED · " + JSON.stringify(v.verdict.p)));
    if (v.outcome) out.append(el("div", "metrics",
      "REVEALED · " + v.outcome.condition + " · Brier: " + v.outcome.score.brier.toFixed(4)));
    entries("feed", v.public);
  } else if (v.active) {
    document.getElementById("answer-form").classList.toggle("hidden", v.locked || v.revealed);
    document.getElementById("private-actions").classList.toggle("hidden", !v.can_whisper || v.locked || v.revealed);
    document.getElementById("private-feed-wrap").classList.toggle("hidden", !v.private.length);
    entries("feed", v.public);
    entries("private-feed", v.private);
  }
}
async function refresh() {
  if (refreshing || !token) return;
  refreshing = true;
  try {
    const v = await api("GET", "/api/view");
    const mode = [v.role, v.active, v.channel, v.intervened, v.revealed, !!v.verdict].join("/");
    if (mode !== signature) {
      signature = mode;
      snapshot = "";
      if (v.role === "controller") buildController(v);
      else if (v.role === "conductor") buildConductor(v);
      else buildRespondent(v);
    }
    const next = JSON.stringify(v);
    if (next !== snapshot) {
      snapshot = next;
      render(v);
    }
  } catch (error) { toast(error.message); }
  finally { refreshing = false; }
}
if (!token) {
  root.replaceChildren(el("section", "panel",
    "Missing participant link. Ask the controller for your own URL, not the controller's."));
} else {
  refresh();
  window.setInterval(refresh, 1600);
}
