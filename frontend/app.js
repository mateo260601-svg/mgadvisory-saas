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
  bpStep: 0,
  claudeHistory: [],
};

const $ = (id) => document.getElementById(id);
const ACTIVE_PROJECT_STORAGE_KEY = "mg_advisory_active_project_id";
const MAX_REVENUE_STREAMS = 10;
const MAX_COST_ITEMS = 12;
const MAX_HEADCOUNT_LINES = 10;
const MAX_DEBT_TRANCHES = 10;
const MAX_HISTORICAL_LINES = 24;

// ── API helper ────────────────────────────────────────────────────────────────
async function api(path, options = {}) {
  const response = await fetch(path, options);
  const text = await response.text();
  let payload = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch (_) {
    payload = { detail: text || "Empty server response" };
  }
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
  localStorage.removeItem(ACTIVE_PROJECT_STORAGE_KEY);
  state.projects = [];
  state.user = null;
  renderUserBadge();
  $("appView").classList.add("hidden");
  $("loginView").classList.remove("hidden");
  if ($("claudeAssistant")) $("claudeAssistant").classList.add("hidden");
  if ($("claudeNavButton")) $("claudeNavButton").classList.add("hidden");
  if ($("claudePanel")) $("claudePanel").classList.add("hidden");
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
  if ($("claudeAssistant")) $("claudeAssistant").classList.remove("hidden");
  if ($("claudeNavButton")) $("claudeNavButton").classList.remove("hidden");
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
  const storedProjectId = localStorage.getItem(ACTIVE_PROJECT_STORAGE_KEY);
  const activeStillExists = state.projects.some((p) => p.id === state.activeProjectId);
  const storedStillExists = state.projects.some((p) => p.id === storedProjectId);
  if (!activeStillExists) {
    state.activeProjectId = storedStillExists ? storedProjectId : state.projects[0]?.id || null;
  }
  if (state.activeProjectId) {
    localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, state.activeProjectId);
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
    localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, state.activeProjectId);
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
    setResult("bpBuilderResult", "Running Claude historical extraction...");
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
    setResult("bpBuilderResult", {
      status: "Historical data normalized for Excel Historical Inputs",
      periods: payload.normalized?.periods,
      extraction: payload.extraction,
    });
  } catch (error) {
    setResult("uploadResult", error.message);
    setResult("bpBuilderResult", error.message);
  }
}

// ── Claude mini assistant ────────────────────────────────────────────────────
function toggleClaudePanel(forceOpen) {
  const panel = $("claudePanel");
  if (!panel) return;
  const shouldOpen = forceOpen ?? panel.classList.contains("hidden");
  panel.classList.toggle("hidden", !shouldOpen);
  if ($("claudeNavButton")) $("claudeNavButton").classList.toggle("active", shouldOpen);
}

function addClaudeMessage(role, text) {
  const target = $("claudeMessages");
  if (!target) return null;
  const div = document.createElement("div");
  div.className = `claude-message ${role}`;
  div.textContent = text;
  target.appendChild(div);
  target.scrollTop = target.scrollHeight;
  return div;
}

async function activeProjectForClaude() {
  let project = activeProject();
  if (!project) {
    await loadProjects();
    renderAll();
    project = activeProject();
  }
  if (!project) {
    throw new Error("Create or select a project before chatting with Claude.");
  }
  return project;
}

