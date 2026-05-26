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
  aiIntelligence: null,
  actualsValidation: { validated: false },
  backgroundAi: {
    running: false,
    timer: null,
    lastProjectId: null,
    lastMode: "idle",
  },
  bpStep: 0,
  claudeHistory: [],
  chat: {
    threadId: "main",
    messages: [],
    streaming: false,
  },
};

const $ = (id) => document.getElementById(id);
const ACTIVE_PROJECT_STORAGE_KEY = "mg_advisory_active_project_id";
const BACKGROUND_AI_INTERVAL_MS = 90000;
const MAX_REVENUE_STREAMS = 10;
const MAX_COST_ITEMS = 12;
const MAX_HEADCOUNT_LINES = 10;
const MAX_DEBT_TRANCHES = 10;
const MAX_HISTORICAL_LINES = 24;

// ── API helper ────────────────────────────────────────────────────────────────
async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.user?.email) headers.set("X-MG-Account", accountKey());
  options.headers = headers;
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

function accountKey() {
  return String(state.user?.email || "license:local-demo").trim().toLowerCase();
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

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function showWorkspaceTransition(text) {
  const overlay = $("workspaceTransition");
  if (!overlay) return;
  if (text && $("workspaceTransitionLabel")) $("workspaceTransitionLabel").textContent = text;
  overlay.classList.remove("hidden");
  requestAnimationFrame(() => overlay.classList.add("active"));
}

function hideWorkspaceTransition() {
  const overlay = $("workspaceTransition");
  if (!overlay) return;
  overlay.classList.remove("active");
  setTimeout(() => overlay.classList.add("hidden"), 260);
}

function setPointerGlow(event) {
  const x = event.clientX || window.innerWidth / 2;
  const y = event.clientY || window.innerHeight / 2;
  document.documentElement.style.setProperty("--cursor-x", `${x}px`);
  document.documentElement.style.setProperty("--cursor-y", `${y}px`);
}

function setButtonBusy(buttonOrId, busy, label) {
  const button = typeof buttonOrId === "string" ? $(buttonOrId) : buttonOrId;
  if (!button) return;
  if (!button.dataset.defaultLabel) button.dataset.defaultLabel = button.textContent;
  button.disabled = Boolean(busy);
  button.classList.toggle("is-busy", Boolean(busy));
  button.textContent = busy ? label || "Working..." : button.dataset.defaultLabel;
}

// ── Auth: license key login ───────────────────────────────────────────────────
async function login(event) {
  event.preventDefault();
  const btn = $("licenseSubmitButton");
  setButtonBusy(btn, true, "Checking...");
  try {
    const payload = await api("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ license_key: $("licenseKey").value }),
    });
    state.unlocked = payload.ok;
    state.user = { name: "License user", email: "license:local-demo", picture: "" };
    enterWorkspace("License active");
  } catch (error) {
    $("loginMessage").textContent = error.message;
  } finally {
    setButtonBusy(btn, false);
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
  stopBackgroundAi();
  renderUserBadge();
  $("loginView").classList.remove("login-view-exit");
  $("appView").classList.remove("app-shell-enter", "app-shell-ready");
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
  showWorkspaceTransition("Preparing your finance workspace");
  $("loginView").classList.add("login-view-exit");
  await wait(280);
  $("appView").classList.remove("hidden");
  $("appView").classList.add("app-shell-enter");
  $("loginView").classList.add("hidden");
  if ($("claudeAssistant")) $("claudeAssistant").classList.remove("hidden");
  if ($("claudeNavButton")) $("claudeNavButton").classList.remove("hidden");
  $("licenseStatus").textContent = statusLabel;
  hideOverlay();
  renderUserBadge();
  try {
    await refreshWorkspace();
    startBackgroundAi();
    if ($("workspaceTransitionLabel")) $("workspaceTransitionLabel").textContent = "Loading projects and Claude context";
    await loadClaudeThread();
  } catch (error) {
    if ($("loginMessage")) $("loginMessage").textContent = error.message;
  } finally {
    await showView("dashboardView");
    await wait(180);
    $("appView").classList.add("app-shell-ready");
    $("appView").classList.remove("app-shell-enter");
    hideWorkspaceTransition();
  }
}

function startBackgroundAi() {
  if (state.backgroundAi.timer) return;
  state.backgroundAi.timer = window.setInterval(() => runBackgroundAi("interval"), BACKGROUND_AI_INTERVAL_MS);
  window.setTimeout(() => runBackgroundAi("warmup"), 1800);
}

function stopBackgroundAi() {
  if (state.backgroundAi.timer) window.clearInterval(state.backgroundAi.timer);
  state.backgroundAi.timer = null;
  state.backgroundAi.running = false;
}

async function runBackgroundAi(reason = "silent") {
  if (!state.unlocked || state.backgroundAi.running || document.hidden) return;
  const project = activeProject();
  if (!project) return;
  state.backgroundAi.running = true;
  state.backgroundAi.lastProjectId = project.id;
  try {
    const payload = await api(`/api/ai/projects/${project.id}/auto-orchestrate`, { method: "POST" });
    state.aiIntelligence = payload.intelligence || state.aiIntelligence;
    state.actualsValidation = state.aiIntelligence?.actuals_validation || state.actualsValidation;
    state.backgroundAi.lastMode = payload.mode || reason;
    renderAiIntelligence();
  } catch (error) {
    state.backgroundAi.lastMode = "quiet_error";
    if (!state.aiIntelligence) {
      state.aiIntelligence = {
        score: 0,
        stage: "Review",
        headline: "AI command layer warming up",
        narrative: error.message,
        actions: [],
        risks: [],
        modules: [],
        prompt_chips: [],
      };
      renderAiIntelligence();
    }
  } finally {
    state.backgroundAi.running = false;
  }
}

// ── Workspace ─────────────────────────────────────────────────────────────────
async function refreshWorkspace() {
  await Promise.all([loadProjects(), loadAiStatus()]);
  await loadWorkspaceIntelligence();
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
    if ($("aiModuleStatus")) $("aiModuleStatus").textContent = label;
    if ($("aiTemplateStatus")) $("aiTemplateStatus").textContent = label;
  } catch (_) {
    $("aiStatusMetric").textContent = "Offline";
    if ($("aiModuleStatus")) $("aiModuleStatus").textContent = "Offline";
  }
}

