"use strict";

// ── Global state ──────────────────────────────────────────────────────────────
const state = {
  unlocked: false,
  activeView: "dashboardView",
  activeProjectId: null,
  projects: [],
  lastOutput: null,
  user: null,
  googleConfigured: false,
};

const $ = (id) => document.getElementById(id);

// ── API helper ────────────────────────────────────────────────────────────────
async function api(path, options = {}) {
  const response = await fetch(path, options);
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(payload.detail || `Request failed (${response.status})`);
  }
  return payload;
}

function requireUnlocked() {
  if (!state.unlocked) throw new Error("Sign in first.");
}

function activeProject() {
  return state.projects.find((p) => p.id === state.activeProjectId) || null;
}

// ── Redirect overlay ──────────────────────────────────────────────────────────
function showOverlay(text) {
  const overlay = $("redirectOverlay");
  if (text) overlay.querySelector(".redirect-title").textContent = text;
  overlay.classList.remove("hidden");
}

function hideOverlay() {
  $("redirectOverlay").classList.add("hidden");
}

// ── Auth: license key login ───────────────────────────────────────────────────
async function login(event) {
  event.preventDefault();
  const btn = $("licenseSubmitButton");
  btn.disabled = true;
  btn.textContent = "Checking…";
  try {
    const payload = await api("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ license_key: $("licenseKey").value }),
    });
    state.unlocked = payload.ok;
    state.user = { name: "License user", email: "license access", picture: "" };
    enterWorkspace("License active");
  } catch (error) {
    $("loginMessage").textContent = error.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "Enter workspace";
  }
}

// ── Auth: Google SSO ──────────────────────────────────────────────────────────
function startGoogleLogin() {
  if (!state.googleConfigured) {
    $("loginMessage").textContent =
      "Google SSO is not configured yet. Add GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI in Railway variables.";
    return;
  }
  showOverlay("Redirecting to Google…");
  api("/api/auth/google/url")
    .then((payload) => {
      window.location.href = payload.url;
    })
    .catch((error) => {
      hideOverlay();
      $("loginMessage").textContent = error.message;
    });
}

async function unlockFromGoogle() {
  showOverlay("Finalising Google sign-in…");
  try {
    const payload = await api("/api/auth/google/me");
    state.unlocked = true;
    state.user = payload.user;
    window.history.replaceState({}, document.title, "/");
    enterWorkspace(payload.user?.email || "Google active");
  } catch (error) {
    hideOverlay();
    $("loginMessage").textContent = error.message;
    window.history.replaceState({}, document.title, "/");
  }
}

async function logout() {
  try {
    await fetch("/api/auth/google/logout", { method: "POST" });
  } catch (_) {
    // License sessions don't need server logout — that's fine
  }
  state.unlocked = false;
  state.activeProjectId = null;
  state.projects = [];
  state.user = null;
  renderUserBadge();
  $("appView").classList.add("hidden");
  $("loginView").classList.remove("hidden");
  hideOverlay();
}

// ── Auth: handle Google callback redirect (?google_auth=success/error) ────────
function handleAuthRedirect() {
  const params = new URLSearchParams(window.location.search);
  const status = params.get("google_auth");
  if (status === "success") {
    unlockFromGoogle();
    return true;
  }
  if (status === "error") {
    $("loginMessage").textContent = googleErrorMessage(params.get("reason"));
    window.history.replaceState({}, document.title, "/");
    return true;
  }
  return false;
}

// ── Auth: boot — check existing session on page load ─────────────────────────
async function bootAuthState() {
  // Load Google status first so the button is correct before anything else
  await loadGoogleStatus();

  // If we just came back from Google, the redirect handler has already started
  const params = new URLSearchParams(window.location.search);
  if (params.get("google_auth")) return;

  // Check for existing Google session cookie
  try {
    const payload = await api("/api/auth/session");
    if (!payload.ok) return;
    state.unlocked = true;
    state.user = payload.user;
    enterWorkspace(payload.user?.email || "Google active");
  } catch (_) {
    state.unlocked = false;
  }
}

async function loadGoogleStatus() {
  const statusEl = $("googleStatus");
  const textEl = $("googleStatusText");
  const btn = $("googleLoginButton");
  try {
    const status = await api("/api/auth/google/status");
    state.googleConfigured = status.configured;
    if (status.configured) {
      statusEl.className = "auth-status ready";
      textEl.textContent = "Google SSO is active — click to sign in.";
      btn.disabled = false;
      btn.classList.add("google-button-ready");
    } else {
      statusEl.className = "auth-status offline";
      textEl.textContent = "Google SSO inactive — add credentials in Railway to activate.";
      btn.disabled = false; // still clickable so we can show an explanation
      btn.classList.add("google-button-unconfigured");
    }
  } catch (_) {
    statusEl.className = "auth-status offline";
    textEl.textContent = "Google SSO status unavailable.";
    btn.disabled = false;
  }
}