async function sendClaudeMessage() {
  let pending = null;
  try {
    requireUnlocked();
    const project = await activeProjectForClaude();
    const message = $("claudeInput").value.trim();
    if (!message) throw new Error("Write a message for Claude.");
    $("claudeInput").value = "";
    addClaudeMessage("user", message);
    pending = addClaudeMessage("assistant", "Claude is thinking...");
    $("claudeResult").textContent = "Claude is thinking...";
    $("claudeSendButton").disabled = true;
    const payload = await api(`/api/ai/projects/${project.id}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history: state.claudeHistory }),
    });
    const reply = payload.reply || "No response.";
    state.claudeHistory.push({ role: "user", content: message }, { role: "assistant", content: reply });
    state.claudeHistory = state.claudeHistory.slice(-16);
    if (pending) pending.textContent = reply;
    $("claudeResult").textContent = payload.source === "claude" ? "Claude response ready." : "Fallback response ready.";
  } catch (error) {
    const errorMessage = `Claude could not answer yet: ${error.message}`;
    if (pending) pending.textContent = errorMessage;
    else addClaudeMessage("assistant", errorMessage);
    $("claudeResult").textContent = error.message;
  } finally {
    $("claudeSendButton").disabled = false;
  }
}

async function uploadFileFromClaude() {
  try {
    requireUnlocked();
    const project = await activeProjectForClaude();
    const file = $("claudeFileInput").files[0];
    if (!file) throw new Error("Choose a PDF, Excel or CSV file first.");
    const body = new FormData();
    body.append("file", file);
    $("claudeResult").textContent = "Uploading and normalizing file...";
    addClaudeMessage("user", `[Uploaded file] ${file.name}`);
    const payload = await api(`/api/projects/${project.id}/upload`, {
      method: "POST",
      body,
    });
    $("claudeFileInput").value = "";
    updateExtractionStatus(payload.normalized?.extraction);
    addClaudeMessage(
      "assistant",
      `File uploaded and normalized: ${payload.file?.filename || file.name}.\nPeriods detected: ${(payload.normalized?.periods || []).join(", ") || "to review"}.\nYou can now ask Claude to extract the 3 financial statements or click Apply to BP data.`
    );
    $("claudeResult").textContent = "File attached to project.";
    await refreshWorkspace();
  } catch (error) {
    addClaudeMessage("assistant", `Upload failed: ${error.message}`);
    $("claudeResult").textContent = error.message;
  }
}

async function applyClaudeToBp() {
  let pending = null;
  try {
    requireUnlocked();
    const project = await activeProjectForClaude();
    const message = $("claudeInput").value.trim() || "Extract all useful financial statements, debt and BP assumptions from this conversation and apply them to the BP model.";
    addClaudeMessage("user", `[Apply to BP] ${message}`);
    pending = addClaudeMessage("assistant", "Claude is extracting and applying the data to the BP...");
    $("claudeResult").textContent = "Extracting and applying to BP data...";
    $("claudeApplyButton").disabled = true;
    const payload = await api(`/api/ai/projects/${project.id}/chat/apply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history: state.claudeHistory }),
    });
    populateBpBuilder(payload.assumptions || {});
    updateExtractionStatus(payload.extraction);
    const appliedMessage = "Applied to BP data. Historical actuals and normalized financials were updated; generate a new Excel BP to push this into the workbook.";
    if (pending) pending.textContent = appliedMessage;
    setResult("bpBuilderResult", {
      status: "Claude chat applied to BP",
      periods: payload.normalized?.periods,
      extraction: payload.extraction,
    });
    $("claudeResult").textContent = "Applied to BP data.";
    await refreshWorkspace();
  } catch (error) {
    const errorMessage = `Claude could not apply the data: ${error.message}`;
    if (pending) pending.textContent = errorMessage;
    else addClaudeMessage("assistant", errorMessage);
    $("claudeResult").textContent = error.message;
  } finally {
    $("claudeApplyButton").disabled = false;
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

// ── BP Builder ────────────────────────────────────────────────────────────────
async function loadBpAssumptions() {
  try {
    requireUnlocked();
    const project = activeProject();
    if (!project) throw new Error("Select a project first.");
    setResult("bpBuilderResult", "Loading BP assumptions...");
    const payload = await api(`/api/projects/${project.id}/bp/assumptions`);
    populateBpBuilder(payload.assumptions || {});
    setResult("bpBuilderResult", "BP assumptions loaded.");
  } catch (error) {
    setResult("bpBuilderResult", error.message);
  }
}

async function saveBpAssumptions() {
  try {
    requireUnlocked();
    const project = activeProject();
    if (!project) throw new Error("Select a project first.");
    const assumptions = collectBpBuilder();
    setResult("bpBuilderResult", "Saving BP assumptions...");
    const payload = await api(`/api/projects/${project.id}/bp/assumptions`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ assumptions }),
    });
    populateBpBuilder(payload.assumptions || {});
    setResult("bpBuilderResult", "BP assumptions saved.");
    return payload.assumptions;
  } catch (error) {
    setResult("bpBuilderResult", error.message);
    throw error;
  }
}

async function generateBpFromBuilder() {
  try {
    await saveBpAssumptions();
    setResult("bpBuilderResult", "Generating Excel BP with saved assumptions...");
    const project = activeProject();
    const payload = await api(`/api/projects/${project.id}/bp/generate`, { method: "POST" });
    state.lastOutput = payload.output;
    $("modelStatusMetric").textContent = "Generated";
    setResult("bpBuilderResult", payload.output);
  } catch (_) {
    // saveBpAssumptions already writes the message
  }
}