async function loadWorkspaceIntelligence() {
  const project = activeProject();
  if (!project) {
    state.aiIntelligence = null;
    state.actualsValidation = { validated: false };
    return;
  }
  try {
    const payload = await api(`/api/ai/projects/${project.id}/intelligence`);
    state.aiIntelligence = payload.intelligence || null;
    state.actualsValidation = state.aiIntelligence?.actuals_validation || { validated: false };
  } catch (error) {
    state.actualsValidation = { validated: false };
    state.aiIntelligence = {
      score: 0,
      stage: "Review",
      headline: "AI command layer unavailable",
      narrative: error.message,
      actions: [],
      risks: [{ label: "AI diagnostic offline", severity: "Medium", detail: error.message }],
      modules: [],
      prompt_chips: [],
    };
  }
}

// ── Projects ──────────────────────────────────────────────────────────────────
async function createProject() {
  setButtonBusy("createProjectButton", true, "Creating dossier...");
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
  } finally {
    setButtonBusy("createProjectButton", false);
  }
}

// ── Upload / extraction ───────────────────────────────────────────────────────
async function uploadFile() {
  setButtonBusy("uploadButton", true, "Uploading...");
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
  } finally {
    setButtonBusy("uploadButton", false);
  }
}

async function extractHistoricals() {
  setButtonBusy("extractHistoricalsButton", true, "Extracting...");
  setButtonBusy("extractHistoricalsBuilderButton", true, "Extracting...");
  showWorkspaceTransition("Claude is extracting actuals and mapping BP assumptions");
  try {
    requireUnlocked();
    const project = activeProject();
    if (!project) throw new Error("Select a project first.");
    setResult("uploadResult", "Running Claude extraction and BP sync...");
    setResult("bpBuilderResult", "Claude is extracting historicals, mapping assumptions and syncing the BP builder...");
    const payload = await api(`/api/ai/projects/${project.id}/extract-historicals`, {
      method: "POST",
    });
    if (payload.assumptions) populateBpBuilder(payload.assumptions);
    updateExtractionStatus(payload.extraction);
    renderClaudeBpBridge(payload.bridge);
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
      status: "Claude extraction synced to BP assumptions",
      periods: payload.normalized?.periods,
      bridge: payload.bridge,
      extraction: payload.extraction,
    });
    await loadWorkspaceIntelligence();
    renderAll();
  } catch (error) {
    setResult("uploadResult", error.message);
    setResult("bpBuilderResult", error.message);
  } finally {
    setButtonBusy("extractHistoricalsButton", false);
    setButtonBusy("extractHistoricalsBuilderButton", false);
    hideWorkspaceTransition();
  }
}

async function validateActuals() {
  setButtonBusy("validateActualsButton", true, "Validating...");
  setButtonBusy("validateActualsBuilderButton", true, "Validating...");
  try {
    requireUnlocked();
    const project = activeProject();
    if (!project) throw new Error("Select a project first.");
    const historicalRows = collectHistoricalRows();
    const populatedRows = historicalRows.filter((row) => row.detail_line && (row.latest_actual || row.fy2025 || row.fy2024 || row.fy2023 || row.fy2022));
    if (populatedRows.length < 5) {
      throw new Error("Actuals validation blocked: review and populate at least 5 historical lines first.");
    }
    const payload = await api(`/api/ai/projects/${project.id}/actuals-validation`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        reviewer: state.user?.name || state.user?.email || "Analyst",
        comment: "Analyst confirmed actuals mapping from SaaS workflow.",
      }),
    });
    state.actualsValidation = payload.validation || { validated: true };
    if (state.aiIntelligence) state.aiIntelligence.actuals_validation = state.actualsValidation;
    setResult("uploadResult", "Actuals mapping validated by analyst. BP configuration is now unlocked.");
    setResult("bpBuilderResult", "Actuals validation complete. Continue the BP Builder projections.");
    renderAll();
  } catch (error) {
    setResult("uploadResult", error.message);
    setResult("bpBuilderResult", error.message);
  } finally {
    setButtonBusy("validateActualsButton", false);
    setButtonBusy("validateActualsBuilderButton", false);
  }
}

// ── Claude mini assistant ────────────────────────────────────────────────────
function toggleClaudePanel(forceOpen) {
  const panel = $("claudePanel");
  if (!panel) return;
  const shouldOpen = forceOpen ?? panel.classList.contains("hidden");
  panel.classList.toggle("hidden", !shouldOpen);
  if ($("claudeNavButton")) $("claudeNavButton").classList.toggle("active", shouldOpen);
  if (shouldOpen) {
    updateClaudeContextLine();
    loadClaudeThread();
    setTimeout(() => $("claudeInput")?.focus(), 80);
  }
}