// ── Enter workspace (shared between Google and license) ───────────────────────
async function enterWorkspace(statusLabel) {
  $("loginView").classList.add("hidden");
  $("appView").classList.remove("hidden");
  $("licenseStatus").textContent = statusLabel;
  hideOverlay();
  renderUserBadge();
  await refreshWorkspace();
  showView("dashboardView");
}

// ── Workspace ─────────────────────────────────────────────────────────────────
async function refreshWorkspace() {
  await Promise.all([loadProjects(), loadAiStatus()]);
  renderAll();
}

async function loadProjects() {
  const payload = await api("/api/projects");
  state.projects = payload.projects || [];
  if (!state.activeProjectId && state.projects.length) {
    state.activeProjectId = state.projects[0].id;
  }
}

async function loadAiStatus() {
  try {
    const status = await api("/api/ai/status");
    const label = status.configured ? "Claude ready" : "Fallback mode";
    $("aiStatusMetric").textContent = label;
    $("aiModuleStatus").textContent = label;
    if ($("aiTemplateStatus")) $("aiTemplateStatus").textContent = label;
  } catch (_) {
    $("aiStatusMetric").textContent = "Offline";
    $("aiModuleStatus").textContent = "Offline";
  }
}

// ── Projects ──────────────────────────────────────────────────────────────────
async function createProject() {
  try {
    requireUnlocked();
    const companyName = $("companyName").value.trim();
    if (!companyName) throw new Error("Company name is required.");
    const payload = await api("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        company_name: companyName,
        project_type: $("projectType").value,
        currency: $("currency").value,
        fiscal_year_end: "December",
      }),
    });
    state.activeProjectId = payload.project.id;
    $("createMessage").textContent = "Dossier created.";
    $("companyName").value = "";
    await refreshWorkspace();
    showView("projectView");
  } catch (error) {
    $("createMessage").textContent = error.message;
  }
}

// ── Upload / extraction ───────────────────────────────────────────────────────
async function uploadFile() {
  try {
    requireUnlocked();
    const project = activeProject();
    if (!project) throw new Error("Select a project first.");
    const file = $("fileInput").files[0];
    if (!file) throw new Error("Choose a file first.");
    const body = new FormData();
    body.append("file", file);
    setResult("uploadResult", "Uploading and normalizing…");
    const payload = await api(`/api/projects/${project.id}/upload`, {
      method: "POST",
      body,
    });
    setResult("uploadResult", {
      uploaded: payload.file?.filename,
      bytes: payload.file?.bytes,
      periods: payload.normalized?.periods,
      extraction: payload.normalized?.extraction,
      source_files: payload.normalized?.source_files,
    });
    updateExtractionStatus(payload.normalized?.extraction);
    await refreshWorkspace();
  } catch (error) {
    setResult("uploadResult", error.message);
  }
}

async function extractHistoricals() {
  try {
    requireUnlocked();
    const project = activeProject();
    if (!project) throw new Error("Select a project first.");
    setResult("uploadResult", "Running Claude historical extraction…");
    const payload = await api(`/api/ai/projects/${project.id}/extract-historicals`, {
      method: "POST",
    });
    updateExtractionStatus(payload.extraction);
    setResult("uploadResult", {
      periods: payload.normalized?.periods,
      currency: payload.normalized?.currency,
      unit: payload.normalized?.unit,
      extraction: payload.extraction,
      income_statement: payload.normalized?.income_statement,
      balance_sheet: payload.normalized?.balance_sheet,
      debt: payload.normalized?.debt,
    });
  } catch (error) {
    setResult("uploadResult", error.message);
  }
}

// ── Outputs ───────────────────────────────────────────────────────────────────
async function generateBp() {
  try {
    requireUnlocked();
    const project = activeProject();
    if (!project) throw new Error("Select a project first.");
    setResult("outputResult", "Generating institutional Excel BP… (this takes ~10 seconds)");
    const payload = await api(`/api/projects/${project.id}/bp/generate`, { method: "POST" });
    state.lastOutput = payload.output;
    $("modelStatusMetric").textContent = "Generated";
    setResult("outputResult", payload.output);
  } catch (error) {
    setResult("outputResult", error.message);
  }
}