function populateBpBuilder(assumptions) {
  const model = assumptions.model || {};
  setValue("bpCurrency", model.currency || activeProject()?.currency || "EUR");
  setValue("bpScenario", model.scenario || "Base");
  setValue("bpModelStart", model.model_start_date || "2026-01-31");
  setValue("bpActualsEnd", model.actuals_end_date || "2025-12-31");
  setValue("bpHistoricalSource", model.historical_source || "Claude extraction");
  setValue("bpForecastMonths", model.forecast_months || 60);
  setValue("bpTaxRate", model.tax_rate ?? 0.25);
  setValue("bpOpeningCash", model.opening_cash ?? 120000);
  setValue("bpOpeningDebt", model.opening_debt ?? 500000);
  setValue("bpMinimumCash", model.minimum_cash ?? 50000);
  renderHistoricalRows(assumptions.historical_actuals || []);

  renderRevenueStreamRows(assumptions.revenue_streams || []);
  const cost = assumptions.cost_base || {};
  setValue("bpCogsPercent", cost.cogs_percent ?? 0.35);
  setValue("bpFulfilmentCost", cost.fulfilment_cost_per_unit ?? 100);
  setValue("bpFixedOpex", cost.opex_fixed_monthly ?? 80000);
  setValue("bpOpexPercent", cost.opex_percent_revenue ?? 0.04);
  setValue("bpRent", cost.rent_monthly ?? 12000);
  setValue("bpProfessionalFees", cost.professional_fees_monthly ?? 8000);
  setValue("bpIt", cost.it_monthly ?? 5000);
  renderCostItemRows(assumptions.cost_items || []);

  renderHeadcountRows(assumptions.headcount || []);
  const wc = assumptions.working_capital || {};
  setValue("bpDso", wc.dso ?? 60);
  setValue("bpDio", wc.dio ?? 45);
  setValue("bpDpo", wc.dpo ?? 55);

  const capex = assumptions.capex || {};
  setValue("bpMaintenanceCapex", capex.maintenance_percent_revenue ?? 0.015);
  setValue("bpGrowthCapex", capex.growth_capex_monthly ?? 15000);
  setValue("bpDepreciationYears", capex.depreciation_years ?? 7);

  renderDebtTrancheRows(assumptions.debt_tranches || []);

  const covenants = assumptions.covenants || {};
  setValue("bpMaxLeverage", covenants.max_net_debt_ebitda ?? 3.5);
  setValue("bpMinIcr", covenants.min_interest_cover ?? 2.0);
  setValue("bpMinLiquidity", covenants.min_liquidity ?? 50000);
}

function collectBpBuilder() {
  return {
    model: {
      currency: getValue("bpCurrency", "EUR"),
      scenario: getValue("bpScenario", "Base"),
      model_start_date: getValue("bpModelStart", "2026-01-31"),
      actuals_end_date: getValue("bpActualsEnd", "2025-12-31"),
      historical_source: getValue("bpHistoricalSource", "Claude extraction"),
      forecast_months: getNumber("bpForecastMonths", 60),
      tax_rate: getNumber("bpTaxRate", 0.25),
      opening_cash: getNumber("bpOpeningCash", 120000),
      opening_debt: getNumber("bpOpeningDebt", 500000),
      minimum_cash: getNumber("bpMinimumCash", 50000),
    },
    historical_actuals: readHistoricalRows(),
    revenue_streams: readRevenueStreamRows(),
    cost_base: {
      cogs_percent: getNumber("bpCogsPercent", 0.35),
      fulfilment_cost_per_unit: getNumber("bpFulfilmentCost", 100),
      opex_fixed_monthly: getNumber("bpFixedOpex", 80000),
      opex_percent_revenue: getNumber("bpOpexPercent", 0.04),
      rent_monthly: getNumber("bpRent", 12000),
      professional_fees_monthly: getNumber("bpProfessionalFees", 8000),
      it_monthly: getNumber("bpIt", 5000),
    },
    cost_items: readCostItemRows(),
    headcount: readHeadcountRows(),
    working_capital: {
      dso: getNumber("bpDso", 60),
      dio: getNumber("bpDio", 45),
      dpo: getNumber("bpDpo", 55),
    },
    capex: {
      maintenance_percent_revenue: getNumber("bpMaintenanceCapex", 0.015),
      growth_capex_monthly: getNumber("bpGrowthCapex", 15000),
      depreciation_years: getNumber("bpDepreciationYears", 7),
    },
    debt_tranches: readDebtTrancheRows(),
    covenants: {
      max_net_debt_ebitda: getNumber("bpMaxLeverage", 3.5),
      min_interest_cover: getNumber("bpMinIcr", 2.0),
      min_liquidity: getNumber("bpMinLiquidity", 50000),
    },
  };
}

function renderHistoricalRows(rows) {
  const table = $("historicalActualsTable");
  if (!table) return;
  const defaults = rows.length ? rows : [
    { model_line: "Revenue", detail_line: "Product revenue", fy2022: 0, fy2023: 0, fy2024: 0, fy2025: 0, latest_actual: 0 },
    { model_line: "Revenue", detail_line: "Service revenue", fy2022: 0, fy2023: 0, fy2024: 0, fy2025: 0, latest_actual: 0 },
    { model_line: "COGS", detail_line: "Materials", fy2022: 0, fy2023: 0, fy2024: 0, fy2025: 0, latest_actual: 0 },
    { model_line: "Payroll", detail_line: "Management payroll", fy2022: 0, fy2023: 0, fy2024: 0, fy2025: 0, latest_actual: 0 },
    { model_line: "Opex", detail_line: "Rent", fy2022: 0, fy2023: 0, fy2024: 0, fy2025: 0, latest_actual: 0 },
    { model_line: "Cash", detail_line: "Cash at bank", fy2022: 0, fy2023: 0, fy2024: 0, fy2025: 0, latest_actual: 0 },
    { model_line: "Closing Debt", detail_line: "Senior term loan A", fy2022: 0, fy2023: 0, fy2024: 0, fy2025: 0, latest_actual: 0 },
  ];
  table.querySelectorAll(".builder-row:not(.builder-head)").forEach((row) => row.remove());
  defaults.slice(0, MAX_HISTORICAL_LINES).forEach((row, idx) => {
    table.insertAdjacentHTML("beforeend", `
      <div class="builder-row historical-row" data-index="${idx}">
        <select data-field="model_line">${historicalModelLineOptions().map((value) => `<option>${escapeHtml(value)}</option>`).join("")}</select>
        <input data-field="detail_line" value="${escapeHtml(row.detail_line || "")}" />
        <input data-field="fy2022" type="number" value="${row.fy2022 ?? 0}" />
        <input data-field="fy2023" type="number" value="${row.fy2023 ?? 0}" />
        <input data-field="fy2024" type="number" value="${row.fy2024 ?? 0}" />
        <input data-field="fy2025" type="number" value="${row.fy2025 ?? 0}" />
        <input data-field="latest_actual" type="number" value="${row.latest_actual ?? 0}" />
        <button class="remove-row-button" type="button">Remove</button>
      </div>`);
    const rowEl = table.lastElementChild;
    rowEl.querySelector('[data-field="model_line"]').value = row.model_line || "Revenue";
    rowEl.querySelector(".remove-row-button").addEventListener("click", () => rowEl.remove());
  });
}