function addClaudeMessage(role, text, status = "complete") {
  const message = {
    id: `local_${Date.now()}_${Math.random().toString(16).slice(2)}`,
    role,
    content: text,
    status,
    created_at: new Date().toISOString(),
    source: "local",
  };
  state.chat.messages.push(message);
  renderClaudeMessages();
  return message;
}

function updateClaudeMessage(messageId, patch) {
  const message = state.chat.messages.find((item) => item.id === messageId);
  if (!message) return;
  Object.assign(message, patch, { updated_at: new Date().toISOString() });
  renderClaudeMessages();
}

async function loadClaudeThread() {
  if (!state.unlocked) return;
  const project = activeProject();
  if (!project) return;
  try {
    const payload = await api(`/api/ai/projects/${project.id}/chat/thread?thread_id=${encodeURIComponent(state.chat.threadId)}`);
    state.chat.messages = payload.thread?.messages || [];
  } catch (error) {
    state.chat.messages = [{
      id: "chat_load_error",
      role: "assistant",
      content: `Chat history could not be loaded: ${error.message}`,
      status: "error",
      created_at: new Date().toISOString(),
    }];
  }
  renderClaudeMessages();
}

function renderClaudeMessages() {
  const target = $("claudeMessages");
  if (!target) return;
  const nearBottom = target.scrollHeight - target.scrollTop - target.clientHeight < 80;
  const messages = state.chat.messages.length ? state.chat.messages : [{
    id: "empty_claude_state",
    role: "assistant",
    content: "I am ready to help with this dossier. Upload source files, ask for an extraction, or use a prompt chip to map data into the BP.",
    status: "complete",
    created_at: new Date().toISOString(),
  }];
  target.innerHTML = messages.map(renderClaudeMessage).join("");
  target.querySelectorAll("[data-copy-message]").forEach((button) => {
    button.addEventListener("click", () => copyClaudeMessage(button.dataset.copyMessage));
  });
  target.querySelectorAll("[data-edit-message]").forEach((button) => {
    button.addEventListener("click", () => editClaudeMessage(button.dataset.editMessage));
  });
  if (nearBottom) target.scrollTop = target.scrollHeight;
}

function setClaudeActivity(text, mode = "ready") {
  if ($("claudeResult")) $("claudeResult").textContent = text || "";
  if ($("claudeTopStatus")) $("claudeTopStatus").textContent = mode === "working" ? "Thinking" : mode === "error" ? "Review" : "Ready";
  if ($("claudePanel")) $("claudePanel").dataset.state = mode;
}

function updateClaudeContextLine() {
  if (!$("claudeContextLine")) return;
  const project = activeProject();
  $("claudeContextLine").textContent = project
    ? `${project.company_name} | ${project.project_type} | ${project.currency} | contextual BP memory active`
    : "Select a project to unlock contextual modelling support.";
}

function openClaudeWithPrompt(prompt) {
  toggleClaudePanel(true);
  if ($("claudeInput")) {
    $("claudeInput").value = prompt;
    $("claudeInput").focus();
  }
  setClaudeActivity("Prompt prepared. Review it, then ask Claude.", "ready");
}

function renderClaudeMessage(message) {
  const role = message.role === "user" ? "user" : "assistant";
  const status = message.status || "complete";
  const thinking = status === "pending" || status === "streaming"
    ? '<span class="thinking-indicator"><span></span><span></span><span></span></span>'
    : "";
  return `
    <article class="claude-message ${role} ${status}" data-message-id="${escapeHtml(message.id)}">
      <div class="claude-message-meta">
        <strong>${role === "user" ? "You" : "Claude"}</strong>
        <span>${formatTime(message.created_at)}</span>
        ${thinking}
      </div>
      <div class="claude-message-body">${renderMarkdownLite(message.content || "")}</div>
      <div class="claude-message-actions">
        <button type="button" data-copy-message="${escapeHtml(message.id)}">Copy</button>
        ${role === "user" ? `<button type="button" data-edit-message="${escapeHtml(message.id)}">Edit</button>` : ""}
      </div>
    </article>`;
}

