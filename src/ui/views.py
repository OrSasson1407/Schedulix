"""
Server-side HTML rendering for Schedulix (Python + CSS only).
This module is responsible for generating the entire HTML structure of the application.
Although the UI primarily relies on traditional form submissions and links handled by app.py,
a small JavaScript layer is included to intercept forms and handle them via AJAX (fetch)
for a smoother, flicker-free user experience.
"""

from __future__ import annotations

import html
from datetime import datetime
from urllib.parse import urlencode

# ==========================================
# CONSTANTS & CONFIGURATIONS
# ==========================================

# Mapping of program IDs to their full names
PROGRAM_NAMES = {
    "83101": "Computer Engineering",
    "83102": "Electrical Engineering",
    "83104": "Industrial & Information Systems",
    "83107": "Data Engineering",
    "83108": "Software Engineering",
    "83109": "Materials Engineering",
    "83105": "Computer Engineering – Computer Hardware",
    "83182": "Electrical Engineering – Quantum Engineering",
    "83103": "Electrical Engineering – Neuro Engineering",
    "83115": "Electrical Engineering – Bio-Medical Engineering",
}

# Titles displayed at the top bar for each main screen
SCREEN_TITLES = {
    "input": "<strong>Input</strong> — Load files &amp; select programs",
    "calendar": "<strong>Calendar</strong> — Moed Aleph &amp; Moed Bet date configuration",
    "output": "<strong>Output</strong> — Browse &amp; export combined schedules",
    "settings": "<strong>Settings</strong> — Configurable hard constraints",
}

# Metadata describing each configurable hard constraint. Drives the Settings UI.
# 'min_k' encodes whether the parameter must be positive (1) or non-negative (0).
CONSTRAINT_META = [
    {
        "key": "mandatory_spacing",
        "label": "Mandatory Exam Spacing",
        "desc": "Minimum number of days between any two mandatory course exams "
                "within the same study program and the same year.",
        "k_label": "Minimum days (k ≥ 1)",
        "min_k": 1,
    },
    {
        "key": "general_spacing",
        "label": "General Exam Spacing",
        "desc": "Minimum number of days between any two exams (mandatory or "
                "elective) within the same study program and the same year.",
        "k_label": "Minimum days (k ≥ 1)",
        "min_k": 1,
    },
    {
        "key": "elective_collisions",
        "label": "Elective Collisions Limit",
        "desc": "Maximum number of same-day collisions allowed between any two "
                "elective courses within the same study program.",
        "k_label": "Max collisions (k ≥ 0)",
        "min_k": 0,
    },
    {
        "key": "mandatory_window",
        "label": "Mandatory Exam Window",
        "desc": "Minimum number of days between the first and the last mandatory "
                "exam for a specific program, year and term (Moed).",
        "k_label": "Minimum days (k ≥ 1)",
        "min_k": 1,
    },
    {
        "key": "daily_capacity",
        "label": "Daily Global Capacity",
        "desc": "Maximum number of exams allowed on the exact same day across the "
                "entire system.",
        "k_label": "Max exams/day (k ≥ 1)",
        "min_k": 1,
    },
    {
        "key": "moed_spacing",
        "label": "Moed A → Moed B Spacing",
        "desc": "Minimum number of days between the Moed Aleph and Moed Bet exam "
                "of the same course.",
        "k_label": "Minimum days (k ≥ 1)",
        "min_k": 1,
    },
]

# Steps used for the quick pagination buttons in the output screen (e.g., jump 10 pages forward)
PAGE_JUMP_STEPS = [1, 2, 3, 5, 10, 20, 50, 100, 200, 500, 1000]

# Predefined date ranges for major holidays to quickly exclude them from the exam calendar
HOLIDAY_PRESETS = {
    "rosh_hashana": {
        "label": "Rosh Hashana",
        "ranges": [
            ("2024-10-02", "2024-10-04"),
            ("2025-09-22", "2025-09-24"),
            ("2026-09-11", "2026-09-13"),
            ("2027-10-01", "2027-10-03"),
        ],
    },
    "yom_kippur": {
        "label": "Yom Kippur",
        "ranges": [
            ("2024-10-11", "2024-10-12"),
            ("2025-10-01", "2025-10-02"),
            ("2026-09-20", "2026-09-21"),
            ("2027-10-10", "2027-10-11"),
        ],
    },
    "sukkot": {
        "label": "Sukkot",
        "ranges": [
            ("2024-10-16", "2024-10-23"),
            ("2025-10-06", "2025-10-13"),
            ("2026-09-25", "2026-10-02"),
            ("2027-10-15", "2027-10-22"),
        ],
    },
    "pesach": {
        "label": "Passover",
        "ranges": [
            ("2025-04-12", "2025-04-20"),
            ("2026-04-01", "2026-04-09"),
            ("2027-04-21", "2027-04-29"),
        ],
    },
    "shavuot": {
        "label": "Shavuot",
        "ranges": [
            ("2025-06-01", "2025-06-03"),
            ("2026-05-21", "2026-05-23"),
            ("2027-06-10", "2027-06-12"),
        ],
    },
    "independence": {
        "label": "Independence Day",
        "ranges": [
            ("2025-04-30", "2025-04-30"),
            ("2026-04-22", "2026-04-22"),
            ("2027-05-12", "2027-05-12"),
        ],
    },
}

DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

LOGO_URL = "/public/SchedulixLogo.jpeg"


# ==========================================
# UTILITY FUNCTIONS
# ==========================================

def _e(s) -> str:
    """
    Escapes a string for safe HTML rendering to prevent XSS (Cross-Site Scripting) attacks.
    Converts characters like '<' to '&lt;'.
    """
    return html.escape(str(s)) if s is not None else ""


def _url(screen: str, **params) -> str:
    """
    Constructs a URL string with query parameters.
    Example: _url('output', page=2) -> '/?screen=output&page=2'
    Filters out parameters that are None or empty strings.
    """
    q = {"screen": screen, **{k: v for k, v in params.items() if v is not None and v != ""}}
    return "/?" + urlencode(q)


def _hidden_fields(fields: dict) -> str:
    """
    Generates HTML hidden input fields from a dictionary.
    Useful for passing state data through forms.
    """
    return "".join(
        f'<input type="hidden" name="{_e(k)}" value="{_e(v)}"/>'
        for k, v in fields.items()
    )


def _render_file_picker(picker_id: str) -> str:
    """Custom English file picker (avoids browser-locale native input labels)."""
    return f"""
<div class="file-picker">
  <input type="file" name="file" id="{_e(picker_id)}" accept=".txt" required class="file-picker-input"/>
  <label for="{_e(picker_id)}" class="btn btn-secondary file-picker-btn">Choose file</label>
  <span class="file-picker-name" data-placeholder="No file chosen">No file chosen</span>
</div>"""


def _theme_toggle_button(*, sidebar: bool = False) -> str:
    """Reusable light/dark toggle; works in topbar and sidebar."""
    btn_id = "theme-toggle-sidebar" if sidebar else "theme-toggle"
    label = '<span class="theme-label">Appearance</span>' if sidebar else ""
    return (
        f'<button type="button" class="btn btn-ghost theme-toggle" id="{btn_id}" '
        f'aria-label="Toggle color theme" title="Toggle color theme">'
        f'<span class="theme-icon theme-icon-dark" aria-hidden="true">🌙</span>'
        f'<span class="theme-icon theme-icon-light" aria-hidden="true">☀️</span>'
        f"{label}</button>"
    )


def _render_toast_shell(flash: dict | None = None) -> str:
    """Center-screen notification overlay (flash on load or empty shell for JS)."""
    if flash and flash.get("msg"):
        kind = flash.get("type", "ok")
        card_cls = "ok" if kind == "ok" else "err"
        title = "Success" if kind == "ok" else "Error"
        icon = "✓" if kind == "ok" else "!"
        overlay_cls = "toast-overlay show"
        message = _e(flash["msg"])
    else:
        card_cls = ""
        title = icon = message = ""
        overlay_cls = "toast-overlay"
    return f"""
<div id="toast-overlay" class="{overlay_cls}">
  <div id="toast-card" class="toast-card {card_cls}" role="alertdialog" aria-live="polite">
    <div class="toast-icon" aria-hidden="true">{icon}</div>
    <div class="toast-body">
      <div class="toast-title">{title}</div>
      <div class="toast-message">{message}</div>
    </div>
    <button type="button" class="toast-close" aria-label="Dismiss" onclick="schedulixHideToast()">×</button>
  </div>
</div>"""


# ==========================================
# MAIN LAYOUT RENDERING
# ==========================================