function downloadBp() {
  try {
    requireUnlocked();
    const project = activeProject();
    if (!project) throw new Error("Select a project first.");
    window.location.href = `/api/projects/${project.id}/bp/download`;
  } catch (error) {
    setResult("outputResult", error.message);
  }
}

async function generateAiBrief() {
  try {
    requireUnlocked();
    const project = activeProject();
    if (!project) throw new Error("Select a project first.");
    setResult("outputResult", "Generating AI project brief…");
    const payload = await api(`/api/ai/projects/${project.id}/brief`, { method: "POST" });
    setResult("outputResult", payload);
  } catch (error) {
    setResult("outputResult", error.message);
  }
}

async function generateQoePack() {
  try {
    requireUnlocked();
    const project = activeProject();
    if (!project) throw new Error("Select a project first.");
    setResult("outputResult", "Building QoE pack…");
    const payload = await api(`/api/qoe/projects/${project.id}/pack`, { method: "POST" });
    setResult("outputResult", payload);
  } catch (error) {
    setResult("outputResult", error.message);
  }
}

async function generateRestructuringPaper() {
  try {
    requireUnlocked();
    const project = activeProject();
    if (!project) throw new Error("Select a project first.");
    setResult("outputResult", "Building restructuring options paper…");
    const payload = await api(`/api/restructuring/projects/${project.id}/paper`, { method: "POST" });
    setResult("outputResult", payload);
  } catch (error) {
    setResult("outputResult", error.message);
  }
}

async function generateLenderDeck() {
  try {
    requireUnlocked();
    const project = activeProject();
    if (!project) throw new Error("Select a project first.");
    setResult("outputResult", "Generating institutional lender presentation…");
    const payload = await api(`/api/projects/${project.id}/decks/lender/generate`, { method: "POST" });
    setResult("outputResult", {
      ...payload.output,
      download_url: `/api/projects/${project.id}/decks/lender/download`,
    });
    window.location.href = `/api/projects/${project.id}/decks/lender/download`;
  } catch (error) {
    setResult("outputResult", error.message);
  }
}

async function planLenderDeck() {
  try {
    requireUnlocked();
    const project = activeProject();
    if (!project) throw new Error("Select a project first.");
    setResult("outputResult", "Claude is selecting the best slide templates…");
    const payload = await api(`/api/projects/${project.id}/decks/lender/plan`, { method: "POST" });
    const blueprint = payload.blueprint || {};
    setResult("outputResult", {
      source: payload.source,
      claude_configured: payload.configured,
      narrative_thesis: blueprint.narrative_thesis,
      selected_slides: (blueprint.slides || []).map((s) => ({
        slide: s.slide_number,
        title: s.slide_title,
        template: s.recommended_template_file,
        template_slide: s.recommended_template_slide,
        proof_object: s.proof_object,
      })),
    });
  } catch (error) {
    setResult("outputResult", error.message);
  }
}

// ── Render ────────────────────────────────────────────────────────────────────
function renderAll() {
  renderMetrics();
  renderProjectTables();
  renderActiveProject();
  renderUserBadge();
}

function renderUserBadge() {
  const badge = $("userBadge");
  badge.classList.toggle("hidden", !state.user);
  if (!state.user) return;
  $("userName").textContent = state.user.name || "Workspace user";
  $("userEmail").textContent = state.user.email || "Signed in";
  if (state.user.picture) {
    $("userAvatar").innerHTML = `<img src="${escapeHtml(state.user.picture)}" alt="" referrerpolicy="no-referrer">`;
  } else {
    $("userAvatar").textContent = initials(state.user.name || state.user.email || "MG");
  }
}

function renderMetrics() {
  $("projectCount").textContent = state.projects.length;
  const project = activeProject();
  $("activeProjectMetric").textContent = project ? project.company_name : "None";
}

function renderProjectTables() {
  renderProjectList("projectList", true);
  renderProjectList("recentProjects", false, 5);
}

function renderProjectList(targetId, allowSearch, limit) {
  const target = $(targetId);
  if (!target) return;
  const search =
    allowSearch && $("projectSearch") ? $("projectSearch").value.toLowerCase().trim() : "";
  const rows = state.projects
    .filter((p) => {
      if (!search) return true;
      return `${p.company_name} ${p.project_type} ${p.currency}`.toLowerCase().includes(search);
    })
    .slice(0, limit || state.projects.length);

  if (!rows.length) {
    target.innerHTML = '<div class="empty-state"><h3>No projects yet</h3></div>';
    return;
  }

  target.innerHTML = rows
    .map((p) => {
      const active = p.id === state.activeProjectId ? " active" : "";
      return `
        <div class="project-row${active}" data-project-id="${p.id}">
          <div>
            <strong>${escapeHtml(p.company_name)}</strong>
            <span>${escapeHtml(p.project_type)} | ${escapeHtml(p.currency)} | ${escapeHtml(p.id)}</span>
            <small>Updated ${formatDate(p.updated_at)}</small>
          </div>
          <div class="status-pill">${escapeHtml(p.status || "active")}</div>
        </div>`;
    })
    .join("");

  target.querySelectorAll("[data-project-id]").forEach((row) => {
    row.addEventListener("click", () => {
      state.activeProjectId = row.dataset.projectId;
      renderAll();
      showView("projectView");
    });
  });
}