function renderMarkdownLite(markdown) {
  const codeBlocks = [];
  let html = escapeHtml(markdown).replace(/```([\s\S]*?)```/g, (_, code) => {
    const token = `@@CODE_${codeBlocks.length}@@`;
    codeBlocks.push(`<pre><code>${code.trim()}</code></pre>`);
    return token;
  });
  html = html
    .replace(/^### (.*)$/gm, "<h4>$1</h4>")
    .replace(/^## (.*)$/gm, "<h4>$1</h4>")
    .replace(/^# (.*)$/gm, "<h4>$1</h4>")
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/^- (.*)$/gm, "<li>$1</li>")
    .replace(/(<li>.*<\/li>)/gs, "<ul>$1</ul>")
    .replace(/\n/g, "<br>");
  codeBlocks.forEach((block, idx) => {
    html = html.replace(`@@CODE_${idx}@@`, block);
  });
  return html || '<span class="muted">Empty message</span>';
}

function formatTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

async function copyClaudeMessage(messageId) {
  const message = state.chat.messages.find((item) => item.id === messageId);
  if (!message) return;
  try {
    await navigator.clipboard.writeText(message.content || "");
    $("claudeResult").textContent = "Message copied.";
  } catch (_) {
    $("claudeResult").textContent = "Copy unavailable in this browser.";
  }
}

async function editClaudeMessage(messageId) {
  const project = await activeProjectForClaude();
  const message = state.chat.messages.find((item) => item.id === messageId);
  if (!message) return;
  const edited = window.prompt("Edit message", message.content || "");
  if (edited === null || edited.trim() === message.content) return;
  await api(`/api/ai/projects/${project.id}/chat/messages/${messageId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content: edited.trim(), thread_id: state.chat.threadId }),
  });
  await loadClaudeThread();
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
  let assistant = null;
  try {
    requireUnlocked();
    const project = await activeProjectForClaude();
    const message = $("claudeInput").value.trim();
    if (!message) throw new Error("Write a message for Claude.");
    $("claudeInput").value = "";
    addClaudeMessage("user", message);
    assistant = addClaudeMessage("assistant", "", "streaming");
    setClaudeActivity("Claude is reading the dossier context and drafting an answer...", "working");
    setButtonBusy("claudeSendButton", true, "Thinking...");
    state.chat.streaming = true;
    const response = await fetch(`/api/ai/projects/${project.id}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history: [], thread_id: state.chat.threadId }),
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `Request failed (${response.status})`);
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let content = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      content += decoder.decode(value, { stream: true });
      updateClaudeMessage(assistant.id, { content, status: "streaming" });
    }
    updateClaudeMessage(assistant.id, { content, status: "complete" });
    setClaudeActivity("Claude response ready.", "ready");
    await loadClaudeThread();
  } catch (error) {
    const errorMessage = `Claude could not answer yet: ${error.message}`;
    if (assistant) updateClaudeMessage(assistant.id, { content: errorMessage, status: "error" });
    else addClaudeMessage("assistant", errorMessage);
    setClaudeActivity(error.message, "error");
  } finally {
    state.chat.streaming = false;
    setButtonBusy("claudeSendButton", false);
  }
}

async function uploadFileFromClaude() {
  setButtonBusy("claudeUploadButton", true, "Uploading...");
  try {
    requireUnlocked();
    const project = await activeProjectForClaude();
    const file = $("claudeFileInput").files[0];
    if (!file) throw new Error("Choose a PDF, Excel or CSV file first.");
    const body = new FormData();
    body.append("file", file);
    setClaudeActivity("Uploading, reading and normalizing the file...", "working");
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
    setClaudeActivity("File attached and normalized. Ask Claude to map it, or apply to BP.", "ready");
    await refreshWorkspace();
  } catch (error) {
    addClaudeMessage("assistant", `Upload failed: ${error.message}`);
    setClaudeActivity(error.message, "error");
  } finally {
    setButtonBusy("claudeUploadButton", false);
  }
}

async function applyClaudeToBp() {
  let pending = null;
  setButtonBusy("claudeApplyButton", true, "Applying...");
  showWorkspaceTransition("Claude is applying conversation outputs into the BP");
  try {
    requireUnlocked();
    const project = await activeProjectForClaude();
    const message = $("claudeInput").value.trim() || "Extract all useful financial statements, debt and BP assumptions from this conversation and apply them to the BP model.";
    addClaudeMessage("user", `[Apply to BP] ${message}`);
    pending = addClaudeMessage("assistant", "Claude is extracting and applying the data to the BP...");
    setClaudeActivity("Claude is extracting, mapping and applying to BP data...", "working");
    const payload = await api(`/api/ai/projects/${project.id}/chat/apply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history: [], thread_id: state.chat.threadId }),
    });
    populateBpBuilder(payload.assumptions || {});
    updateExtractionStatus(payload.extraction);
    renderClaudeBpBridge(payload.bridge);
    const bridge = payload.bridge || {};
    const appliedMessage = `Applied to BP data. ${bridge.historical_lines ?? 0} historical lines, ${bridge.revenue_streams ?? 0} revenue streams, ${bridge.cost_items ?? 0} cost items and ${bridge.debt_tranches ?? 0} debt layers are now feeding the BP builder. Generate a new Excel BP to push this into the workbook.`;
    if (pending) updateClaudeMessage(pending.id, { content: appliedMessage, status: "complete" });
    setResult("bpBuilderResult", {
      status: "Claude chat applied to BP",
      periods: payload.normalized?.periods,
      bridge: payload.bridge,
      extraction: payload.extraction,
    });
    setClaudeActivity("Applied to BP data.", "ready");
    await refreshWorkspace();
  } catch (error) {
    const errorMessage = `Claude could not apply the data: ${error.message}`;
    if (pending) updateClaudeMessage(pending.id, { content: errorMessage, status: "error" });
    else addClaudeMessage("assistant", errorMessage);
    setClaudeActivity(error.message, "error");
  } finally {
    setButtonBusy("claudeApplyButton", false);
    hideWorkspaceTransition();
  }
}

async function regenerateClaudeResponse() {
  setButtonBusy("claudeRegenerateButton", true, "Regenerating...");
  try {
    requireUnlocked();
    const project = await activeProjectForClaude();
    const pending = addClaudeMessage("assistant", "Regenerating response...", "pending");
    const payload = await api(`/api/ai/projects/${project.id}/chat/regenerate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: "", history: [], thread_id: state.chat.threadId }),
    });
    updateClaudeMessage(pending.id, { content: payload.reply || payload.message?.content || "Regenerated.", status: "complete" });
    await loadClaudeThread();
  } catch (error) {
    addClaudeMessage("assistant", `Regenerate failed: ${error.message}`, "error");
    setClaudeActivity(error.message, "error");
  } finally {
    setButtonBusy("claudeRegenerateButton", false);
  }
}