def render_page(ctx: dict) -> str:
    """
    The main entry point for rendering the entire HTML document.
    It takes a context dictionary ('ctx') containing all the data needed for the current state,
    determines which screen to show, and wraps it in the master HTML layout.
    """
    # Determine the current screen (defaults to 'input')
    screen = ctx.get("screen", "input")
    
    # Handle flash messages (center-screen notification)
    flash = ctx.get("flash")
    flash_html = _render_toast_shell(flash if flash and flash.get("msg") else None)

    # Determine system status based on loaded files
    status_ok = ctx.get("courses_count", 0) > 0 and ctx.get("periods_count", 0) > 0
    dot = "dot-green" if status_ok else "dot-gray"
    status_line = (
        f'{ctx.get("courses_count", 0)} courses · {ctx.get("periods_count", 0)} periods · '
        f'{len(ctx.get("selected_programs", []))} selected'
    )

    # Build the sidebar navigation links
    nav = ""
    for sid, icon, label in [
        ("input", "📁", "Input"),
        ("calendar", "📅", "Calendar"),
        ("settings", "⚙️", "Settings"),
        ("output", "📊", "Output"),
    ]:
        active = " active" if screen == sid else ""
        nav += (
            f'<a class="nav-item{active}" href="{_url(sid)}">'
            f'<span class="nav-icon">{icon}</span> {label}</a>'
        )

    # Delegate body rendering to the specific screen function
    if screen == "input":
        body = _render_input(ctx)
    elif screen == "calendar":
        body = _render_calendar(ctx)
    elif screen == "settings":
        body = _render_settings(ctx)
    else:
        body = _render_output(ctx)

    # Maintain scroll position if the page reloads
    scroll_y = int(ctx.get("content_scroll_y") or 0)

    # Return the full HTML document
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Schedulix v34.0</title>
<link rel="icon" href="{LOGO_URL}" type="image/jpeg"/>
<script>
(function () {{
  var key = "schedulix-theme";
  var stored = localStorage.getItem(key);
  var theme = stored === "light" || stored === "dark"
    ? stored
    : (window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
  document.documentElement.setAttribute("data-theme", theme);
}})();
</script>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:ital,wght@0,400;0,700;1,400&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet"/>
<link rel="stylesheet" href="/static/style.css"/>
</head>
<body>
<div class="shell">
  <nav class="sidebar">
    <div class="logo logo-brand">
      <img class="logo-img" src="{LOGO_URL}" alt="Schedulix logo" width="48" height="48"/>
      <div class="logo-text">
        <span class="logo-name">Schedulix</span>
        <span class="logo-version">Version 34.0</span>
      </div>
    </div>
    {nav}
    <div class="sidebar-footer">
      <div style="font-size:11px; color:var(--muted); margin-bottom:6px;">Status</div>
      <div style="display:flex; align-items:center; font-size:12px;">
        <span class="status-dot {dot}"></span>
        <span style="font-size:11px; color:var(--muted);">{_e(status_line)}</span>
      </div>
      <div class="sidebar-theme">{_theme_toggle_button(sidebar=True)}</div>
    </div>
  </nav>
  
  <div class="main">
    <div class="topbar">
      <div class="topbar-title">{SCREEN_TITLES.get(screen, "")}</div>
      <div class="topbar-actions">{_theme_toggle_button()}</div>
    </div>
    <div class="content">
      {body}
    </div>
  </div>
</div>
{flash_html}

<script>
(function () {{
  function schedulixApplyTheme(theme) {{
    if (theme !== "light" && theme !== "dark") theme = "dark";
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("schedulix-theme", theme);
    document.querySelectorAll(".theme-toggle").forEach(function (btn) {{
      btn.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
      btn.title = theme === "dark" ? "Switch to light mode" : "Switch to dark mode";
    }});
  }}

  function schedulixToggleTheme() {{
    var cur = document.documentElement.getAttribute("data-theme") || "dark";
    schedulixApplyTheme(cur === "dark" ? "light" : "dark");
  }}

  window.schedulixApplyTheme = schedulixApplyTheme;
  window.schedulixToggleTheme = schedulixToggleTheme;
  schedulixApplyTheme(document.documentElement.getAttribute("data-theme") || "dark");
  document.querySelectorAll(".theme-toggle").forEach(function (btn) {{
    btn.addEventListener("click", schedulixToggleTheme);
  }});

  // Center-screen notification toast
  function hideToast() {{
    var overlay = document.getElementById("toast-overlay");
    if (overlay) overlay.classList.remove("show");
  }}

  function showToast(msg, type) {{
    var overlay = document.getElementById("toast-overlay");
    var el = document.getElementById("toast-card");
    if (!overlay || !el) return;
    type = type || "ok";
    var isOk = type === "ok";
    el.className = "toast-card " + (isOk ? "ok" : "err");
    var iconEl = el.querySelector(".toast-icon");
    var titleEl = el.querySelector(".toast-title");
    var msgEl = el.querySelector(".toast-message");
    if (iconEl) iconEl.textContent = isOk ? "✓" : "!";
    if (titleEl) titleEl.textContent = isOk ? "Success" : "Error";
    if (msgEl) msgEl.textContent = msg;
    overlay.classList.add("show");
    clearTimeout(el._t);
    el._t = setTimeout(hideToast, 4200);
  }}
  window.schedulixShowToast = showToast;
  window.schedulixHideToast = hideToast;

  (function initFlashToast() {{
    var overlay = document.getElementById("toast-overlay");
    if (overlay && overlay.classList.contains("show")) {{
      var el = document.getElementById("toast-card");
      if (el) el._t = setTimeout(hideToast, 4200);
    }}
  }})();

  // Wrapper for fetch requests to backend forms
  function schedulixFetch(form) {{
    return fetch(form.action, {{
      method: "POST",
      body: new FormData(form),
      headers: {{ "X-Requested-With": "Schedulix" }},
    }}).then(function (r) {{
      return r.json().then(function (data) {{ return {{ ok: r.ok, data: data }}; }});
    }});
  }}

  // ── Scroll position: keep .content scroll across reloads ──
  function scrollStorageKey() {{
    var u = new URL(window.location.href);
    u.searchParams.delete("scroll");
    u.searchParams.delete("aleph_page");
    u.searchParams.delete("bet_page");
    u.hash = "";
    return "schedulix:scroll:" + u.pathname + u.search;
  }}

  function saveContentScroll() {{
    var c = document.querySelector(".content");
    if (!c) return;
    try {{ sessionStorage.setItem(scrollStorageKey(), String(c.scrollTop)); }} catch (e) {{}}
  }}

  function restoreContentScroll(serverY) {{
    var c = document.querySelector(".content");
    if (!c) return;
    var y = serverY > 0 ? serverY : 0;
    if (y <= 0) {{
      try {{ y = parseInt(sessionStorage.getItem(scrollStorageKey()), 10) || 0; }} catch (e) {{}}
    }}
    if (y <= 0) return;
    function apply() {{ c.scrollTop = y; }}
    apply();
    requestAnimationFrame(apply);
    setTimeout(apply, 50);
    setTimeout(apply, 200);
  }}

  function injectScrollField(form) {{
    if (!form || form.classList.contains("program-toggle-form") ||
        form.classList.contains("generate-form") ||
        form.classList.contains("file-upload-form") ||
        form.classList.contains("history-restore-form") ||
        form.classList.contains("sort-form") ||
        form.classList.contains("reschedule-undo-form")) return;
    var c = document.querySelector(".content");
    if (!c) return;
    var inp = form.querySelector('input[name="scroll_y"]');
    if (!inp) {{
      inp = document.createElement("input");
      inp.type = "hidden";
      inp.name = "scroll_y";
      form.appendChild(inp);
    }}
    inp.value = c.scrollTop;
    saveContentScroll();
  }}

  var scrollSaveTimer = null;
  var contentEl = document.querySelector(".content");
  if (contentEl) {{
    contentEl.addEventListener("scroll", function () {{
      clearTimeout(scrollSaveTimer);
      scrollSaveTimer = setTimeout(saveContentScroll, 120);
    }}, {{ passive: true }});
  }}
  window.addEventListener("beforeunload", saveContentScroll);
  document.addEventListener("click", function (e) {{
    var a = e.target.closest("a[href]");
    if (!a || a.target === "_blank") return;
    try {{
      var dest = new URL(a.href, window.location.href);
      if (dest.origin === window.location.origin) saveContentScroll();
    }} catch (err) {{}}
  }}, true);
  document.addEventListener("submit", function (e) {{
    injectScrollField(e.target);
  }}, true);

  function applyOutputLive(data) {{
    if (data.output_top_bar_html) {{
      var top = document.getElementById("output-top-bar");
      if (top) top.innerHTML = data.output_top_bar_html;
    }}
    if (data.output_body_html) {{
      var body = document.getElementById("output-body");
      if (body) body.innerHTML = data.output_body_html;
    }}
    var exportBtn = document.querySelector(".export-bar .btn-primary");
    if (exportBtn) exportBtn.removeAttribute("disabled");
  }}
  window.schedulixApplyOutputLive = applyOutputLive;

  // Intercept program selection toggles (checkboxes/cards)
  function bindProgramToggles() {{
    document.querySelectorAll("form.program-toggle-form").forEach(function (form) {{
      if (form._schedulixBound) return;
      form._schedulixBound = true;
      form.addEventListener("submit", function (e) {{
        e.preventDefault();
        schedulixFetch(form)
          .then(function (res) {{
            if (!res.data.ok) {{
              showToast(res.data.error || "Could not update selection", "err");
              return;
            }}
            var countEl = document.getElementById("sel-count");
            if (countEl) countEl.textContent = res.data.count;
            var card = document.querySelector('.program-card[data-prog-id="' + res.data.prog_id + '"]');
            if (card) {{
              card.classList.toggle("selected", res.data.is_selected);
              var mark = card.querySelector(".checkmark");
              if (mark) mark.textContent = res.data.is_selected ? "\\u2713" : "";
            }}
          }})
          .catch(function () {{
            showToast("Could not update selection", "err");
          }});
      }});
    }});
  }}
  bindProgramToggles();

  // Custom file pickers — English labels instead of browser locale
  function bindFilePickers(root) {{
    (root || document).querySelectorAll(".file-picker-input").forEach(function (input) {{
      if (input._schedulixBound) return;
      input._schedulixBound = true;
      var nameEl = input.parentElement.querySelector(".file-picker-name");
      var placeholder = (nameEl && nameEl.dataset.placeholder) || "No file chosen";
      input.addEventListener("change", function () {{
        if (!nameEl) return;
        nameEl.textContent =
          input.files && input.files[0] ? input.files[0].name : placeholder;
      }});
    }});
  }}
  bindFilePickers();

  // Intercept the "Generate Schedules" form — start job and go to Output immediately
  document.querySelectorAll("form.generate-form").forEach(function (form) {{
    form.addEventListener("submit", function (e) {{
      e.preventDefault();
      var btn = form.querySelector("#generateBtn");
      if (btn) {{
        btn.disabled = true;
        btn.textContent = "Starting…";
      }}
      schedulixFetch(form)
        .then(function (res) {{
          if (!res.data.ok) {{
            showToast(res.data.error || "Generate failed", "err");
            if (btn) {{ btn.disabled = false; btn.textContent = "▶ Generate"; }}
            return;
          }}
          window.location.href = "/?screen=output&generating=1";
        }})
        .catch(function () {{
          showToast("Generate failed", "err");
          if (btn) {{ btn.disabled = false; btn.textContent = "▶ Generate"; }}
        }});
    }});
  }});

  // Intercept file upload forms — update status without full page reload
  document.querySelectorAll("form.file-upload-form").forEach(function (form) {{
    form.addEventListener("submit", function (e) {{
      e.preventDefault();
      var fileInput = form.querySelector(".file-picker-input");
      if (!fileInput || !fileInput.files || !fileInput.files.length) {{
        showToast("Choose a file first", "err");
        return;
      }}
      var historyEl = document.getElementById("gen-history-root");
      var resultEl = document.getElementById("gen-result");
      var outLink = document.getElementById("view-output-link");
      var hadGeneratedData =
        (historyEl && historyEl.innerHTML.trim()) ||
        (resultEl && resultEl.textContent.trim()) ||
        (outLink && outLink.style.display !== "none");
      if (hadGeneratedData) {{
        var ok = window.confirm(
          "Uploading a new file will delete generation history, all generated schedules, " +
          "and manual calendar edits. Continue?"
        );
        if (!ok) return;
      }}
      var statusEl = form.querySelector(".file-status");
      var btn = form.querySelector("button[type=submit]");
      if (btn) btn.disabled = true;
      fetch(form.action, {{
        method: "POST",
        body: new FormData(form),
        headers: {{ "X-Requested-With": "Schedulix" }},
      }})
        .then(function (r) {{ return r.json().then(function (data) {{ return {{ ok: r.ok, data: data }}; }}); }})
        .then(function (res) {{
          if (!res.data.ok) {{
            showToast(res.data.error || "Upload failed", "err");
            return;
          }}
          if (statusEl) {{
            statusEl.textContent = res.data.courses_status || res.data.periods_status || "";
            statusEl.className = "file-status ok";
          }}
          if (res.data.program_grid_html) {{
            var grid = document.querySelector(".program-grid");
            if (grid) grid.innerHTML = res.data.program_grid_html;
            bindProgramToggles();
          }}
          if (typeof res.data.sel_count === "number") {{
            var countEl = document.getElementById("sel-count");
            if (countEl) countEl.textContent = res.data.sel_count;
          }}
          if (res.data.history_html !== undefined) {{
            var historyEl = document.getElementById("gen-history-root");
            if (historyEl) historyEl.innerHTML = res.data.history_html;
          }}
          if (res.data.gen_result !== undefined) {{
            var resultEl = document.getElementById("gen-result");
            if (resultEl) resultEl.textContent = res.data.gen_result;
          }}
          var outLink = document.getElementById("view-output-link");
          if (outLink) outLink.style.display = "none";
          if (res.data.flash && res.data.flash.msg) {{
            showToast(res.data.flash.msg, res.data.flash.type || "ok");
          }}
          form.reset();
          var pickerName = form.querySelector(".file-picker-name");
          if (pickerName) pickerName.textContent = pickerName.dataset.placeholder || "No file chosen";
        }})
        .catch(function () {{ showToast("Upload failed", "err"); }})
        .finally(function () {{ if (btn) btn.disabled = false; }});
    }});
  }});

  // Logic to restore previous schedule generations
  function bindHistoryRestore(form) {{
    if (form._schedulixBound) return;
    form._schedulixBound = true;
    form.addEventListener("submit", function (e) {{
      e.preventDefault();
      schedulixFetch(form)
        .then(function (res) {{
          if (!res.data.ok) {{
            showToast(res.data.error || "Could not restore", "err");
            return;
          }}
          // Update history panel and selection UI dynamically
          var historyEl = document.getElementById("gen-history-root");
          if (historyEl) historyEl.innerHTML = res.data.history_html || "";
          var resultEl = document.getElementById("gen-result");
          if (resultEl) resultEl.textContent = res.data.gen_result || "";
          var outLink = document.getElementById("view-output-link");
          if (outLink) outLink.style.display = res.data.gen_result ? "inline-flex" : "none";
          if (typeof res.data.count === "number") {{
            var countEl = document.getElementById("sel-count");
            if (countEl) countEl.textContent = res.data.count;
          }}
          
          // Re-select the correct programs based on the restored state
          if (res.data.selected) {{
            var selectedSet = {{}};
            res.data.selected.forEach(function (id) {{ selectedSet[id] = true; }});
            document.querySelectorAll(".program-card[data-prog-id]").forEach(function (card) {{
              var id = card.getAttribute("data-prog-id");
              var on = !!selectedSet[id];
              card.classList.toggle("selected", on);
              var mark = card.querySelector(".checkmark");
              if (mark) mark.textContent = on ? "\\u2713" : "";
            }});
          }}
          if (res.data.flash && res.data.flash.msg) {{
            showToast(res.data.flash.msg, res.data.flash.type || "ok");
          }}
          document.querySelectorAll("form.history-restore-form").forEach(bindHistoryRestore);
        }})
        .catch(function () {{
          showToast("Could not restore", "err");
        }});
    }});
  }}
  document.querySelectorAll("form.history-restore-form").forEach(bindHistoryRestore);

  // Output screen — poll while generation runs; update calendars and counts live
  (function outputGenerationPoll() {{
    var params = new URLSearchParams(window.location.search);
    if (params.get("screen") !== "output") return;
    var genBar = document.getElementById("gen-progress-bar");
    var shouldPoll = params.get("generating") === "1" ||
      (genBar && genBar.getAttribute("data-active") === "1");
    if (!shouldPoll) return;

    function applyLiveOutput(data) {{
      if (data.gen_progress_html) {{
        var bar = document.getElementById("gen-progress-bar");
        if (bar) bar.outerHTML = data.gen_progress_html;
      }}
      applyOutputLive(data);
      var exportBtn = document.querySelector(".export-bar .btn-primary");
      if (exportBtn && (data.aleph_count || data.bet_count)) {{
        exportBtn.removeAttribute("disabled");
      }}
    }}

    function poll() {{
      fetch("/generate/status", {{ headers: {{ "X-Requested-With": "Schedulix" }} }})
        .then(function (r) {{ return r.json(); }})
        .then(function (data) {{
          applyLiveOutput(data);
          if (data.running) {{
            setTimeout(poll, 300);
            return;
          }}
          if (params.get("generating") === "1") {{
            var clean = new URL(window.location.href);
            clean.searchParams.delete("generating");
            window.history.replaceState({{}}, "", clean.pathname + clean.search);
          }}
          if (data.error) {{
            showToast(data.error, "err");
          }} else if (data.flash && data.flash.msg) {{
            showToast(data.flash.msg, data.flash.type || "ok");
          }}
        }})
        .catch(function () {{ setTimeout(poll, 500); }});
    }}
    poll();
  }})();

  // Restore scroll position after reload
  restoreContentScroll({scroll_y});
  var content = document.querySelector(".content");
  if (content && !{scroll_y}) {{
    var id = location.hash;
    if (id) {{
      var el = document.querySelector(id);
      if (el) el.scrollIntoView({{ block: "start", behavior: "instant" }});
    }}
  }}

  // Sort + undo on Output — AJAX so scroll is not lost
  document.querySelectorAll("form.sort-form").forEach(function (form) {{
    form.addEventListener("submit", function (e) {{
      e.preventDefault();
      schedulixFetch(form).then(function (res) {{
        if (!res.data.ok) {{ showToast(res.data.error || "Sort failed", "err"); return; }}
        applyOutputLive(res.data);
        if (res.data.flash && res.data.flash.msg) showToast(res.data.flash.msg, res.data.flash.type || "ok");
      }}).catch(function () {{ showToast("Sort failed", "err"); }});
    }});
  }});
  document.querySelectorAll("form.reschedule-undo-form").forEach(function (form) {{
    form.addEventListener("submit", function (e) {{
      e.preventDefault();
      schedulixFetch(form).then(function (res) {{
        if (!res.data.ok) {{ showToast(res.data.error || "Nothing to undo", "err"); return; }}
        applyOutputLive(res.data);
        var btn = form.querySelector("button");
        if (btn && typeof res.data.remaining === "number") {{
          btn.disabled = res.data.remaining <= 0;
          btn.textContent = res.data.remaining > 0 ? "\u21b6 Undo (" + res.data.remaining + ")" : "\u21b6 Undo";
        }}
        if (res.data.flash && res.data.flash.msg) showToast(res.data.flash.msg, res.data.flash.type || "ok");
      }}).catch(function () {{ showToast("Undo failed", "err"); }});
    }});
  }});
}})();
  // Course detail modal
  (function() {{
    var overlay = document.createElement('div');
    overlay.id = 'course-modal-overlay';
    overlay.className = 'modal-overlay';
    overlay.innerHTML = [
      '<div id="course-modal" class="course-modal-panel">',
      '<button type="button" class="course-modal-close" onclick="hideCourseModal()">\\u2715</button>',
      '<div id="cm-badge" class="course-modal-badge"></div>',
      '<div id="cm-name" class="course-modal-name"></div>',
      '<div id="cm-id" class="course-modal-id"></div>',
      '<table class="course-modal-table">',
      '<tr><td class="label">Instructor</td><td id="cm-instructor" class="value"></td></tr>',
      '<tr><td class="label">Requirement</td><td id="cm-req" class="value"></td></tr>',
      '<tr><td class="label">Programs</td><td id="cm-programs" class="value"></td></tr>',
      '<tr><td class="label">Exam Date</td><td id="cm-date" class="value" style="font-family:var(--mono);font-weight:400;"></td></tr>',
      '<tr><td class="label">Moed</td><td id="cm-moed" class="value"></td></tr>',
      '</table></div>'
    ].join('');
    document.body.appendChild(overlay);
    overlay.addEventListener('click', function(e) {{ if (e.target === overlay) hideCourseModal(); }});
  }})();

  function showCourseModal(el) {{
    var d = el.dataset;
    var isAleph = d.moed === 'aleph';
    var reqColor = d.requirement === 'Obligatory' ? 'var(--aleph-color)' : 'var(--bet-color)';
    var moodColor = isAleph ? 'var(--aleph-color)' : 'var(--bet-color)';
    document.getElementById('cm-badge').style.color = moodColor;
    document.getElementById('cm-badge').textContent = isAleph ? '\u2666 MOED ALEPH' : '\u2666 MOED BET';
    document.getElementById('cm-name').textContent = d.courseName;
    document.getElementById('cm-id').textContent = d.courseId;
    document.getElementById('cm-instructor').textContent = d.instructor;
    document.getElementById('cm-req').textContent = d.requirement;
    document.getElementById('cm-req').style.color = reqColor;
    document.getElementById('cm-programs').textContent = d.programs || '\u2014';
    document.getElementById('cm-date').textContent = d.date;
    document.getElementById('cm-moed').textContent = isAleph ? 'Aleph' : 'Bet';
    document.getElementById('cm-moed').style.color = moodColor;
    document.getElementById('course-modal-overlay').classList.add('is-open');
  }}

  function hideCourseModal() {{
    document.getElementById('course-modal-overlay').classList.remove('is-open');
  }}

  // ===== Exam reschedule drag & drop =====
  var rscDrag_ = null;     // the exam currently being dragged
  var rscPending_ = null;  // the move awaiting Apply
  var rscHoverCell_ = null;
  var rscCheckTimer_ = null;
  var rscCheckCache_ = {{}};
  var rscCheckSeq_ = 0;

  function rscClearDropHints() {{
    document.querySelectorAll(
      '.out-cal-day.rsc-drop-ok, .out-cal-day.rsc-drop-bad, .out-cal-day.rsc-drop-pending'
    ).forEach(function (el) {{
      el.classList.remove('rsc-drop-ok', 'rsc-drop-bad', 'rsc-drop-pending');
    }});
  }}

  function rscDragEnd() {{
    rscDrag_ = null;
    rscHoverCell_ = null;
    rscCheckCache_ = {{}};
    clearTimeout(rscCheckTimer_);
    rscClearDropHints();
  }}

  function rscToast(msg, type) {{
    if (window.schedulixShowToast) window.schedulixShowToast(msg, type);
  }}

  function rscDrag(e) {{
    var d = e.target.dataset;
    if (d.locked === '1') {{ e.preventDefault(); rscToast('Exam is locked', 'err'); return; }}
    rscDrag_ = {{ course_id: d.courseId, moed: d.moed, from_date: d.date }};
    rscCheckCache_ = {{}};
    try {{ e.dataTransfer.setData('text/plain', d.courseId); }} catch (err) {{}}
    e.dataTransfer.effectAllowed = 'move';
  }}

  function rscDragEndEvent() {{ rscDragEnd(); }}

  function rscInstantDropClass(cell) {{
    if (!rscDrag_) return null;
    if (cell.moed !== rscDrag_.moed) return 'bad';
    if (cell.date === rscDrag_.from_date) return null;
    return 'pending';
  }}

  function rscValidateDropCell(el, cell) {{
    var cacheKey = rscDrag_.course_id + '|' + rscDrag_.from_date + '|' + cell.date;
    if (rscCheckCache_[cacheKey] !== undefined) {{
      el.classList.remove('rsc-drop-pending');
      el.classList.add(rscCheckCache_[cacheKey] ? 'rsc-drop-ok' : 'rsc-drop-bad');
      return;
    }}
    clearTimeout(rscCheckTimer_);
    var seq = ++rscCheckSeq_;
    rscCheckTimer_ = setTimeout(function () {{
      if (rscHoverCell_ !== el || !rscDrag_) return;
      rscPost('/reschedule/resolve', {{
        moed: rscDrag_.moed,
        course_id: rscDrag_.course_id,
        new_date: cell.date,
      }}).then(function (data) {{
        if (rscHoverCell_ !== el || seq !== rscCheckSeq_) return;
        var ok = !!(data.ok && data.solved);
        rscCheckCache_[cacheKey] = ok;
        el.classList.remove('rsc-drop-pending');
        el.classList.add(ok ? 'rsc-drop-ok' : 'rsc-drop-bad');
      }}).catch(function () {{
        if (rscHoverCell_ !== el) return;
        rscCheckCache_[cacheKey] = false;
        el.classList.remove('rsc-drop-pending');
        el.classList.add('rsc-drop-bad');
      }});
    }}, 100);
  }}

  function rscToggleLock(e, btn) {{
    e.stopPropagation();
    var block = btn.parentNode;
    var d = block.dataset;
    rscPost('/reschedule/lock', {{ moed: d.moed, course_id: d.courseId }}).then(function (data) {{
      if (!data.ok) {{ rscToast(data.error || 'Lock failed', 'err'); return; }}
      d.locked = data.locked ? '1' : '0';
      block.classList.toggle('locked', data.locked);
      block.setAttribute('draggable', data.locked ? 'false' : 'true');
      btn.textContent = data.locked ? '🔒' : '🔓';
      rscToast(data.locked ? 'Exam locked' : 'Exam unlocked', 'ok');
    }}).catch(function () {{ rscToast('Lock failed', 'err'); }});
  }}

  function rscOver(e) {{
    e.preventDefault();
    if (!rscDrag_) return;
    var el = e.currentTarget;
    var cell = el.dataset;
    e.dataTransfer.dropEffect = cell.moed === rscDrag_.moed ? 'move' : 'none';

    if (rscHoverCell_ === el) return;
    rscHoverCell_ = el;
    rscClearDropHints();

    var instant = rscInstantDropClass(cell);
    if (instant === 'bad') {{
      el.classList.add('rsc-drop-bad');
      return;
    }}
    if (instant === null) return;

    el.classList.add('rsc-drop-pending');
    rscValidateDropCell(el, cell);
  }}

  function rscLeave(e) {{
    var el = e.currentTarget;
    var rel = e.relatedTarget;
    if (rel && el.contains(rel)) return;
    el.classList.remove('rsc-drop-ok', 'rsc-drop-bad', 'rsc-drop-pending');
    if (rscHoverCell_ === el) rscHoverCell_ = null;
  }}

  function rscPost(url, params) {{
    return fetch(url, {{
      method: 'POST',
      headers: {{
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-Requested-With': 'Schedulix'
      }},
      body: new URLSearchParams(params).toString()
    }}).then(function (r) {{ return r.json(); }});
  }}

  function rscDrop(e) {{
    e.preventDefault();
    rscClearDropHints();
    rscHoverCell_ = null;
    var cell = e.currentTarget.dataset;
    if (!rscDrag_) return;
    if (cell.moed !== rscDrag_.moed) {{ rscToast('Drag within the same moed', 'err'); return; }}
    if (cell.date === rscDrag_.from_date) {{ rscDrag_ = null; return; }}
    var params = {{ moed: rscDrag_.moed, course_id: rscDrag_.course_id, new_date: cell.date }};
    rscPending_ = params;
    rscPost('/reschedule/resolve', params).then(function (data) {{
      if (!data.ok) {{ rscShowError(data.error || 'This move is not allowed.'); return; }}
      rscShow(data);
    }}).catch(function () {{ rscToast('Reschedule preview failed', 'err'); }});
    rscDrag_ = null;
  }}

  function rscList(items, empty, cls) {{
    if (!items || !items.length) return '<div class="rsc-empty">' + empty + '</div>';
    return items.map(function (v) {{
      return '<div class="rsc-item ' + (cls || '') + '">' + v.message + '</div>';
    }}).join('');
  }}

  function rscShow(data) {{
    var b = data.before || {{}};
    var plan = data.plan || [];
    var planHtml;
    if (b.legal) {{
      planHtml = '<div class="rsc-ok">This move is already legal — no cascade needed.</div>';
    }} else if (data.solved) {{
      planHtml = plan.map(function (m, i) {{
        return '<div class="rsc-move">' + (i + 1) + '. Move <strong>' + m.course_name +
               '</strong>: ' + m.from_date + ' \\u2192 ' + m.to_date + '</div>';
      }}).join('');
      if (!plan.length) planHtml = '<div class="rsc-ok">Legal — no cascade needed.</div>';
    }} else {{
      planHtml = '<div class="rsc-bad">No legal fix found within the move/time limit.</div>';
    }}
    document.getElementById('rsc-sub').textContent =
      'Move ' + rscPending_.course_id + ' \\u2192 ' + rscPending_.new_date + '  (Moed ' + rscPending_.moed + ')';
    document.getElementById('rsc-violations').innerHTML = rscList(b.violations, 'None \\uD83C\\uDF89', 'bad');
    document.getElementById('rsc-collisions').innerHTML = rscList(b.collisions, 'None', 'warn');
    document.getElementById('rsc-plan').innerHTML = planHtml;
    var applyBtn = document.getElementById('rsc-apply');
    applyBtn.textContent = (data.solved && !b.legal && plan.length) ? 'Apply move + cascade' : 'Apply move';
    document.getElementById('rsc-body-normal').style.display = 'block';
    document.getElementById('rsc-body-error').style.display = 'none';
    applyBtn.style.display = 'inline-flex';
    document.getElementById('rsc-overlay').classList.add('is-open');
  }}

  function rscShowError(message) {{
    document.getElementById('rsc-sub').textContent =
      'Move ' + (rscPending_ ? rscPending_.course_id + ' \\u2192 ' + rscPending_.new_date +
      '  (Moed ' + rscPending_.moed + ')' : '');
    document.getElementById('rsc-error').innerHTML =
      '<div class="rsc-item bad">\\uD83D\\uDCC5 ' + message + '</div>' +
      '<div class="rsc-empty">Exams can only be placed on available dates inside the exam period. ' +
      'Drop the exam on a valid day to preview how the move affects the schedule.</div>';
    document.getElementById('rsc-body-normal').style.display = 'none';
    document.getElementById('rsc-body-error').style.display = 'block';
    document.getElementById('rsc-apply').style.display = 'none';
    document.getElementById('rsc-overlay').classList.add('is-open');
  }}

  function rscHide() {{
    document.getElementById('rsc-overlay').classList.remove('is-open');
  }}

  function rscApply() {{
    if (!rscPending_) return;
    rscPost('/reschedule/apply', rscPending_).then(function (data) {{
      if (!data.ok) {{ rscToast(data.error || 'Apply failed', 'err'); return; }}
      rscHide();
      rscPending_ = null;
      if (window.schedulixApplyOutputLive) window.schedulixApplyOutputLive(data);
      var undoBtn = document.querySelector('form.reschedule-undo-form button');
      if (undoBtn) {{
        undoBtn.disabled = false;
        undoBtn.textContent = '\u21b6 Undo';
      }}
      if (data.flash && data.flash.msg) rscToast(data.flash.msg, data.flash.type || 'ok');
    }}).catch(function () {{ rscToast('Apply failed', 'err'); }});
  }}

  (function () {{
    var o = document.createElement('div');
    o.id = 'rsc-overlay';
    o.className = 'modal-overlay';
    o.innerHTML = [
      '<div class="rsc-modal">',
      '<button class="rsc-close" onclick="rscHide()">\\u2715</button>',
      '<div class="rsc-title">\\u26A1 Exam Reschedule</div>',
      '<div id="rsc-sub" class="rsc-subtitle"></div>',
      '<div id="rsc-body-normal">',
      '<div class="rsc-section-title">Baseline requirements violated</div>',
      '<div id="rsc-violations"></div>',
      '<div class="rsc-section-title">Elective courses now colliding</div>',
      '<div id="rsc-collisions"></div>',
      '<div class="rsc-section-title">Minimal cascade to restore a legal schedule</div>',
      '<div id="rsc-plan"></div>',
      '</div>',
      '<div id="rsc-body-error" style="display:none;">',
      '<div class="rsc-section-title">Move not allowed</div>',
      '<div id="rsc-error"></div>',
      '</div>',
      '<div class="rsc-actions">',
      '<button class="btn btn-green" id="rsc-apply" onclick="rscApply()">Apply</button>',
      '<button class="btn btn-secondary" onclick="rscHide()">Cancel</button>',
      '</div></div>'
    ].join('');
    document.body.appendChild(o);
    o.addEventListener('click', function (e) {{ if (e.target === o) rscHide(); }});
  }})();
</script>
</body>
</html>"""


# ==========================================
# SCREEN: INPUT (File upload & Program selection)
# ==========================================

def _render_input(ctx: dict) -> str:
    """
    Renders the 'Input' screen.
    Includes file upload forms (overwrite/append modes), the program selection grid,
    the drilldown view (if a specific program is clicked), and the generate button.
    """
    # Determine the current file loading mode (overwrite existing data vs append to it)
    file_mode = ctx.get("file_mode", "overwrite")
    ow_cls = "active" if file_mode == "overwrite" else ""
    ap_cls = "active" if file_mode == "append" else ""

    # Status labels indicating if courses/periods data files have been loaded
    cs = ctx.get("courses_status", "Not loaded")
    ps = ctx.get("periods_status", "Not loaded")
    cs_cls = "ok" if ctx.get("courses_count", 0) > 0 else "none"
    ps_cls = "ok" if ctx.get("periods_count", 0) > 0 else "none"

    # Render sub-components
    programs_html = _render_program_grid(ctx)
    drilldown_html = _render_drilldown(ctx) if ctx.get("drilldown") else ""
    
    # Render generation results and history
    gen_result = ctx.get("generate_result", "")
    history_html = _render_gen_history(ctx)
    view_out_style = "display:inline-flex" if gen_result else "display:none"
    view_output_link = (
        f'<a class="btn btn-ghost" id="view-output-link" href="{_url("output")}" '
        f'style="margin-left:10px; font-size:12px; {view_out_style}">View schedules →</a>'
    )

    return f"""
<div class="screen active">
  <div class="card" id="file-loading">
    <div class="card-title">📂 File Loading</div>
    <p class="file-upload-notice">
      Uploading a <strong>courses</strong> or <strong>dates</strong> file (overwrite or append)
      clears <strong>generation history</strong>, generated schedules, and any manual calendar edits.
      You will need to select programs and click Generate again.
    </p>
    
    <form method="post" action="/set_mode" style="margin-bottom:14px;">
      <div style="font-size:12px; color:var(--muted); margin-bottom:8px;">Load Mode</div>
      <div class="mode-toggle">
        <button type="submit" name="mode" value="overwrite" class="mode-btn {ow_cls}">Overwrite</button>
        <button type="submit" name="mode" value="append" class="mode-btn {ap_cls}">Append</button>
      </div>
    </form>
    
    <form method="post" action="/upload/courses" enctype="multipart/form-data" class="file-row file-upload-form">
      <input type="hidden" name="mode" value="{_e(file_mode)}"/>
      <span class="file-label">Courses File</span>
      {_render_file_picker("courses-file-input")}
      <button type="submit" class="btn btn-secondary">📂 Upload</button>
      <span class="file-status {cs_cls}">{_e(cs)}</span>
    </form>
    
    <form method="post" action="/upload/periods" enctype="multipart/form-data" class="file-row file-upload-form">
      <input type="hidden" name="mode" value="{_e(file_mode)}"/>
      <span class="file-label">Dates File</span>
      {_render_file_picker("periods-file-input")}
      <button type="submit" class="btn btn-secondary">📂 Upload</button>
      <span class="file-status {ps_cls}">{_e(ps)}</span>
    </form>
  </div>

  <div class="card" id="program-selection">
    <div class="card-title">🎓 Study Program Selection</div>
    <div class="selection-count">Selected: <span id="sel-count">{len(ctx.get('selected_programs', []))}</span> / 5</div>
    <div class="program-grid">{programs_html}</div>
  </div>
  
  {drilldown_html}
  
  <div class="card" id="generate-schedules">
    <div class="card-title">⚙️ Generate Schedules</div>
    <p style="color:var(--muted); font-size:13px; margin-bottom:14px;">
      <strong>Generate</strong> runs the backtracking scheduler on your loaded courses and exam dates.
      It finds every valid timetable for the selected programs (up to 5), separately for
      Moed Aleph <strong style="color:var(--aleph-color)">✦</strong> and Moed Bet
      <strong style="color:var(--bet-color)">✦</strong>.
      Results appear live on the Output screen. Change programs, calendar dates, or settings first — then click Generate again.
    </p>
    <form method="post" action="/generate" class="generate-form" style="display:inline;">
      <button type="submit" class="btn btn-green" id="generateBtn">▶ Generate</button>
    </form>
    <span id="gen-result" style="margin-left:12px; font-family:var(--mono); font-size:12px; color:var(--muted);">{_e(gen_result)}</span>
    {view_output_link}
    <div id="gen-history-root">{history_html}</div>
  </div>
</div>"""


def _render_program_grid(ctx: dict) -> str:
    """
    Renders the grid of study programs (e.g., Software Engineering, Data Engineering).
    Provides clickable cards to toggle selection for the scheduler algorithm.
    """
    if not ctx.get("courses_count", 0):
        # Empty state if no courses are uploaded yet
        return '<div class="empty-state"><div class="icon">📭</div>Load a courses file first</div>'
        
    selected = set(ctx.get("selected_programs", []))
    programs = ctx.get("programs", [])
    if not programs:
        return '<div class="empty-state"><div class="icon">📭</div>No programs found in data</div>'
        
    parts = []
    # Loop through each program and create a card
    for p in programs:
        pid, name = p["id"], p["name"]
        sel = " selected" if pid in selected else ""
        mark = "✓" if pid in selected else ""
        
        # Each card contains a form to submit the toggle action
        parts.append(f"""
<div class="program-card{sel}" data-prog-id="{_e(pid)}">
  <form method="post" action="/programs/toggle" class="program-card-form program-toggle-form">
    <input type="hidden" name="prog_id" value="{_e(pid)}"/>
    <button type="submit" class="program-card-hit" aria-label="Toggle program {_e(pid)}">
      <span class="checkmark">{mark}</span>
      <span class="program-card-text">
        <span class="pid">{_e(pid)}</span>
        <span class="pname">{_e(name)}</span>
      </span>
    </button>
  </form>
  <a class="btn btn-ghost program-view-link" href="{_url('input', drilldown=pid)}">View courses →</a>
</div>""")
    return "".join(parts)


def _render_drilldown(ctx: dict) -> str:
    """
    Renders the detailed table of courses for a specific selected program.
    Includes filtering options by Year and Semester.
    """
    d = ctx["drilldown"]
    pid, name = d["prog_id"], d["name"]
    year = d.get("year_filter", "")
    sem = d.get("sem_filter", "")
    courses = d.get("courses", [])

    rows = ""
    if courses:
        # Generate table rows for each course
        for c in courses:
            req = c["requirement"].lower()
            ev = c["evaluation"].lower()
            rows += f"""<tr>
              <td style="font-family:var(--mono); font-size:11px; color:var(--muted);">{_e(c['course_id'])}</td>
              <td>{_e(c['name'])}</td>
              <td style="color:var(--muted);">{_e(c['instructor'])}</td>
              <td style="font-family:var(--mono);">{_e(c['year'])}</td>
              <td style="font-family:var(--mono); font-size:11px;">{_e(c['semester'])}</td>
              <td><span class="badge badge-{req}">{_e(c['requirement'])}</span></td>
              <td><span class="badge badge-{ev}">{_e(c['evaluation'])}</span></td>
            </tr>"""
            
        table = f"""<table class="course-table">
          <thead><tr>
            <th>ID</th><th>Course Name</th><th>Instructor</th>
            <th>Year</th><th>Sem</th><th>Requirement</th><th>Evaluation</th>
          </tr></thead><tbody>{rows}</tbody></table>"""
    else:
        table = '<div class="empty-state">No courses match the filters.</div>'

    # Filter row to apply Year/Semester parameters
    return f"""
<div class="card">
  <div style="display:flex; align-items:center; gap:10px; margin-bottom:14px;">
    <a class="btn btn-ghost" href="{_url('input')}">← Back</a>
    <div class="card-title" style="margin:0;">{_e(pid)} — {_e(name)}</div>
  </div>
  <form method="get" action="/" class="filter-row">
    <input type="hidden" name="screen" value="input"/>
    <input type="hidden" name="drilldown" value="{_e(pid)}"/>
    
    <select class="filter" name="year">
      <option value="" {"selected" if not year else ""}>All Years</option>
      {"".join(f'<option value="{y}" {"selected" if str(y)==str(year) else ""}>Year {y}</option>' for y in range(1,5))}
    </select>
    
    <select class="filter" name="semester">
      <option value="" {"selected" if not sem else ""}>All Semesters</option>
      <option value="FALL" {"selected" if sem=="FALL" else ""}>FALL</option>
      <option value="SPRI" {"selected" if sem=="SPRI" else ""}>SPRING</option>
      <option value="SUMM" {"selected" if sem=="SUMM" else ""}>SUMMER</option>
    </select>
    <button type="submit" class="btn btn-secondary">Apply</button>
  </form>
  {table}
</div>"""


def format_generate_result(aleph_count: int, bet_count: int) -> str:
    """Formats a simple text string indicating how many schedules were successfully generated."""
    if aleph_count or bet_count:
        return f"✓ {aleph_count} Aleph · {bet_count} Bet schedules"
    return ""


def render_program_grid_html(ctx: dict) -> str:
    """Render only the program grid (for AJAX refresh after file upload)."""
    return _render_program_grid(ctx)


def render_gen_history_html(history: list) -> str:
    """Wrapper function to render the history list outside the main flow (used by JS)."""
    return _render_gen_history({"gen_history": history})


def _render_gen_history(ctx: dict) -> str:
    """
    Renders a list showing the recent scheduling algorithm runs (history).
    Allows the user to restore a previous run if they want to roll back their selection.
    """
    history = ctx.get("gen_history", [])
    if not history:
        return ""
        
    items = []
    # Loop through the history backwards (newest first)
    for i, h in enumerate(reversed(history)):
        idx = h.get("_index", len(history) - 1 - i)
        is_current = i == 0
        ts = h.get("ts")
        time_str = ts.strftime("%H:%M") if ts else ""
        date_str = ts.strftime("%b %d") if ts else ""
        prog_str = ", ".join(h.get("programs", [])) or "—"
        
        # Indicator if the backtracking algorithm hit a time limit and returned partial results
        partial = ' <span style="color:var(--yellow)">(partial)</span>' if h.get("timed_out") else ""
        
        # Current state has a badge; older states have a 'Restore' button
        restore = (
            '<span class="gen-history-badge">current</span>'
            if is_current
            else f'<form method="post" action="/history/restore" class="history-restore-form" style="display:inline;">'
                 f'<input type="hidden" name="index" value="{idx}"/>'
                 f'<button type="submit" class="btn btn-secondary" style="font-size:11px; padding:4px 10px;">↩ Restore</button></form>'
        )
        
        items.append(f"""
<div class="gen-history-item {"is-current" if is_current else ""}">
  <div class="gen-history-slot">#{idx + 1}</div>
  <div class="gen-history-meta">
    <div class="gen-history-counts">
      <span class="a">{h.get('aleph_count', 0)} Aleph</span>
      <span style="color:var(--muted)"> · </span>
      <span class="b">{h.get('bet_count', 0)} Bet</span>{partial}
    </div>
    <div class="gen-history-detail">Programs: {_e(prog_str)}</div>
  </div>
  <div class="gen-history-time">{_e(date_str)} {_e(time_str)}</div>
  {restore}
</div>""")

    return f"""
<div class="gen-history-wrap" style="display:block; margin-top:14px;">
  <hr class="divider"/>
  <div class="gen-history-title">📋 Generation history (last 2)</div>
  <p style="color:var(--muted); font-size:11px; margin:6px 0 10px;">
    Restore rolls back programs, calendar overrides, and schedules from a prior run.
    Only entries matching the currently loaded files are shown.
  </p>
  <div class="gen-history-list">{"".join(items)}</div>
</div>"""


# ==========================================
# SCREEN: SETTINGS (Configurable Hard Constraints)
# ==========================================

def _render_settings(ctx: dict) -> str:
    """
    Renders the 'Settings' screen where the user enables/disables each of the
    five hard constraints and sets their individual integer parameter k.

    Every constraint is a hard constraint: when enabled, any generated schedule
    that violates it is immediately disqualified by the scheduler.
    """
    constraints = ctx.get("constraints", {})

    cards = []
    for meta in CONSTRAINT_META:
        key = meta["key"]
        cfg = constraints.get(key, {})
        enabled = bool(cfg.get("enabled", False))
        k_val = cfg.get("k", meta["min_k"])
        checked = "checked" if enabled else ""
        on_cls = " on" if enabled else ""

        cards.append(f"""
<div class="constraint-row{on_cls}">
  <label class="switch">
    <input type="checkbox" name="{_e(key)}_enabled" value="1" {checked}/>
    <span class="switch-slider"></span>
  </label>
  <div class="constraint-info">
    <div class="constraint-name">{_e(meta['label'])}</div>
    <div class="constraint-desc">{_e(meta['desc'])}</div>
  </div>
  <div class="constraint-k">
    <label for="{_e(key)}_k">{_e(meta['k_label'])}</label>
    <input id="{_e(key)}_k" class="shift-input" type="number" name="{_e(key)}_k"
           value="{_e(k_val)}" min="{meta['min_k']}" step="1"/>
  </div>
</div>""")

    return f"""
<div class="screen active">
  <div class="card">
    <div class="card-title">⚙️ Scheduling Hard Constraints</div>
    <p style="color:var(--muted); font-size:13px; margin-bottom:16px;">
      Each constraint below is a <strong>hard constraint</strong>: when enabled, any
      generated schedule that violates it is dropped. Day differences count calendar
      days (weekends and holidays included). Re-run <em>Generate</em> after changing these.
    </p>
    <form method="post" action="/settings">
      <div class="constraint-list">
        {"".join(cards)}
      </div>
      <div style="margin-top:18px;">
        <button type="submit" class="btn btn-green">💾 Save Settings</button>
      </div>
    </form>
  </div>
</div>"""


# ==========================================
# SCREEN: CALENDAR (Moed Aleph & Bet Setup)
# ==========================================

def _render_custom_event_form(ctx: dict) -> str:
    """
    Renders the custom holiday/event exclusion tool: a name, a single date or a
    date range, and the target moed(s). Applying it blocks those dates exactly
    like a weekend or a holiday preset.
    """
    events = ctx.get("custom_events", [])
    chips = ""
    if events:
        rows = ""
        for ev in events:
            span = ev["start"] + (f" → {ev['end']}" if ev.get("end") else "")
            targets = "·".join(
                t for t, on in (("A", ev.get("aleph")), ("B", ev.get("bet"))) if on
            )
            rows += (
                '<span class="ce-chip">'
                f'<strong>{_e(ev["name"])}</strong> '
                f'<span class="ce-chip-span">{_e(span)}</span> '
                f'<span class="ce-chip-moed">[{_e(targets)}]</span> '
                f'<span class="ce-chip-count">−{ev.get("excluded", 0)}d</span>'
                '</span>'
            )
        chips = f'<div class="ce-list">{rows}</div>'

    return f"""
<div class="custom-event-bar">
  <span class="preset-bar-label">🛠 Custom event exclusion</span>
  <form method="post" action="/calendar/custom_event" class="custom-event-form">
    <input class="ce-input" type="text" name="event_name" placeholder="Event name" />
    <label class="ce-field">From <input class="ce-input" type="date" name="start_date" required/></label>
    <label class="ce-field">To <input class="ce-input" type="date" name="end_date" placeholder="(optional)"/></label>
    <label class="ce-check"><input type="checkbox" name="target_aleph" value="1" checked/> Aleph</label>
    <label class="ce-check"><input type="checkbox" name="target_bet" value="1" checked/> Bet</label>
    <button type="submit" class="btn btn-secondary">Apply</button>
  </form>
  {chips}
</div>"""


def _render_calendar(ctx: dict) -> str:
    """
    Renders the 'Calendar' configuration screen.
    This UI allows users to visually configure which days are available for exams.
    Displays two parallel panels: one for Moed Aleph and one for Moed Bet.
    """
    aleph = ctx.get("aleph_periods", [])
    bet = ctx.get("bet_periods", [])
    
    # Track which semester tab is currently active
    active_a = min(ctx.get("active_aleph", 0), max(0, len(aleph) - 1))
    active_b = min(ctx.get("active_bet", 0), max(0, len(bet) - 1))
    
    # State flags to know which Moed the Holiday Presets apply to
    pt_a = ctx.get("preset_target_aleph", True)
    pt_b = ctx.get("preset_target_bet", True)

    # Render buttons for predefined holidays (Rosh Hashana, Sukkot, etc.)
    preset_btns = ""
    for key, preset in HOLIDAY_PRESETS.items():
        preset_btns += f"""
<form method="post" action="/calendar/preset" style="display:inline;">
  <input type="hidden" name="preset" value="{_e(key)}"/>
  <input type="hidden" name="target_aleph" value="{'1' if pt_a else '0'}"/>
  <input type="hidden" name="target_bet" value="{'1' if pt_b else '0'}"/>
  <button type="submit" class="preset-btn">{_e(preset['label'])}</button>
</form>"""

    aleph_on = " on" if pt_a else ""
    bet_on = " on" if pt_b else ""

    custom_event_form = _render_custom_event_form(ctx)

    # Generate the calendar grids
    aleph_panel = _render_moed_panel("aleph", aleph, active_a, ctx) if aleph else (
        '<div class="empty-state" style="padding:20px; color:var(--muted); font-size:12px;">No Moed Aleph periods found</div>'
    )
    bet_panel = _render_moed_panel("bet", bet, active_b, ctx) if bet else (
        '<div class="empty-state" style="padding:20px; color:var(--muted); font-size:12px;">No Moed Bet periods found</div>'
    )

    return f"""
<div class="screen active">
  <div style="font-size:13px; color:var(--muted); margin-bottom:12px;">
    Configure available exam dates for each moed independently. Click any date to toggle it.
  </div>
  
  <div class="preset-bar">
    <span class="preset-bar-label">🗓 Holiday presets</span>
    {preset_btns}
    
    <div class="preset-target">
      <span style="font-size:10px; color:var(--muted); font-family:var(--mono); align-self:center;">apply to:</span>
      <form method="post" action="/calendar/preset_target" style="display:inline;">
        <input type="hidden" name="moed" value="aleph"/>
        <input type="hidden" name="target_aleph" value="{'0' if pt_a else '1'}"/>
        <input type="hidden" name="target_bet" value="{'1' if pt_b else '0'}"/>
        <button type="submit" class="preset-target-btn aleph-t{aleph_on}">Aleph</button>
      </form>
      <form method="post" action="/calendar/preset_target" style="display:inline;">
        <input type="hidden" name="moed" value="bet"/>
        <input type="hidden" name="target_aleph" value="{'1' if pt_a else '0'}"/>
        <input type="hidden" name="target_bet" value="{'0' if pt_b else '1'}"/>
        <button type="submit" class="preset-target-btn bet-t{bet_on}">Bet</button>
      </form>
    </div>
  </div>

  {custom_event_form}

  <div class="dual-cal-layout">
    <div class="moed-panel aleph">
      <div class="moed-header">
        <span class="moed-badge aleph">MOED ALEPH</span>
        <span style="font-size:12px; color:var(--muted);">Aleph session</span>
      </div>
      {aleph_panel}
    </div>
    <div class="moed-panel bet">
      <div class="moed-header">
        <span class="moed-badge bet">MOED BET</span>
        <span style="font-size:12px; color:var(--muted);">Bet session</span>
      </div>
      {bet_panel}
    </div>
  </div>
</div>"""


def _render_moed_panel(moed_key: str, periods: list, active: int, ctx: dict) -> str:
    """
    Renders the panel for a single Moed (either Aleph or Bet).
    Contains semester tabs, 'shift' controls (to globally push start/end dates),
    and the actual visual calendar grid.
    """
    period = periods[active]
    
    # Create tabs for navigating between different semesters (e.g. Fall, Spring)
    tabs = ""
    for i, p in enumerate(periods):
        cls = f" active-{moed_key}" if i == active else ""
        cal_params = {
            "active_aleph": i if moed_key == "aleph" else ctx.get("active_aleph", 0),
            "active_bet": i if moed_key == "bet" else ctx.get("active_bet", 0),
        }
        tabs += f'<a class="period-tab{cls}" href="{_url("calendar", **cal_params)}">{_e(p["semester"])}</a>'

    # Global date shifting controls
    controls = f"""
<div class="cal-controls">
  <form method="post" action="/calendar/shift" class="shift-group" style="display:flex; align-items:center; gap:12px; flex-wrap:wrap;">
    <input type="hidden" name="semester" value="{_e(period['semester'])}"/>
    <input type="hidden" name="moed" value="{_e(period['moed'])}"/>
    <input type="hidden" name="moed_key" value="{_e(moed_key)}"/>
    <div class="shift-group">
      <label>Start shift</label>
      <input class="shift-input" type="number" name="start_shift" value="{period.get('start_shift', 0)}" min="-30" max="30"/>
    </div>
    <div class="shift-group">
      <label>End shift</label>
      <input class="shift-input" type="number" name="end_shift" value="{period.get('end_shift', 0)}" min="-30" max="30"/>
    </div>
    <button type="submit" class="btn btn-secondary">Apply</button>
    <span style="font-size:11px; color:var(--muted);">{len(period['available'])} days · click to toggle</span>
  </form>
</div>"""

    cal = _render_config_calendar(period, moed_key, ctx)
    legend_color = "rgba(79,142,247,.3)" if moed_key == "aleph" else "rgba(232,131,79,.3)"
    
    return f"""
{tabs}
{controls}
<div>{cal}</div>
<div class="cal-legend">
  <div class="legend-item"><div class="legend-dot" style="background:{legend_color}"></div> Available</div>
  <div class="legend-item"><div class="legend-dot" style="background:rgba(224,82,82,.2)"></div> Excluded</div>
</div>"""


def _render_config_calendar(period: dict, moed_key: str, ctx: dict) -> str:
    """
    Renders the month-by-month grid for date configuration.
    Each day is a button that submits a form to toggle its availability state.
    """
    # Parse boundaries
    start = datetime.strptime(period["start"], "%Y-%m-%d")
    end = datetime.strptime(period["end"], "%Y-%m-%d")
    
    # Identify all months spanning the period
    months = []
    cur = datetime(start.year, start.month, 1)
    end_month = datetime(end.year, end.month, 1)
    while cur <= end_month:
        months.append(cur)
        if cur.month == 12:
            cur = datetime(cur.year + 1, 1, 1)
        else:
            cur = datetime(cur.year, cur.month + 1, 1)

    avail = set(period["available"])
    all_dates = set(period["all_dates"])
    avail_cls = f"available-{moed_key}"
    blocks = []

    # Render each month as a block
    for m in months:
        year, month = m.year, m.month
        # Calculate padding needed for the first week (align to Sunday=0)
        first_day = datetime(year, month, 1).weekday()
        first_day = (first_day + 1) % 7
        
        # Calculate how many days exist in the current month
        days_in_month = (
            datetime(year + 1, 1, 1) - datetime(year, month, 1)
            if month == 12
            else datetime(year, month + 1, 1) - datetime(year, month, 1)
        ).days
        
        month_str = m.strftime("%B %Y")
        
        # Build Day name headers (Sun, Mon, Tue...)
        cells = "".join(f'<div class="cal-header-cell">{d}</div>' for d in DAY_NAMES)
        
        # Fill empty cells before the 1st of the month
        for _ in range(first_day):
            cells += '<div class="cal-day empty"></div>'
            
        # Loop through all real days in the month
        for d in range(1, days_in_month + 1):
            date_str = f"{year}-{month:02d}-{d:02d}"
            
            if date_str not in all_dates:
                # Outside the configured start/end period
                cells += f'<div class="cal-day out-of-range">{d}</div>'
            elif date_str in avail:
                # Available for scheduling: create a toggle button form
                cells += f"""
<form method="post" action="/calendar/toggle" style="display:block;">
  <input type="hidden" name="semester" value="{_e(period['semester'])}"/>
  <input type="hidden" name="moed" value="{_e(period['moed'])}"/>
  <input type="hidden" name="date" value="{_e(date_str)}"/>
  <button type="submit" class="cal-day {avail_cls}" style="width:100%; border:inherit; font:inherit; cursor:pointer;">{d}</button>
</form>"""
            else:
                # Excluded (manual or holiday): create a toggle button form to reactivate
                cells += f"""
<form method="post" action="/calendar/toggle" style="display:block;">
  <input type="hidden" name="semester" value="{_e(period['semester'])}"/>
  <input type="hidden" name="moed" value="{_e(period['moed'])}"/>
  <input type="hidden" name="date" value="{_e(date_str)}"/>
  <button type="submit" class="cal-day excluded" style="width:100%; border:inherit; font:inherit; cursor:pointer;">{d}</button>
</form>"""
                
        blocks.append(
            f'<div class="month-block"><div class="month-label">{_e(month_str)}</div>'
            f'<div class="cal-grid">{cells}</div></div>'
        )
    return "".join(blocks)


# ==========================================
# SCREEN: OUTPUT (Viewing Generated Results)
# ==========================================

def _render_sort_panel(ctx: dict) -> str:
    """
    Renders the dynamic multi-criteria sort controls for the Output screen.

    The user picks an ordered set of criteria (Primary, Secondary, Tertiary, ...).
    Submitting re-orders the already-generated schedules instantly without
    re-running the scheduler. Every selected criterion sorts in descending order.
    """
    options = ctx.get("sort_options", [])
    current = ctx.get("sort_criteria", [])
    if not options:
        return ""

    active_sem = ctx.get("active_semester", "")
    priority_labels = ["Primary", "Secondary", "Tertiary", "4th", "5th"]

    slots = []
    for i, prio in enumerate(priority_labels):
        selected_key = current[i] if i < len(current) else ""
        opts = [
            f'<option value="" {"selected" if not selected_key else ""}>— none —</option>'
        ]
        for opt in options:
            sel = "selected" if opt["key"] == selected_key else ""
            opts.append(
                f'<option value="{_e(opt["key"])}" {sel} title="{_e(opt["desc"])}">{_e(opt["label"])}</option>'
            )
        slots.append(f"""
<div class="sort-slot">
  <label class="sort-slot-label">{_e(prio)}</label>
  <select class="filter" name="sort_{i + 1}">{"".join(opts)}</select>
</div>""")

    if current:
        labels = {o["key"]: o["label"] for o in options}
        active_txt = " ▸ ".join(_e(labels.get(k, k)) for k in current)
        summary = f'<span class="sort-active">Active: {active_txt} <span style="color:var(--muted-soft)">(all descending)</span></span>'
    else:
        summary = '<span class="sort-active" style="color:var(--muted);">No sorting applied — generation order</span>'

    return f"""
<div class="card sort-panel">
  <div class="card-title" style="margin-bottom:6px;">↕ Sort Schedules</div>
  <p style="color:var(--muted); font-size:12px; margin-bottom:12px;">
    Choose an ordered set of criteria. Each layer sorts in <strong>descending</strong> order
    and re-orders the existing results instantly (no re-generation).
  </p>
  <form method="post" action="/sort" class="sort-form">
    <input type="hidden" name="semester_view" value="{_e(active_sem)}"/>
    <div class="sort-slots">{"".join(slots)}</div>
    <div style="display:flex; align-items:center; gap:14px; margin-top:14px; flex-wrap:wrap;">
      <button type="submit" class="btn btn-green">Apply Sort</button>
      {summary}
    </div>
  </form>
</div>"""


def _render_gen_progress_bar(ctx: dict) -> str:
    """Banner shown on Output while schedules are still being generated."""
    active = ctx.get("gen_running", False)
    style = "" if active else ' style="display:none;"'
    aleph = ctx.get("aleph_total", 0)
    bet = ctx.get("bet_total", 0)
    return (
        f'<div id="gen-progress-bar" class="gen-progress-bar" data-active="{"1" if active else "0"}"{style}>'
        f'⏳ Generating… <span id="live-aleph-count">{aleph}</span> Aleph · '
        f'<span id="live-bet-count">{bet}</span> Bet schedules found so far'
        f'</div>'
    )


def _render_output_body(ctx: dict) -> str:
    schedule = ctx.get("schedule")
    if schedule and (schedule.get("aleph_entries") or schedule.get("bet_entries")):
        return (
            '<div class="dual-output-layout">'
            '<div class="output-panel">'
            '<div class="output-panel-header aleph">'
            '<span>♦ MOED ALEPH</span>'
            f'<span style="font-size:10px;color:rgba(79,142,247,.6);">{len(schedule.get("aleph_entries", []))} exams</span>'
            '</div>'
            + _render_result_calendar(schedule.get("aleph_entries", []), "aleph")
            + '</div>'
            '<div class="output-panel">'
            '<div class="output-panel-header bet">'
            '<span>♦ MOED BET</span>'
            f'<span style="font-size:10px;color:rgba(232,131,79,.6);">{len(schedule.get("bet_entries", []))} exams</span>'
            '</div>'
            + _render_result_calendar(schedule.get("bet_entries", []), "bet")
            + '</div></div>'
        )
    if ctx.get("gen_running"):
        return (
            '<div class="empty-state">'
            '<div class="icon">⏳</div>'
            'Generating schedules… calendars will appear here as results are found.'
            '</div>'
        )
    return (
        '<div class="empty-state">'
        '<div class="icon">📭</div>'
        'No schedules yet — generate from the Input screen.'
        '</div>'
    )


def render_output_live(ctx: dict) -> dict:
    """Return HTML fragments for live Output updates during background generation."""
    aleph_page = ctx.get("aleph_page", 0)
    bet_page = ctx.get("bet_page", 0)
    aleph_total = ctx.get("aleph_total", 0)
    bet_total = ctx.get("bet_total", 0)
    return {
        "gen_progress_html": _render_gen_progress_bar(ctx),
        "output_top_bar_html": (
            _render_output_toolbar("aleph", aleph_page, aleph_total, ctx)
            + _render_output_toolbar("bet", bet_page, bet_total, ctx)
        ),
        "output_body_html": _render_output_body(ctx),
    }


def _render_output(ctx: dict) -> str:
    aleph_page  = ctx.get("aleph_page", 0)
    bet_page    = ctx.get("bet_page", 0)
    aleph_total = ctx.get("aleph_total", 0)
    bet_total   = ctx.get("bet_total", 0)
    semesters   = ctx.get("semesters", [])
    active_sem  = ctx.get("active_semester", "")

    sem_tabs = ""
    for sem in semesters:
        active_cls = " active" if sem == active_sem else ""
        # Let app.py read the saved indices for this semester from the state. 
        # By not forcing aleph_page/bet_page in the URL, it naturally loads the saved ones.
        sem_tabs += (
            f'<a class="btn btn-secondary sem-tab{active_cls}" ' +
            f'href="{_url("output", semester_view=sem)}">' +
            f'{_e(sem)}</a>'
        )
    if len(semesters) > 1:
        sem_bar = (
            '<div class="sem-switcher" style="display:flex;gap:8px;align-items:center;margin-bottom:16px;flex-wrap:wrap;">' +
            '<span style="font-size:11px;color:var(--muted);font-family:var(--mono);letter-spacing:1px;">SEMESTER:</span>' +
            sem_tabs + '</div>'
        )
    else:
        sem_bar = (
            f'<div style="font-family:var(--mono);font-size:11px;color:var(--muted);margin-bottom:14px;letter-spacing:1px;">SEMESTER: {_e(active_sem)}</div>'
            if active_sem else ""
        )

    aleph_toolbar = _render_output_toolbar("aleph", aleph_page, aleph_total, ctx)
    bet_toolbar   = _render_output_toolbar("bet",   bet_page,   bet_total,   ctx)

    out_body = _render_output_body(ctx)
    gen_progress = _render_gen_progress_bar(ctx)

    export_disabled = "" if (aleph_total or bet_total) else " disabled"
    export_href = f"/export"
    export_label = f"↓ Export All Semesters"

    can_undo = ctx.get("can_undo", False)
    edit_count = ctx.get("edit_count", 0)
    undo_disabled = "" if can_undo else " disabled"
    undo_label = "↶ Undo" + (f" ({edit_count})" if edit_count else "")
    undo_btn = (
        '<form method="post" action="/reschedule/undo" class="reschedule-undo-form" style="display:inline;">'
        f'<input type="hidden" name="semester_view" value="{_e(active_sem)}"/>'
        f'<button type="submit" class="btn btn-secondary"{undo_disabled}>{undo_label}</button>'
        '</form>'
    )

    sort_panel = _render_sort_panel(ctx)

    return (
        '<div class="screen active">' +
        sem_bar +
        sort_panel +
        gen_progress +
        '<div class="output-top-bar" id="output-top-bar">' + aleph_toolbar + bet_toolbar + '</div>' +
        '<div class="export-bar">' +
        f'<a class="btn btn-primary" href="{export_href}"{export_disabled}>{export_label}</a>' +
        undo_btn +
        '<span class="rsc-hint">💡 Drag any exam to another day to preview the reschedule impact · 🔒 lock to freeze an exam</span>' +
        '</div>' +
        f'<div id="output-body">{out_body}</div>' +
        '</div>'
    )


def _render_output_toolbar(moed: str, page: int, total: int, ctx: dict) -> str:
    active_sem = ctx.get("active_semester", "")
    """
    Renders the pagination controls for navigating through multiple schedule variations.
    Because backtracking can generate hundreds of valid combinations, pagination is essential.
    """
    color_var = "aleph-color" if moed == "aleph" else "bet-color"
    num_cls = "aleph-num" if moed == "aleph" else "bet-num"
    label = "Moed Aleph" if moed == "aleph" else "Moed Bet"

    # Disable buttons if at boundaries
    if total == 0:
        counter = '<span class="x">—</span> <span class="y">/ 0</span>'
        prev_dis = next_dis = " disabled"
    else:
        counter = f'<span class="x {num_cls}">{page + 1}</span> <span class="y">/ {total}</span>'
        prev_dis = " disabled" if page <= 0 else ""
        next_dis = " disabled" if page >= total - 1 else ""

    page_btns = _render_page_jump_buttons(moed, page, total, ctx, active_sem)
    other = "bet_page" if moed == "aleph" else "aleph_page"
    other_val = ctx.get("bet_page" if moed == "aleph" else "aleph_page", 0)

    # Build navigation URLs
    other_val_1b = other_val + 1
    prev_url = _url("output", semester_view=active_sem, **{f"{moed}_page": page, other: other_val_1b})
    next_url = _url("output", semester_view=active_sem, **{f"{moed}_page": page + 2, other: other_val_1b})

    return f"""
<div class="output-toolbar {moed}" style="flex-direction:column; gap:6px; align-items:center;">
  <div style="font-size:9px; color:var(--{color_var}); font-family:var(--mono); text-transform:uppercase; letter-spacing:1px;">{label}</div>
  <div style="display:flex; gap:4px; align-items:center; flex-wrap:wrap; justify-content:center;">
    <a class="btn btn-secondary" style="padding:4px 9px; font-size:11px;" href="{prev_url}"{prev_dis}>← Prev</a>
    <div class="schedule-counter" style="min-width:70px; text-align:center;">{counter}</div>
    <a class="btn btn-secondary" style="padding:4px 9px; font-size:11px;" href="{next_url}"{next_dis}>Next →</a>
  </div>
  <div style="display:flex; gap:3px; flex-wrap:wrap; justify-content:center;">{page_btns}</div>
  
  <form method="get" action="/" style="display:flex; gap:4px; align-items:center;">
    <input type="hidden" name="screen" value="output"/>
    <input type="hidden" name="semester_view" value="{active_sem}"/>
    <input type="hidden" name="{'aleph_page' if moed == 'bet' else 'bet_page'}" value="{other_val_1b}"/>
    <input type="number" name="{moed}_page" min="1" max="{max(total, 1)}"
      style="width:62px; padding:3px 6px; border:1px solid var(--border); border-radius:5px;
             background:var(--surface); color:var(--text); font-size:12px; font-family:var(--mono);"
      placeholder="#" required/>
    <button type="submit" class="btn btn-secondary" style="padding:3px 9px; font-size:11px;">Go</button>
  </form>
</div>"""


def _render_page_jump_buttons(moed: str, current: int, total: int, ctx: dict, active_sem: str = "") -> str:
    """
    Renders quick-jump pagination buttons (+10, -50, etc.).
    Uses PAGE_JUMP_STEPS list to decide intervals based on current page position.
    """
    if total <= 1:
        return ""
    other_key = "bet_page" if moed == "aleph" else "aleph_page"
    other_val = ctx.get(other_key, 0)
    
    left, right = [], []
    
    # Calculate visible left jumps
    for s in PAGE_JUMP_STEPS:
        p = current - s
        if 0 <= p < total and p not in left:
            left.append(p)
    left.sort(reverse=True)
    left_show = list(reversed(left[:5]))
    
    # Calculate visible right jumps
    for s in PAGE_JUMP_STEPS:
        p = current + s
        if p < total and p not in right:
            right.append(p)
    right_show = right[:5]
    
    parts = []
    # Build HTML for left jumps
    for p in left_show:
        parts.append(
            f'<a class="btn btn-secondary" style="padding:2px 7px; font-size:11px; font-family:var(--mono);" '
            f'href="{_url("output", semester_view=active_sem, **{f"{moed}_page": p + 1, other_key: other_val + 1})}">{p + 1}</a>'
        )
        
    # Current page indicator in the middle
    parts.append(
        f'<span style="padding:2px 5px; font-size:11px; font-family:var(--mono); color:var(--muted);">[{current + 1}]</span>'
    )
    
    # Build HTML for right jumps
    for p in right_show:
        parts.append(
            f'<a class="btn btn-secondary" style="padding:2px 7px; font-size:11px; font-family:var(--mono);" '
            f'href="{_url("output", semester_view=active_sem, **{f"{moed}_page": p + 1, other_key: other_val + 1})}">{p + 1}</a>'
        )
    return "".join(parts)


def _render_result_calendar(entries: list, moed: str) -> str:
    """
    Renders the read-only final result calendar displaying mapped exams.
    Displays course ID, name, and color-codes obligatory vs elective courses.
    """
    if not entries:
        return '<div style="padding:24px; color:var(--muted); font-size:12px; text-align:center;">No exams scheduled</div>'

    # Group the exam entries by their assigned date string
    by_date: dict[str, list] = {}
    for e in entries:
        by_date.setdefault(e["date"], []).append(e)

    # Determine date boundaries
    dates = sorted(by_date.keys())
    start = datetime.strptime(dates[0], "%Y-%m-%d")
    end = datetime.strptime(dates[-1], "%Y-%m-%d")
    
    # Identify required months for rendering
    months = []
    cur = datetime(start.year, start.month, 1)
    end_month = datetime(end.year, end.month, 1)
    while cur <= end_month:
        months.append(cur)
        if cur.month == 12:
            cur = datetime(cur.year + 1, 1, 1)
        else:
            cur = datetime(cur.year, cur.month + 1, 1)

    blocks = []
    # Build the display grid for each month
    for m in months:
        year, month = m.year, m.month
        first_day = (datetime(year, month, 1).weekday() + 1) % 7
        days_in_month = (
            datetime(year + 1, 1, 1) - datetime(year, month, 1)
            if month == 12
            else datetime(year, month + 1, 1) - datetime(year, month, 1)
        ).days
        
        month_str = m.strftime("%B %Y")
        cells = "".join(f'<div class="out-cal-header">{d}</div>' for d in DAY_NAMES)
        
        for _ in range(first_day):
            cells += '<div class="out-cal-day empty-day"></div>'
            
        # Draw each day cell, embedding exam info if any exist on this date
        for d in range(1, days_in_month + 1):
            date_str = f"{year}-{month:02d}-{d:02d}"
            exams = by_date.get(date_str, [])
            exam_html = ""
            for e in exams:
                # Add CSS classes based on requirement to color-code the blocks
                req = "obligatory" if e["requirement"] == "Obligatory" else "elective"
                title = _e(f"{e['course_name']} ({e['instructor']})")
                progs_str = _e(", ".join(e.get("programs", [])))
                is_locked = bool(e.get("locked"))
                locked_cls = " locked" if is_locked else ""
                lock_icon = "🔒" if is_locked else "🔓"
                exam_html += (
                    f'<div class="exam-block {req} {moed}{locked_cls}" title="{title}" '
                    f'draggable="{"false" if is_locked else "true"}" '
                    f'ondragstart="rscDrag(event)" ondragend="rscDragEndEvent()" '
                    f'data-course-id="{_e(e["course_id"])}" '
                    f'data-course-name="{_e(e["course_name"])}" '
                    f'data-instructor="{_e(e["instructor"])}" '
                    f'data-requirement="{_e(req)}" '
                    f'data-programs="{progs_str}" '
                    f'data-date="{_e(e["date"])}" '
                    f'data-moed="{_e(moed)}" '
                    f'data-locked="{1 if is_locked else 0}">'
                    f'<button type="button" class="exam-lock" title="Lock / unlock exam" '
                    f'onclick="rscToggleLock(event, this)">{lock_icon}</button>'
                    f'<span class="exam-block-label" onclick="showCourseModal(this.parentNode)">'
                    f'{_e(e["course_id"])} {_e(e["course_name"])}</span>'
                    f'</div>'
                )
            cells += (
                f'<div class="out-cal-day" data-date="{date_str}" data-moed="{_e(moed)}" '
                f'ondragover="rscOver(event)" ondragleave="rscLeave(event)" ondrop="rscDrop(event)">'
                f'<div class="out-day-num">{d}</div>{exam_html}</div>'
            )
            
        blocks.append(
            f'<div class="month-block"><div class="month-label">{_e(month_str)}</div>'
            f'<div class="out-cal-grid">{cells}</div></div>'
        )
    return "".join(blocks)