function renderRevenueStreamRows(rows) {
  const table = $("revenueStreamTable");
  if (!table) return;
  const defaults = rows.length ? rows : [
    { name: "Core product", type: "Product", volume: 100, price: 1000, volume_growth: 0.01, price_growth: 0.002 },
    { name: "Services", type: "Service", volume: 80, price: 850, volume_growth: 0.008, price_growth: 0.002 },
    { name: "Recurring revenue", type: "Recurring", volume: 60, price: 700, volume_growth: 0.012, price_growth: 0.001 },
    { name: "Projects", type: "Project", volume: 40, price: 600, volume_growth: 0.006, price_growth: 0.001 },
    { name: "Other", type: "Other", volume: 25, price: 500, volume_growth: 0.004, price_growth: 0.001 },
  ];
  table.querySelectorAll(".builder-row:not(.builder-head)").forEach((row) => row.remove());
  defaults.slice(0, MAX_REVENUE_STREAMS).forEach((row, idx) => {
    table.insertAdjacentHTML("beforeend", `
      <div class="builder-row revenue-row" data-index="${idx}">
        <input data-field="name" value="${escapeHtml(row.name || "")}" />
        <select data-field="type"><option>Product</option><option>Service</option><option>Recurring</option><option>Project</option><option>Consulting</option><option>License</option><option>Maintenance</option><option>Other</option></select>
        <input data-field="volume" type="number" value="${row.volume ?? 0}" />
        <input data-field="price" type="number" value="${row.price ?? 0}" />
        <input data-field="volume_growth" type="number" step="0.001" value="${row.volume_growth ?? 0}" />
        <input data-field="price_growth" type="number" step="0.001" value="${row.price_growth ?? 0}" />
        <button class="remove-row-button" type="button">Remove</button>
      </div>`);
    const rowEl = table.lastElementChild;
    rowEl.querySelector('[data-field="type"]').value = row.type || "Other";
    rowEl.querySelector(".remove-row-button").addEventListener("click", () => rowEl.remove());
  });
}

function renderHeadcountRows(rows) {
  const table = $("headcountTable");
  if (!table) return;
  const defaults = rows.length ? rows : [
    { department: "Management", opening_fte: 2, avg_salary_month: 10000, hiring_every_months: 12, new_hires: 1 },
    { department: "Sales", opening_fte: 4, avg_salary_month: 5000, hiring_every_months: 6, new_hires: 1 },
    { department: "Operations", opening_fte: 8, avg_salary_month: 4200, hiring_every_months: 6, new_hires: 2 },
    { department: "Finance", opening_fte: 2, avg_salary_month: 4800, hiring_every_months: 12, new_hires: 1 },
    { department: "IT", opening_fte: 2, avg_salary_month: 5200, hiring_every_months: 12, new_hires: 1 },
    { department: "Admin", opening_fte: 3, avg_salary_month: 3500, hiring_every_months: 12, new_hires: 1 },
  ];
  table.querySelectorAll(".builder-row:not(.builder-head)").forEach((row) => row.remove());
  defaults.slice(0, MAX_HEADCOUNT_LINES).forEach((row, idx) => {
    table.insertAdjacentHTML("beforeend", `
      <div class="builder-row headcount-row" data-index="${idx}">
        <input data-field="department" value="${escapeHtml(row.department || "")}" />
        <input data-field="opening_fte" type="number" value="${row.opening_fte ?? 0}" />
        <input data-field="avg_salary_month" type="number" value="${row.avg_salary_month ?? 0}" />
        <input data-field="hiring_every_months" type="number" value="${row.hiring_every_months ?? 6}" />
        <input data-field="new_hires" type="number" value="${row.new_hires ?? 0}" />
        <button class="remove-row-button" type="button">Remove</button>
      </div>`);
    const rowEl = table.lastElementChild;
    rowEl.querySelector(".remove-row-button").addEventListener("click", () => rowEl.remove());
  });
}