// ── Outputs ───────────────────────────────────────────────────────────────────
async function generateBp() {
  setButtonBusy("generateBpButton", true, "Generating...");
  setButtonBusy("generateBpOutputButton", true, "Generating...");
  showWorkspaceTransition("Building formula-driven Excel BP and checks");
  try {
    requireUnlocked();
    const project = activeProject();
    if (!project) throw new Error("Select a project first.");
    assertBpGenerationAllowed();
    setResult("outputResult", "Generating institutional Excel BP… (this takes ~10 seconds)");
    const payload = await api(`/api/projects/${project.id}/bp/generate`, { method: "POST" });
    state.lastOutput = payload.output;
    if ($("modelStatusMetric")) $("modelStatusMetric").textContent = "Generated";
    setResult("outputResult", payload.output);
  } catch (error) {
    setResult("outputResult", error.message);
  } finally {
    setButtonBusy("generateBpButton", false);
    setButtonBusy("generateBpOutputButton", false);
    hideWorkspaceTransition();
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
  setButtonBusy("saveBpAssumptionsButton", true, "Saving...");
  setButtonBusy("saveBpFinalButton", true, "Saving...");
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
  } finally {
    setButtonBusy("saveBpAssumptionsButton", false);
    setButtonBusy("saveBpFinalButton", false);
  }
}

function updateBpReadiness() {
  if (!$("bpReadinessScore")) return;
  const assumptions = collectBpBuilder();
  const issues = [];
  let score = 0;
  const revenueRows = assumptions.revenue_streams.filter((row) => row.name && row.volume > 0 && row.price > 0);
  const historicalRows = assumptions.historical_actuals.filter((row) => row.detail_line && (row.latest_actual || row.fy2025 || row.fy2024));
  const debtRows = assumptions.debt_tranches.filter((row) => row.name && (row.opening_balance || row.commitment));
  const costRows = assumptions.cost_items.filter((row) => row.name && (row.monthly_fixed || row.percent_revenue || row.cost_per_fte));
  const headcountRows = assumptions.headcount.filter((row) => row.department && row.opening_fte >= 0 && row.avg_salary_month >= 0);

  if (assumptions.model.model_start_date) score += 10; else issues.push("Set forecast start date.");
  if (assumptions.model.actuals_end_date) score += 10; else issues.push("Set last actuals date.");
  if (historicalRows.length >= 3 || assumptions.model.historical_source === "Claude extraction") score += 18; else issues.push("Add or extract historical actuals.");
  if (revenueRows.length >= 1) score += 18; else issues.push("Add at least one revenue stream with volume and price.");
  if (costRows.length >= 3) score += 12; else issues.push("Add key cost lines.");
  if (headcountRows.length >= 1) score += 8; else issues.push("Add headcount or payroll assumptions.");
  if (assumptions.working_capital.dso || assumptions.working_capital.dpo) score += 8; else issues.push("Set working capital days.");
  if (debtRows.length >= 1 || assumptions.model.opening_debt === 0) score += 10; else issues.push("Add debt layers or set opening debt to zero.");
  if (assumptions.covenants.max_net_debt_ebitda && assumptions.covenants.min_liquidity) score += 6; else issues.push("Set covenant thresholds.");

  const readiness = Math.min(100, score);
  $("bpReadinessScore").textContent = `${readiness}%`;
  $("bpReadinessBar").style.width = `${readiness}%`;
  $("bpOperatingStatus").textContent = revenueRows.length ? `${revenueRows.length} revenue line${revenueRows.length > 1 ? "s" : ""}` : "Needs revenue";
  $("bpDebtStatus").textContent = debtRows.length ? `${debtRows.length} debt layer${debtRows.length > 1 ? "s" : ""}` : "No debt layer";
  $("bpReadinessIssues").innerHTML = issues.slice(0, 4).map((issue) => `<span>${escapeHtml(issue)}</span>`).join("") || "<span>Ready to generate and review Excel outputs.</span>";
}

function bpGenerationIssues() {
  const assumptions = collectBpBuilder();
  const revenueRows = assumptions.revenue_streams.filter((row) => row.name && row.volume > 0 && row.price > 0);
  const historicalRows = assumptions.historical_actuals.filter((row) => row.detail_line && (row.latest_actual || row.fy2025 || row.fy2024 || row.fy2023));
  const costRows = assumptions.cost_items.filter((row) => row.name && (row.monthly_fixed || row.percent_revenue || row.cost_per_fte));
  const headcountRows = assumptions.headcount.filter((row) => row.department && row.avg_salary_month >= 0);
  const debtRows = assumptions.debt_tranches.filter((row) => row.name && (row.opening_balance || row.commitment));
  const issues = [];
  if (!activeProject()) issues.push("Create or select a dossier.");
  if (historicalRows.length < 5) issues.push("Transfer at least 5 actual historical lines.");
  if (!state.actualsValidation?.validated) issues.push("Run the analyst actuals validation check.");
  if (!assumptions.model.model_start_date || !assumptions.model.actuals_end_date) issues.push("Complete model setup dates.");
  if (revenueRows.length < 1) issues.push("Add at least one revenue stream with volume and price.");
  if (costRows.length < 3) issues.push("Add at least three key cost lines.");
  if (headcountRows.length < 1) issues.push("Add headcount/payroll assumptions.");
  if (!assumptions.working_capital.dso || !assumptions.working_capital.dpo) issues.push("Complete working capital assumptions.");
  if (assumptions.model.opening_debt > 0 && debtRows.length < 1) issues.push("Add at least one debt layer or set opening debt to zero.");
  if (!assumptions.covenants.max_net_debt_ebitda || !assumptions.covenants.min_liquidity) issues.push("Complete covenant thresholds.");
  return issues;
}