function renderActiveProject() {
  const project = activeProject();
  $("emptyProjectState").classList.toggle("hidden", Boolean(project));
  $("projectWorkspace").classList.toggle("hidden", !project);
  if (!project) return;
  $("activeProjectName").textContent = project.company_name;
  $("activeProjectMeta").textContent = `${project.project_type} | ${project.currency} | ${project.id}`;
  updateExtractionStatus(null);
}

function updateExtractionStatus(extraction) {
  const el = $("extractionStatus");
  if (!el) return;
  if (!extraction) { el.textContent = "Ready"; return; }
  const confidence = extraction.confidence ? ` / ${extraction.confidence}` : "";
  el.textContent = `${extraction.mode || "local"}${confidence}`;
}

function showView(viewId) {
  state.activeView = viewId;
  document.querySelectorAll(".view").forEach((v) => {
    v.classList.toggle("active-view", v.id === viewId);
  });
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.view === viewId);
  });
  const titles = {
    dashboardView: "Dashboard",
    libraryView: "Project Library",
    projectView: "Active Project",
    outputsView: "Outputs",
  };
  $("pageTitle").textContent = titles[viewId] || "Workspace";
}

function setResult(id, payload) {
  const target = $(id);
  if (!target) return;
  target.textContent =
    typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
}

// ── Error messages ────────────────────────────────────────────────────────────
function googleErrorMessage(reason) {
  const messages = {
    direct_callback:
      "Open the homepage and click 'Continue with Google'. Do not open the callback URL directly.",
    invalid_state:
      "Google login expired. Please click 'Continue with Google' again.",
    token_exchange_failed:
      "Could not complete Google sign-in. Verify GOOGLE_CLIENT_SECRET and the redirect URI match in Railway and Google Cloud Console.",
    userinfo_failed:
      "Google profile could not be loaded. Try again or check Google OAuth scopes.",
    missing_email:
      "Google did not return an email address. Check OAuth scopes include 'email'.",
    email_domain_not_allowed:
      "This Google email domain is not authorised for this workspace. Contact your administrator.",
  };
  return messages[reason] || `Google login error: ${reason || "unknown"}`;
}

// ── Utilities ─────────────────────────────────────────────────────────────────
function formatDate(value) {
  if (!value) return "n/a";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString();
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function initials(value) {
  return String(value || "MG")
    .split(/[ .@_-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0].toUpperCase())
    .join("");
}

// ── Event listeners ───────────────────────────────────────────────────────────
$("loginForm").addEventListener("submit", login);
$("googleLoginButton").addEventListener("click", startGoogleLogin);
$("logoutButton").addEventListener("click", logout);
$("refreshButton").addEventListener("click", refreshWorkspace);
$("newProjectTopButton").addEventListener("click", () => showView("libraryView"));
$("createProjectButton").addEventListener("click", createProject);
$("uploadButton").addEventListener("click", uploadFile);
$("extractHistoricalsButton").addEventListener("click", extractHistoricals);
$("generateBpButton").addEventListener("click", generateBp);
$("generateBpOutputButton").addEventListener("click", generateBp);
$("downloadBpButton").addEventListener("click", downloadBp);
$("aiBriefButton").addEventListener("click", generateAiBrief);
$("qoePackButton").addEventListener("click", generateQoePack);
$("restructuringButton").addEventListener("click", generateRestructuringPaper);
$("planLenderDeckButton").addEventListener("click", planLenderDeck);
$("generateLenderDeckButton").addEventListener("click", generateLenderDeck);
$("projectSearch").addEventListener("input", () => renderProjectList("projectList", true));

document.querySelectorAll("[data-view], [data-view-button]").forEach((el) => {
  el.addEventListener("click", () => showView(el.dataset.view || el.dataset.viewButton));
});

// ── Boot ──────────────────────────────────────────────────────────────────────
const redirectHandled = handleAuthRedirect();
if (!redirectHandled) bootAuthState();