function renderCostItemRows(rows) {
  const table = $("costItemTable");
  if (!table) return;
  const defaults = rows.length ? rows : [
    { name: "Rent", driver: "Fixed", monthly_fixed: 12000, percent_revenue: 0, cost_per_fte: 0 },
    { name: "Marketing", driver: "% Revenue", monthly_fixed: 0, percent_revenue: 0.03, cost_per_fte: 0 },
    { name: "IT & software", driver: "Per FTE", monthly_fixed: 5000, percent_revenue: 0, cost_per_fte: 120 },
    { name: "Professional fees", driver: "Fixed", monthly_fixed: 8000, percent_revenue: 0, cost_per_fte: 0 },
    { name: "Travel & commercial", driver: "% Revenue", monthly_fixed: 0, percent_revenue: 0.01, cost_per_fte: 0 },
    { name: "Other SG&A", driver: "Fixed", monthly_fixed: 10000, percent_revenue: 0, cost_per_fte: 0 },
  ];
  table.querySelectorAll(".builder-row:not(.builder-head)").forEach((row) => row.remove());
  defaults.slice(0, MAX_COST_ITEMS).forEach((row, idx) => {
    table.insertAdjacentHTML("beforeend", `
      <div class="builder-row cost-row" data-index="${idx}">
        <input data-field="name" value="${escapeHtml(row.name || "")}" />
        <select data-field="driver"><option>Fixed</option><option>% Revenue</option><option>Per FTE</option></select>
        <input data-field="monthly_fixed" type="number" value="${row.monthly_fixed ?? 0}" />
        <input data-field="percent_revenue" type="number" step="0.001" value="${row.percent_revenue ?? 0}" />
        <input data-field="cost_per_fte" type="number" value="${row.cost_per_fte ?? 0}" />
        <button class="remove-row-button" type="button">Remove</button>
      </div>`);
    const rowEl = table.lastElementChild;
    rowEl.querySelector('[data-field="driver"]').value = row.driver || "Fixed";
    rowEl.querySelector(".remove-row-button").addEventListener("click", () => rowEl.remove());
  });
}

function renderDebtTrancheRows(rows) {
  const table = $("debtTrancheTable");
  if (!table) return;
  const defaults = rows.length ? rows : [
    { name: "Senior Term Loan A", debt_type: "Senior Term Loan A", borrower: "OpCo", start_date: "2026-01-31", opening_balance: 500000, commitment: 500000, term_months: 60, moratorium_months: 6, margin: 0.045, base_rate: 0.035, amortization: "Linear", interest_type: "Cash", cash_pay_frequency: "Monthly", cash_pay_percent: 1.0 },
    { name: "Super Senior RCF", debt_type: "Super Senior RCF", borrower: "OpCo", start_date: "2026-01-31", opening_balance: 0, commitment: 100000, term_months: 60, moratorium_months: 0, margin: 0.025, base_rate: 0.035, amortization: "Revolver", interest_type: "Cash", cash_pay_frequency: "Quarterly", cash_pay_percent: 1.0 },
    { name: "Mezzanine PIK", debt_type: "Mezzanine PIK", borrower: "HoldCo", start_date: "2026-01-31", opening_balance: 200000, commitment: 200000, term_months: 84, moratorium_months: 24, margin: 0.06, base_rate: 0.06, amortization: "PIK", interest_type: "PIK", cash_pay_frequency: "Annual", cash_pay_percent: 0 },
  ];
  table.querySelectorAll(".builder-row:not(.builder-head)").forEach((row) => row.remove());
  defaults.slice(0, MAX_DEBT_TRANCHES).forEach((row, idx) => {
    table.insertAdjacentHTML("beforeend", `
      <div class="builder-row debt-row" data-index="${idx}">
        <input data-field="name" value="${escapeHtml(row.name || "")}" />
        <select data-field="debt_type">${debtTypeOptions().map((value) => `<option>${escapeHtml(value)}</option>`).join("")}</select>
        <input data-field="borrower" value="${escapeHtml(row.borrower || "")}" />
        <input data-field="start_date" type="date" value="${row.start_date || "2026-01-31"}" />
        <input data-field="opening_balance" type="number" value="${row.opening_balance ?? 0}" />
        <input data-field="commitment" type="number" value="${row.commitment ?? 0}" />
        <input data-field="term_months" type="number" value="${row.term_months ?? 60}" />
        <input data-field="moratorium_months" type="number" value="${row.moratorium_months ?? 0}" />
        <input data-field="margin" type="number" step="0.001" value="${row.margin ?? 0.03}" />
        <input data-field="base_rate" type="number" step="0.001" value="${row.base_rate ?? 0.03}" />
        <select data-field="amortization"><option>Linear</option><option>Bullet</option><option>Annuity</option><option>Cash Sweep</option><option>Revolver</option><option>PIK</option><option>PIK Toggle</option><option>Interest Only Then Linear</option></select>
        <select data-field="interest_type"><option>Cash</option><option>PIK</option><option>Cash / PIK Toggle</option></select>
        <select data-field="cash_pay_frequency"><option>Monthly</option><option>Quarterly</option><option>Annual</option></select>
        <input data-field="cash_pay_percent" type="number" step="0.001" value="${row.cash_pay_percent ?? (row.pik ? 0 : 1)}" />
        <button class="remove-row-button" type="button">Remove</button>
      </div>`);
    const tr = table.lastElementChild;
    tr.querySelector('[data-field="debt_type"]').value = row.debt_type || "Senior Term Loan A";
    tr.querySelector('[data-field="amortization"]').value = row.amortization || "Bullet";
    tr.querySelector('[data-field="interest_type"]').value = row.interest_type || (row.pik ? "PIK" : "Cash");
    tr.querySelector('[data-field="cash_pay_frequency"]').value = row.cash_pay_frequency || "Monthly";
    tr.querySelector(".remove-row-button").addEventListener("click", () => tr.remove());
  });
}