function assertBpGenerationAllowed() {
  const issues = bpGenerationIssues();
  if (!issues.length) return true;
  const message = `BP generation locked:\n- ${issues.join("\n- ")}`;
  setResult("bpBuilderResult", message);
  setResult("outputResult", message);
  throw new Error(message);
}

async function generateBpFromBuilder() {
  setButtonBusy("generateBpBuilderButton", true, "Generating...");
  setButtonBusy("generateBpFinalButton", true, "Generating...");
  setButtonBusy("bpWizardNextButton", true, "Generating...");
  showWorkspaceTransition("Generating institutional BP model from assumptions");
  try {
    assertBpGenerationAllowed();
    await saveBpAssumptions();
    setResult("bpBuilderResult", "Generating Excel BP with saved assumptions...");
    const project = activeProject();
    const payload = await api(`/api/projects/${project.id}/bp/generate`, { method: "POST" });
    state.lastOutput = payload.output;
    if ($("modelStatusMetric")) $("modelStatusMetric").textContent = "Generated";
    setResult("bpBuilderResult", payload.output);
  } catch (_) {
    // saveBpAssumptions already writes the message
  } finally {
    setButtonBusy("generateBpBuilderButton", false);
    setButtonBusy("generateBpFinalButton", false);
    setButtonBusy("bpWizardNextButton", false);
    hideWorkspaceTransition();
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
  updateBpReadiness();
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
  renderAiIntelligence();
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
  const project = activeProject();
  const activeCount = state.projects.filter((p) => (p.status || "active") === "active").length;
  const bpReady = project ? "Ready to configure" : "Select dossier";
  if ($("projectCount")) $("projectCount").textContent = activeCount;
  if ($("activeProjectMetric")) $("activeProjectMetric").textContent = project ? project.company_name : "None";
  if ($("dashboardHeroTitle")) $("dashboardHeroTitle").textContent = project ? `${project.company_name}: next BP step is ready.` : "Build the BP step by step.";
  if ($("dashboardHeroCopy")) $("dashboardHeroCopy").textContent = project
    ? `Current dossier: ${project.project_type} | ${project.currency}. Follow the next action below; the system blocks anything risky until the required checks are done.`
    : "Create a dossier, upload actuals, validate the mapping, then fill the BP assumptions. The app tells you exactly what is missing.";
  const needsActualsValidation = project && !state.actualsValidation?.validated;
  if ($("dashboardNextAction")) $("dashboardNextAction").textContent = !project ? "Create your first dossier" : needsActualsValidation ? "Upload and validate actuals" : "Complete BP assumptions";
  if ($("dashboardNextActionCopy")) $("dashboardNextActionCopy").textContent = !project
    ? "A dossier is the company file. It keeps uploads, extracted historicals, BP assumptions and outputs together."
    : needsActualsValidation
      ? "Upload source files, let Claude prepare the mapping, then confirm the actuals manually before projections unlock."
      : "Actuals are validated. Now fill revenue, costs, working capital, debt and covenants.";
  if ($("dashboardPrimaryAction")) {
    $("dashboardPrimaryAction").textContent = !project ? "Open project library" : needsActualsValidation ? "Open actuals transfer" : "Open BP Builder";
    $("dashboardPrimaryAction").dataset.viewButton = !project ? "libraryView" : needsActualsValidation ? "projectView" : "bpBuilderView";
  }
  if ($("dashboardWorkspaceLabel")) $("dashboardWorkspaceLabel").textContent = project ? project.company_name : "No dossier selected";
  if ($("dashboardWorkspaceMeta")) $("dashboardWorkspaceMeta").textContent = project ? `${project.project_type} | ${project.currency} | updated ${formatDate(project.updated_at)}` : "Select a project to unlock the operating workflow.";
  if ($("dashboardHealthData")) $("dashboardHealthData").textContent = project ? "Active" : "Data";
  if ($("dashboardHealthBp")) $("dashboardHealthBp").textContent = project ? bpReady : "BP";
  if ($("dashboardHealthOutputs")) $("dashboardHealthOutputs").textContent = project ? "Generate" : "Outputs";
  if ($("dashboardAIContext")) $("dashboardAIContext").textContent = project
    ? `Claude watches ${project.company_name} in the background and flags missing actuals or assumptions.`
    : "Claude prepares mappings and flags missing items quietly once a dossier is selected.";
  updateClaudeContextLine();
  if ($("dashboardAccountName")) $("dashboardAccountName").textContent = state.user?.email || "License workspace";
  if ($("dashboardActiveProject")) $("dashboardActiveProject").textContent = project ? project.company_name : "No active dossier";
  if ($("dashboardBpStatus")) $("dashboardBpStatus").textContent = bpReady;
  if ($("dashboardOutputStatus")) $("dashboardOutputStatus").textContent = project ? "Available after generation" : "No dossier selected";
  if ($("libraryAccountLabel")) $("libraryAccountLabel").textContent = state.user?.email || "License workspace";
  if ($("libraryProjectCount")) $("libraryProjectCount").textContent = `${activeCount} active dossier${activeCount === 1 ? "" : "s"}`;
  renderWorkflowRail();
}

function workflowState() {
  const project = activeProject();
  const intel = state.aiIntelligence || {};
  const modules = intel.modules || [];
  const historicalModule = modules.find((item) => item.name === "Historicals");
  const docsCount = Number(intel.documents_count || 0);
  const assumptions = $("bpBuilderWorkspace") ? collectBpBuilder() : null;
  const generationIssues = assumptions ? bpGenerationIssues() : ["BP not loaded"];
  return [
    { key: "library", label: "1. Company file", view: "libraryView", complete: Boolean(project), locked: false, note: project ? project.company_name : "Create or select" },
    { key: "actuals", label: "2. Actuals", view: "projectView", complete: docsCount > 0 || historicalModule?.status === "Ready", locked: !project, note: docsCount ? `${docsCount} file${docsCount > 1 ? "s" : ""} uploaded` : "Upload PDFs/Excel" },
    { key: "validate", label: "3. Validate", view: "projectView", complete: Boolean(state.actualsValidation?.validated), locked: !project, note: state.actualsValidation?.validated ? "Checked by analyst" : "Manual check" },
    { key: "outputs", label: "4. Build BP", view: "bpBuilderView", complete: generationIssues.length === 0, locked: !state.actualsValidation?.validated, note: generationIssues.length ? `${generationIssues.length} item${generationIssues.length > 1 ? "s" : ""} missing` : "Ready to generate" },
  ];
}

function renderWorkflowRail() {
  const rail = $("workflowRail");
  if (!rail) return;
  rail.innerHTML = workflowState().map((step, index) => {
    const stateClass = step.complete ? "complete" : step.locked ? "locked" : "current";
    return `<article class="workflow-step ${stateClass}">
      <span>${index + 1}</span>
      <strong>${escapeHtml(step.label)}</strong>
      <em>${escapeHtml(step.note)}</em>
    </article>`;
  }).join("");
  if ($("actualsValidationStatus")) {
    $("actualsValidationStatus").textContent = state.actualsValidation?.validated ? "Actuals validated" : "Actuals not validated";
  }
  if ($("actualsValidationCopy")) {
    $("actualsValidationCopy").textContent = state.actualsValidation?.validated
      ? `Validated by ${state.actualsValidation.reviewer || "Analyst"}. Continue to BP Builder.`
      : "Review extracted historical rows and confirm that P&L, balance sheet, cash flow, debt and working capital lines are mapped correctly.";
  }
  ["validateActualsButton", "validateActualsBuilderButton"].forEach((id) => {
    const button = $(id);
    if (button) button.textContent = state.actualsValidation?.validated ? "Actuals validated" : "Validate actuals";
  });
}

function renderAiIntelligence() {
  const intel = state.aiIntelligence;
  const project = activeProject();
  const score = intel?.score ?? 0;
  if ($("aiReadinessScore")) $("aiReadinessScore").textContent = project ? `${score}%` : "0%";
  if ($("aiReadinessStage")) $("aiReadinessStage").textContent = project ? intel?.stage || "Review" : "Waiting";
  if ($("aiCommandHeadline")) $("aiCommandHeadline").textContent = project ? intel?.headline || "AI command layer active" : "Select a dossier to activate the AI command layer";
  if ($("aiCommandNarrative")) $("aiCommandNarrative").textContent = project ? intel?.narrative || "Claude is monitoring model readiness." : "Claude will monitor data coverage, BP assumptions and output readiness.";
  if ($("aiModuleStrip")) {
    const modules = intel?.modules || [];
    $("aiModuleStrip").innerHTML = modules.length
      ? modules.map((item) => `<span class="${statusClass(item.status)}"><strong>${escapeHtml(item.name)}</strong><em>${escapeHtml(item.status)}</em><small>${escapeHtml(item.detail || "")}</small></span>`).join("")
      : '<span><strong>Historicals</strong><em>Waiting</em><small>No active dossier</small></span>';
  }
  if ($("aiRiskList")) {
    const risks = intel?.risks || [];
    $("aiRiskList").innerHTML = risks.length
      ? risks.map((risk) => `<div class="${severityClass(risk.severity)}"><strong>${escapeHtml(risk.label)}</strong><span>${escapeHtml(risk.detail || "")}</span></div>`).join("")
      : '<div><strong>No active AI risks</strong><span>Select a dossier to run the command diagnostic.</span></div>';
  }
  if ($("bpAiNudge")) {
    const primary = intel?.actions?.[0] || intel?.next_action;
    const label = primary?.label || "Ask Claude for the next modelling gap";
    const prompt = primary?.prompt || "Review the BP Builder and identify the highest-impact missing assumption before Excel generation.";
    $("bpAiNudge").querySelector("strong").textContent = project ? label : "Claude will surface the next modelling gap once a dossier is active.";
    const button = $("bpAiNudge").querySelector("button");
    if (button) button.dataset.claudePrompt = prompt;
  }
}

function statusClass(status) {
  const value = String(status || "").toLowerCase();
  if (value.includes("ready")) return "is-ready";
  if (value.includes("missing")) return "is-missing";
  return "needs-work";
}

function severityClass(severity) {
  const value = String(severity || "").toLowerCase();
  if (value.includes("high")) return "risk-high";
  if (value.includes("low")) return "risk-low";
  return "risk-medium";
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
    row.addEventListener("click", async () => {
      state.activeProjectId = row.dataset.projectId;
      localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, state.activeProjectId);
      await loadWorkspaceIntelligence();
      renderAll();
      loadClaudeThread();
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

function renderClaudeBpBridge(bridge) {
  if (!$("claudeBpBridgeStatus")) return;
  if (!bridge) {
    $("claudeBpBridgeStatus").textContent = "Waiting for Claude extraction";
    $("claudeBpBridgeLines").textContent = "-";
    $("claudeBpBridgeRevenue").textContent = "-";
    $("claudeBpBridgeCosts").textContent = "-";
    $("claudeBpBridgeDebt").textContent = "-";
    return;
  }
  $("claudeBpBridgeStatus").textContent = `${bridge.status || "Synced"} / ${bridge.confidence || "review"}`;
  $("claudeBpBridgeLines").textContent = bridge.historical_lines ?? 0;
  $("claudeBpBridgeRevenue").textContent = bridge.revenue_streams ?? 0;
  $("claudeBpBridgeCosts").textContent = bridge.cost_items ?? 0;
  $("claudeBpBridgeDebt").textContent = bridge.debt_tranches ?? 0;
}

async function showView(viewId) {
  const guard = viewAccessIssue(viewId);
  if (guard) {
    setResult("bpBuilderResult", guard);
    setResult("outputResult", guard);
    if ($("uploadResult")) setResult("uploadResult", guard);
    return;
  }
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
    if (!state.actualsValidation?.validated) state.bpStep = 1;
    showBpStep(state.bpStep || 0);
    loadBpAssumptions();
  }
}

function viewAccessIssue(viewId) {
  if (viewId === "dashboardView" || viewId === "libraryView") return "";
  if (!activeProject()) return "Create or select a dossier first.";
  if (viewId === "outputsView") {
    const issues = bpGenerationIssues();
    if (issues.length) return `Outputs are locked until BP inputs are complete:\n- ${issues.join("\n- ")}`;
  }
  return "";
}

function showBpStep(step) {
  const maxStep = 8;
  const requested = Math.max(0, Math.min(maxStep, Number(step) || 0));
  const allowed = maxAllowedBpStep();
  if (requested > allowed) {
    setResult("bpBuilderResult", allowed < 2 ? "Projection steps are locked until actuals are transferred and manually validated." : "Complete the previous BP inputs before moving forward.");
  }
  state.bpStep = Math.min(requested, allowed);
  document.querySelectorAll("[data-bp-step]").forEach((panel) => {
    panel.classList.toggle("active-step", Number(panel.dataset.bpStep) === state.bpStep);
  });
  document.querySelectorAll("[data-bp-step-target]").forEach((button) => {
    button.classList.toggle("active", Number(button.dataset.bpStepTarget) === state.bpStep);
  });
  if ($("bpWizardPrevButton")) $("bpWizardPrevButton").disabled = state.bpStep === 0;
  if ($("bpWizardNextButton")) $("bpWizardNextButton").textContent = state.bpStep === maxStep ? "Generate" : "Next";
  updateBpReadiness();
}

function maxAllowedBpStep() {
  if (!activeProject()) return 0;
  if (!state.actualsValidation?.validated) return 1;
  return 8;
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
$("claudeRegenerateButton").addEventListener("click", regenerateClaudeResponse);
$("claudeInput").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendClaudeMessage();
  }
});
document.querySelectorAll("[data-claude-prompt]").forEach((button) => {
  button.addEventListener("click", () => openClaudeWithPrompt(button.dataset.claudePrompt || ""));
});
$("refreshButton").addEventListener("click", refreshWorkspace);
$("newProjectTopButton").addEventListener("click", () => showView("libraryView"));
$("createProjectButton").addEventListener("click", createProject);
$("uploadButton").addEventListener("click", uploadFile);
$("extractHistoricalsButton").addEventListener("click", extractHistoricals);
$("extractHistoricalsBuilderButton").addEventListener("click", extractHistoricals);
$("validateActualsButton").addEventListener("click", validateActuals);
$("validateActualsBuilderButton").addEventListener("click", validateActuals);
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
$("bpBuilderWorkspace").addEventListener("input", updateBpReadiness);
$("bpBuilderWorkspace").addEventListener("change", updateBpReadiness);

document.querySelectorAll("[data-view], [data-view-button]").forEach((el) => {
  el.addEventListener("click", () => showView(el.dataset.view || el.dataset.viewButton));
});

document.querySelectorAll("[data-bp-step-target]").forEach((el) => {
  el.addEventListener("click", () => showBpStep(el.dataset.bpStepTarget));
});

window.addEventListener("pointermove", setPointerGlow, { passive: true });
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) runBackgroundAi("resume");
});
setPointerGlow({ clientX: window.innerWidth * 0.72, clientY: window.innerHeight * 0.28 });

$("bpWizardPrevButton").addEventListener("click", previousBpStep);
$("bpWizardNextButton").addEventListener("click", nextBpStep);

// ── Boot ──────────────────────────────────────────────────────────────────────
const redirectHandled = handleAuthRedirect();
if (!redirectHandled) bootAuthState();