function addRevenueStreamRow() {
  const rows = readRevenueStreamRows();
  if (rows.length >= MAX_REVENUE_STREAMS) return setResult("bpBuilderResult", `Maximum ${MAX_REVENUE_STREAMS} product/service lines reached.`);
  renderRevenueStreamRows([...rows, { name: `Product / Service ${rows.length + 1}`, type: "Service", volume: 0, price: 0, volume_growth: 0, price_growth: 0 }]);
}

function addCostItemRow() {
  const rows = readCostItemRows();
  if (rows.length >= MAX_COST_ITEMS) return setResult("bpBuilderResult", `Maximum ${MAX_COST_ITEMS} cost lines reached.`);
  renderCostItemRows([...rows, { name: `Cost item ${rows.length + 1}`, driver: "Fixed", monthly_fixed: 0, percent_revenue: 0, cost_per_fte: 0 }]);
}

function addHeadcountLine() {
  const rows = readHeadcountRows();
  if (rows.length >= MAX_HEADCOUNT_LINES) return setResult("bpBuilderResult", `Maximum ${MAX_HEADCOUNT_LINES} headcount lines reached.`);
  renderHeadcountRows([...rows, { department: `Team ${rows.length + 1}`, opening_fte: 0, avg_salary_month: 0, hiring_every_months: 12, new_hires: 0 }]);
}

function addDebtTrancheRow() {
  const rows = readDebtTrancheRows();
  if (rows.length >= MAX_DEBT_TRANCHES) return setResult("bpBuilderResult", `Maximum ${MAX_DEBT_TRANCHES} debt layers reached.`);
  renderDebtTrancheRows([...rows, { name: `Debt layer ${rows.length + 1}`, debt_type: "Senior Term Loan B", borrower: "OpCo", start_date: getValue("bpModelStart", "2026-01-31"), opening_balance: 0, commitment: 0, term_months: 60, moratorium_months: 0, margin: 0.03, base_rate: 0.03, amortization: "Bullet", interest_type: "Cash", cash_pay_frequency: "Monthly", cash_pay_percent: 1 }]);
}

function addHistoricalLineRow() {
  const rows = readHistoricalRows();
  if (rows.length >= MAX_HISTORICAL_LINES) return setResult("bpBuilderResult", `Maximum ${MAX_HISTORICAL_LINES} manual historical lines reached.`);
  renderHistoricalRows([...rows, { model_line: "Opex", detail_line: `Historical line ${rows.length + 1}`, fy2022: 0, fy2023: 0, fy2024: 0, fy2025: 0, latest_actual: 0 }]);
}

function readHistoricalRows() {
  return [...document.querySelectorAll(".historical-row")]
    .map((row) => ({
      model_line: fieldValue(row, "model_line"),
      detail_line: fieldValue(row, "detail_line"),
      fy2022: fieldNumber(row, "fy2022"),
      fy2023: fieldNumber(row, "fy2023"),
      fy2024: fieldNumber(row, "fy2024"),
      fy2025: fieldNumber(row, "fy2025"),
      latest_actual: fieldNumber(row, "latest_actual"),
    }))
    .filter((row) => row.model_line || row.detail_line || row.latest_actual || row.fy2025);
}

function readRevenueStreamRows() {
  return [...document.querySelectorAll(".revenue-row")].map((row) => ({
    name: fieldValue(row, "name"),
    type: fieldValue(row, "type"),
    volume: fieldNumber(row, "volume"),
    price: fieldNumber(row, "price"),
    volume_growth: fieldNumber(row, "volume_growth"),
    price_growth: fieldNumber(row, "price_growth"),
  }));
}

function readCostItemRows() {
  return [...document.querySelectorAll(".cost-row")].map((row) => ({
    name: fieldValue(row, "name"),
    driver: fieldValue(row, "driver"),
    monthly_fixed: fieldNumber(row, "monthly_fixed"),
    percent_revenue: fieldNumber(row, "percent_revenue"),
    cost_per_fte: fieldNumber(row, "cost_per_fte"),
  }));
}

function readHeadcountRows() {
  return [...document.querySelectorAll(".headcount-row")].map((row) => ({
    department: fieldValue(row, "department"),
    opening_fte: fieldNumber(row, "opening_fte"),
    avg_salary_month: fieldNumber(row, "avg_salary_month"),
    hiring_every_months: fieldNumber(row, "hiring_every_months"),
    new_hires: fieldNumber(row, "new_hires"),
  }));
}

function readDebtTrancheRows() {
  return [...document.querySelectorAll(".debt-row")]
    .map((row) => ({
      name: fieldValue(row, "name"),
      debt_type: fieldValue(row, "debt_type"),
      borrower: fieldValue(row, "borrower"),
      start_date: fieldValue(row, "start_date") || "2026-01-31",
      opening_balance: fieldNumber(row, "opening_balance"),
      commitment: fieldNumber(row, "commitment"),
      term_months: fieldNumber(row, "term_months"),
      moratorium_months: fieldNumber(row, "moratorium_months"),
      interest_cap_months: 0,
      margin: fieldNumber(row, "margin"),
      base_rate: fieldNumber(row, "base_rate"),
      amortization: fieldValue(row, "amortization"),
      bullet_percent: fieldValue(row, "amortization") === "Bullet" ? 1 : 0.2,
      cash_sweep_percent: fieldValue(row, "amortization") === "Cash Sweep" ? 0.5 : 0.25,
      interest_type: fieldValue(row, "interest_type"),
      cash_pay_frequency: fieldValue(row, "cash_pay_frequency"),
      cash_pay_percent: fieldNumber(row, "cash_pay_percent"),
      pik: fieldValue(row, "interest_type") !== "Cash",
      minimum_cash: getNumber("bpMinimumCash", 50000),
    }))
    .filter((row) => row.name || row.opening_balance || row.commitment);
}

function debtTypeOptions() {
  return [
    "Super Senior RCF", "RCF", "Senior Term Loan A", "Senior Term Loan B", "Unitranche",
    "Second Lien", "Mezzanine Cash Pay", "Mezzanine PIK", "HoldCo PIK", "High Yield Bond",
    "Senior Secured Notes", "Vendor Loan", "Seller Note", "Bridge Loan", "DIP Financing",
    "Rescue Financing", "Tax Debt Payment Plan", "Supplier Payment Plan", "Project Finance",
    "Equipment Loan", "Finance Lease", "Venture Debt", "Growth Debt", "FX Debt"
  ];
}

function historicalModelLineOptions() {
  return [
    "Revenue", "COGS", "Gross Profit", "Payroll", "Opex", "EBITDA", "D&A", "EBIT",
    "Cash Interest", "Tax", "Net Income", "Cash", "Receivables", "Inventory", "Payables",
    "Net PPE", "Closing Debt", "Net Debt", "Equity", "Change in NWC", "Capex", "Free Cash Flow"
  ];
}

function setValue(id, value) {
  const el = $(id);
  if (el) el.value = value;
}

function getValue(id, fallback = "") {
  const el = $(id);
  return el && el.value !== "" ? el.value : fallback;
}

function getNumber(id, fallback = 0) {
  const value = Number(getValue(id, fallback));
  return Number.isFinite(value) ? value : fallback;
}

function fieldValue(row, field) {
  const el = row.querySelector(`[data-field="${field}"]`);
  return el ? el.value : "";
}

function fieldNumber(row, field) {
  const value = Number(fieldValue(row, field));
  return Number.isFinite(value) ? value : 0;
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

async function generateImDeck() {
  try {
    requireUnlocked();
    const project = activeProject();
    if (!project) throw new Error("Select a project first.");
    setResult("outputResult", "Generating IM / M&A presentation…");
    const payload = await api(`/api/projects/${project.id}/decks/im/generate`, { method: "POST" });
    setResult("outputResult", {
      ...payload.output,
      download_url: `/api/projects/${project.id}/decks/im/download`,
    });
    window.location.href = `/api/projects/${project.id}/decks/im/download`;
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

async function planImDeck() {
  try {
    requireUnlocked();
    const project = activeProject();
    if (!project) throw new Error("Select a project first.");
    setResult("outputResult", "Claude is planning the IM / M&A deck from the reference templates…");
    const payload = await api(`/api/projects/${project.id}/decks/im/plan`, { method: "POST" });
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
      localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, state.activeProjectId);
      renderAll();
      showView("projectView");
    });
  });
}

function renderActiveProject() {
  if (!activeProject() && state.projects.length) {
    state.activeProjectId = state.projects[0].id;
    localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, state.activeProjectId);
  }
  const project = activeProject();
  $("emptyProjectState").classList.toggle("hidden", Boolean(project));
  $("projectWorkspace").classList.toggle("hidden", !project);
  if ($("bpBuilderEmpty")) $("bpBuilderEmpty").classList.toggle("hidden", Boolean(project));
  if ($("bpBuilderWorkspace")) $("bpBuilderWorkspace").classList.toggle("hidden", !project);
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
  const mode = extraction.mode || "local";
  if (mode.includes("fallback")) {
    el.textContent = `Fallback only${confidence}`;
  } else if (mode === "claude") {
    el.textContent = `Claude extraction${confidence}`;
  } else {
    el.textContent = `${mode}${confidence}`;
  }
}

async function showView(viewId) {
  if ((viewId === "bpBuilderView" || viewId === "projectView" || viewId === "outputsView") && !activeProject()) {
    try {
      await loadProjects();
      renderAll();
    } catch (_) {
      // The target view will show its empty state if projects cannot be loaded.
    }
  }
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
    bpBuilderView: "BP Builder",
    outputsView: "Outputs",
  };
  $("pageTitle").textContent = titles[viewId] || "Workspace";
  if (viewId === "bpBuilderView" && activeProject()) {
    showBpStep(state.bpStep || 0);
    loadBpAssumptions();
  }
}

function showBpStep(step) {
  const maxStep = 8;
  state.bpStep = Math.max(0, Math.min(maxStep, Number(step) || 0));
  document.querySelectorAll("[data-bp-step]").forEach((panel) => {
    panel.classList.toggle("active-step", Number(panel.dataset.bpStep) === state.bpStep);
  });
  document.querySelectorAll("[data-bp-step-target]").forEach((button) => {
    button.classList.toggle("active", Number(button.dataset.bpStepTarget) === state.bpStep);
  });
  if ($("bpWizardPrevButton")) $("bpWizardPrevButton").disabled = state.bpStep === 0;
  if ($("bpWizardNextButton")) $("bpWizardNextButton").textContent = state.bpStep === maxStep ? "Generate" : "Next";
}

function nextBpStep() {
  if (state.bpStep >= 8) {
    generateBpFromBuilder();
    return;
  }
  showBpStep(state.bpStep + 1);
}

function previousBpStep() {
  showBpStep(state.bpStep - 1);
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
$("claudeNavButton").addEventListener("click", () => toggleClaudePanel());
$("claudeCloseButton").addEventListener("click", () => toggleClaudePanel(false));
$("claudeUploadButton").addEventListener("click", uploadFileFromClaude);
$("claudeSendButton").addEventListener("click", sendClaudeMessage);
$("claudeApplyButton").addEventListener("click", applyClaudeToBp);
$("claudeInput").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendClaudeMessage();
  }
});
$("refreshButton").addEventListener("click", refreshWorkspace);
$("newProjectTopButton").addEventListener("click", () => showView("libraryView"));
$("createProjectButton").addEventListener("click", createProject);
$("uploadButton").addEventListener("click", uploadFile);
$("extractHistoricalsButton").addEventListener("click", extractHistoricals);
$("extractHistoricalsBuilderButton").addEventListener("click", extractHistoricals);
$("generateBpButton").addEventListener("click", generateBp);
$("generateBpOutputButton").addEventListener("click", generateBp);
$("loadBpAssumptionsButton").addEventListener("click", loadBpAssumptions);
$("saveBpAssumptionsButton").addEventListener("click", saveBpAssumptions);
$("generateBpBuilderButton").addEventListener("click", generateBpFromBuilder);
$("saveBpFinalButton").addEventListener("click", saveBpAssumptions);
$("generateBpFinalButton").addEventListener("click", generateBpFromBuilder);
$("downloadBpButton").addEventListener("click", downloadBp);
$("downloadBpBuilderButton").addEventListener("click", downloadBp);
$("downloadBpFinalButton").addEventListener("click", downloadBp);
$("aiBriefButton").addEventListener("click", generateAiBrief);
$("qoePackButton").addEventListener("click", generateQoePack);
$("restructuringButton").addEventListener("click", generateRestructuringPaper);
$("planLenderDeckButton").addEventListener("click", planLenderDeck);
$("planImDeckButton").addEventListener("click", planImDeck);
$("generateLenderDeckButton").addEventListener("click", generateLenderDeck);
$("generateImDeckButton").addEventListener("click", generateImDeck);
$("projectSearch").addEventListener("input", () => renderProjectList("projectList", true));
$("addRevenueStreamButton").addEventListener("click", addRevenueStreamRow);
$("addHistoricalLineButton").addEventListener("click", addHistoricalLineRow);
$("addCostItemButton").addEventListener("click", addCostItemRow);
$("addHeadcountLineButton").addEventListener("click", addHeadcountLine);
$("addDebtTrancheButton").addEventListener("click", addDebtTrancheRow);

document.querySelectorAll("[data-view], [data-view-button]").forEach((el) => {
  el.addEventListener("click", () => showView(el.dataset.view || el.dataset.viewButton));
});

document.querySelectorAll("[data-bp-step-target]").forEach((el) => {
  el.addEventListener("click", () => showBpStep(el.dataset.bpStepTarget));
});

$("bpWizardPrevButton").addEventListener("click", previousBpStep);
$("bpWizardNextButton").addEventListener("click", nextBpStep);

// ── Boot ──────────────────────────────────────────────────────────────────────
const redirectHandled = handleAuthRedirect();
if (!redirectHandled) bootAuthState();
