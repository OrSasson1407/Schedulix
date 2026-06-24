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
    
    # Handle flash messages (toast notifications like "Saved successfully" or "Error")
    flash = ctx.get("flash")
    flash_html = ""
    if flash and flash.get("msg"):
        cls = "show " + ("ok" if flash.get("type") == "ok" else "err")
        flash_html = f'<div id="toast" class="{cls}">{_e(flash["msg"])}</div>'
    else:
        flash_html = '<div id="toast"></div>'

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
<title>Schedulix v2.0</title>
<link rel="icon" href="{LOGO_URL}" type="image/jpeg"/>
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
        <span class="logo-version">Version 2.0</span>
      </div>
    </div>
    {nav}
    <div class="sidebar-footer">
      <div style="font-size:11px; color:var(--muted); margin-bottom:6px;">Status</div>
      <div style="display:flex; align-items:center; font-size:12px;">
        <span class="status-dot {dot}"></span>
        <span style="font-size:11px; color:var(--muted);">{_e(status_line)}</span>
      </div>
    </div>
  </nav>
  
  <div class="main">
    <div class="topbar">
      <div class="topbar-title">{SCREEN_TITLES.get(screen, "")}</div>
    </div>
    <div class="content">
      {body}
    </div>
  </div>
</div>
{flash_html}

<script>
(function () {{
  // Helper to show popup toast notifications
  function showToast(msg, type) {{
    var el = document.getElementById("toast");
    if (!el) return;
    el.textContent = msg;
    el.className = "show " + (type || "ok");
    clearTimeout(el._t);
    el._t = setTimeout(function () {{ el.className = ""; }}, 2800);
  }}

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

  // Intercept program selection toggles (checkboxes/cards)
  document.querySelectorAll("form.program-toggle-form").forEach(function (form) {{
    form.addEventListener("submit", function (e) {{
      e.preventDefault();
      schedulixFetch(form)
        .then(function (res) {{
          if (!res.data.ok) {{
            showToast(res.data.error || "Could not update selection", "err");
            return;
          }}
          // Update the selected counter text dynamically
          var countEl = document.getElementById("sel-count");
          if (countEl) countEl.textContent = res.data.count;
          
          // Visually toggle the card state
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

  // Intercept the "Generate Schedules" form
  document.querySelectorAll("form.generate-form").forEach(function (form) {{
    form.addEventListener("submit", function (e) {{
      e.preventDefault();
      var btn = form.querySelector("#generateBtn");
      var label = btn ? btn.textContent : "";
      if (btn) {{
        btn.disabled = true; // Disable button to prevent double-clicks
        btn.textContent = "Generating…"; // Show loading state
      }}
      schedulixFetch(form)
        .then(function (res) {{
          if (!res.data.ok) {{
            showToast(res.data.error || "Generate failed", "err");
            return;
          }}
          // Update the UI with generation results
          var resultEl = document.getElementById("gen-result");
          if (resultEl) resultEl.textContent = res.data.gen_result || "";
          var historyEl = document.getElementById("gen-history-root");
          if (historyEl) historyEl.innerHTML = res.data.history_html || "";
          var outLink = document.getElementById("view-output-link");
          if (outLink) outLink.style.display = res.data.gen_result ? "inline-flex" : "none";
          if (res.data.flash && res.data.flash.msg) {{
            showToast(res.data.flash.msg, res.data.flash.type || "ok");
          }}
          // Re-bind click events for newly injected HTML
          document.querySelectorAll("form.history-restore-form").forEach(bindHistoryRestore);
          // Auto-navigate to output page when generation is done
          window.location.href = "/?screen=output";
        }})
        .catch(function () {{
          showToast("Generate failed", "err");
        }})
        .finally(function () {{
          if (btn) {{
            btn.disabled = false;
            btn.textContent = label;
          }}
        }});
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

  // Restore scroll position logic
  var content = document.querySelector(".content");
  if (!content) return;
  var scrollY = {scroll_y};
  if (scrollY > 0) {{
    content.scrollTop = scrollY;
    return;
  }}
  var id = location.hash;
  if (!id) return;
  var el = document.querySelector(id);
  if (el) el.scrollIntoView({{ block: "start", behavior: "instant" }});
}})();
  // Course detail modal
  (function() {{
    var overlay = document.createElement('div');
    overlay.id = 'course-modal-overlay';
    overlay.style.cssText = 'display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:9999;align-items:center;justify-content:center;';
    overlay.innerHTML = [
      '<div id="course-modal" style="background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:28px 32px;min-width:300px;max-width:420px;width:90%;box-shadow:0 8px 32px rgba(0,0,0,.4);position:relative;">',
      '<button onclick="hideCourseModal()" style="position:absolute;top:12px;right:16px;background:none;border:none;color:var(--muted);font-size:18px;cursor:pointer;line-height:1;">\u2715</button>',
      '<div id="cm-badge" style="font-size:10px;font-family:var(--mono);letter-spacing:1px;text-transform:uppercase;margin-bottom:8px;"></div>',
      '<div id="cm-name" style="font-size:17px;font-weight:700;color:var(--text);margin-bottom:4px;"></div>',
      '<div id="cm-id" style="font-size:11px;font-family:var(--mono);color:var(--muted);margin-bottom:18px;"></div>',
      '<table style="width:100%;border-collapse:collapse;font-size:13px;">',
      '<tr><td style="color:var(--muted);padding:5px 0;width:110px;">Instructor</td><td id="cm-instructor" style="color:var(--text);font-weight:500;"></td></tr>',
      '<tr><td style="color:var(--muted);padding:5px 0;">Requirement</td><td id="cm-req" style="font-weight:500;"></td></tr>',
      '<tr><td style="color:var(--muted);padding:5px 0;">Programs</td><td id="cm-programs" style="color:var(--text);"></td></tr>',
      '<tr><td style="color:var(--muted);padding:5px 0;">Exam Date</td><td id="cm-date" style="color:var(--text);font-family:var(--mono);"></td></tr>',
      '<tr><td style="color:var(--muted);padding:5px 0;">Moed</td><td id="cm-moed" style="font-weight:500;"></td></tr>',
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
    document.getElementById('course-modal-overlay').style.display = 'flex';
  }}

  function hideCourseModal() {{
    document.getElementById('course-modal-overlay').style.display = 'none';
  }}

  // ===== What-If / Domino-Effect drag & drop =====
  var wifDrag_ = null;     // the exam currently being dragged
  var wifPending_ = null;  // the move awaiting Apply

  function wifToast(msg, type) {{
    var el = document.getElementById('toast');
    if (!el) return;
    el.textContent = msg;
    el.className = 'show ' + (type || 'ok');
    clearTimeout(el._t);
    el._t = setTimeout(function () {{ el.className = ''; }}, 2800);
  }}

  function wifDrag(e) {{
    var d = e.target.dataset;
    wifDrag_ = {{ course_id: d.courseId, moed: d.moed, from_date: d.date }};
    try {{ e.dataTransfer.setData('text/plain', d.courseId); }} catch (err) {{}}
    e.dataTransfer.effectAllowed = 'move';
  }}

  function wifOver(e) {{
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    e.currentTarget.classList.add('wif-drop-hover');
  }}

  function wifLeave(e) {{ e.currentTarget.classList.remove('wif-drop-hover'); }}

  function wifPost(url, params) {{
    return fetch(url, {{
      method: 'POST',
      headers: {{
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-Requested-With': 'Schedulix'
      }},
      body: new URLSearchParams(params).toString()
    }}).then(function (r) {{ return r.json(); }});
  }}

  function wifDrop(e) {{
    e.preventDefault();
    e.currentTarget.classList.remove('wif-drop-hover');
    var cell = e.currentTarget.dataset;
    if (!wifDrag_) return;
    if (cell.moed !== wifDrag_.moed) {{ wifToast('Drag within the same moed', 'err'); return; }}
    if (cell.date === wifDrag_.from_date) {{ wifDrag_ = null; return; }}
    var params = {{ moed: wifDrag_.moed, course_id: wifDrag_.course_id, new_date: cell.date }};
    wifPending_ = params;
    wifPost('/whatif/resolve', params).then(function (data) {{
      if (!data.ok) {{ wifToast(data.error || 'What-if failed', 'err'); return; }}
      wifShow(data);
    }}).catch(function () {{ wifToast('What-if failed', 'err'); }});
    wifDrag_ = null;
  }}

  function wifList(items, empty, cls) {{
    if (!items || !items.length) return '<div class="wif-empty">' + empty + '</div>';
    return items.map(function (v) {{
      return '<div class="wif-item ' + (cls || '') + '">' + v.message + '</div>';
    }}).join('');
  }}

  function wifShow(data) {{
    var b = data.before || {{}};
    var plan = data.plan || [];
    var planHtml;
    if (b.legal) {{
      planHtml = '<div class="wif-ok">This move is already legal — no cascade needed.</div>';
    }} else if (data.solved) {{
      planHtml = plan.map(function (m, i) {{
        return '<div class="wif-move">' + (i + 1) + '. Move <strong>' + m.course_name +
               '</strong>: ' + m.from_date + ' \\u2192 ' + m.to_date + '</div>';
      }}).join('');
      if (!plan.length) planHtml = '<div class="wif-ok">Legal — no cascade needed.</div>';
    }} else {{
      planHtml = '<div class="wif-bad">No legal fix found within the move/time limit.</div>';
    }}
    document.getElementById('wif-sub').textContent =
      'Move ' + wifPending_.course_id + ' \\u2192 ' + wifPending_.new_date + '  (Moed ' + wifPending_.moed + ')';
    document.getElementById('wif-violations').innerHTML = wifList(b.violations, 'None \\uD83C\\uDF89', 'bad');
    document.getElementById('wif-collisions').innerHTML = wifList(b.collisions, 'None', 'warn');
    document.getElementById('wif-plan').innerHTML = planHtml;
    var applyBtn = document.getElementById('wif-apply');
    applyBtn.textContent = (data.solved && !b.legal && plan.length) ? 'Apply move + cascade' : 'Apply move';
    document.getElementById('wif-overlay').style.display = 'flex';
  }}

  function wifHide() {{ document.getElementById('wif-overlay').style.display = 'none'; }}

  function wifApply() {{
    if (!wifPending_) return;
    wifPost('/whatif/apply', wifPending_).then(function (data) {{
      if (!data.ok) {{ wifToast(data.error || 'Apply failed', 'err'); return; }}
      window.location.href = '/?screen=output';
    }}).catch(function () {{ wifToast('Apply failed', 'err'); }});
  }}

  (function () {{
    var o = document.createElement('div');
    o.id = 'wif-overlay';
    o.style.cssText = 'display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:10000;align-items:center;justify-content:center;';
    o.innerHTML = [
      '<div class="wif-modal">',
      '<button class="wif-close" onclick="wifHide()">\\u2715</button>',
      '<div class="wif-title">\\u26A1 What-If / Domino Effect</div>',
      '<div id="wif-sub" class="wif-subtitle"></div>',
      '<div class="wif-section-title">Baseline requirements violated</div>',
      '<div id="wif-violations"></div>',
      '<div class="wif-section-title">Elective courses now colliding</div>',
      '<div id="wif-collisions"></div>',
      '<div class="wif-section-title">Minimal cascade to restore a legal schedule</div>',
      '<div id="wif-plan"></div>',
      '<div class="wif-actions">',
      '<button class="btn btn-green" id="wif-apply" onclick="wifApply()">Apply</button>',
      '<button class="btn btn-secondary" onclick="wifHide()">Cancel</button>',
      '</div></div>'
    ].join('');
    document.body.appendChild(o);
    o.addEventListener('click', function (e) {{ if (e.target === o) wifHide(); }});
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
    
    <form method="post" action="/set_mode" style="margin-bottom:14px;">
      <div style="font-size:12px; color:var(--muted); margin-bottom:8px;">Load Mode</div>
      <div class="mode-toggle">
        <button type="submit" name="mode" value="overwrite" class="mode-btn {ow_cls}">Overwrite</button>
        <button type="submit" name="mode" value="append" class="mode-btn {ap_cls}">Append</button>
      </div>
    </form>
    
    <form method="post" action="/upload/courses" enctype="multipart/form-data" class="file-row">
      <input type="hidden" name="mode" value="{_e(file_mode)}"/>
      <span class="file-label">Courses File</span>
      <input type="file" name="file" accept=".txt" required style="max-width:220px; font-size:12px;"/>
      <button type="submit" class="btn btn-secondary">📂 Upload</button>
      <span class="file-status {cs_cls}">{_e(cs)}</span>
    </form>
    
    <form method="post" action="/upload/periods" enctype="multipart/form-data" class="file-row">
      <input type="hidden" name="mode" value="{_e(file_mode)}"/>
      <span class="file-label">Dates File</span>
      <input type="file" name="file" accept=".txt" required style="max-width:220px; font-size:12px;"/>
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
      Runs the backtracking scheduler on Moed Aleph <strong style="color:var(--aleph-color)">✦</strong>
      and Moed Bet <strong style="color:var(--bet-color)">✦</strong> independently.
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
        idx = len(history) - 1 - i
        is_current = idx == len(history) - 1
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
  
  <div class="dual-cal-layout">
    <div class="moed-panel aleph">
      <div class="moed-header">
        <span class="moed-badge aleph">MOED ALEPH</span>
        <span style="font-size:12px; color:var(--muted);">מועד א׳</span>
      </div>
      {aleph_panel}
    </div>
    <div class="moed-panel bet">
      <div class="moed-header">
        <span class="moed-badge bet">MOED BET</span>
        <span style="font-size:12px; color:var(--muted);">מועד ב׳</span>
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
  <form method="post" action="/sort">
    <input type="hidden" name="semester_view" value="{_e(active_sem)}"/>
    <div class="sort-slots">{"".join(slots)}</div>
    <div style="display:flex; align-items:center; gap:14px; margin-top:14px; flex-wrap:wrap;">
      <button type="submit" class="btn btn-green">Apply Sort</button>
      {summary}
    </div>
  </form>
</div>"""


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

    schedule = ctx.get("schedule")
    if schedule and (schedule.get("aleph_entries") or schedule.get("bet_entries")):
        out_body = (
            '<div class="dual-output-layout">' +
            '<div class="output-panel">' +
            '<div class="output-panel-header aleph">' +
            '<span>♦ MOED ALEPH</span>' +
            f'<span style="font-size:10px;color:rgba(79,142,247,.6);">{len(schedule.get("aleph_entries",[]))} exams</span>' +
            '</div>' +
            _render_result_calendar(schedule.get("aleph_entries", []), "aleph") +
            '</div>' +
            '<div class="output-panel">' +
            '<div class="output-panel-header bet">' +
            '<span>♦ MOED BET</span>' +
            f'<span style="font-size:10px;color:rgba(232,131,79,.6);">{len(schedule.get("bet_entries",[]))} exams</span>' +
            '</div>' +
            _render_result_calendar(schedule.get("bet_entries", []), "bet") +
            '</div></div>'
        )
    else:
        out_body = '<div class="empty-state"><div class="icon">📭</div>No schedules yet — generate from the Input screen.</div>'

    export_disabled = "" if (aleph_total or bet_total) else " disabled"
    export_href = f"/export"
    export_label = f"↓ Export All Semesters"

    sort_panel = _render_sort_panel(ctx)

    return (
        '<div class="screen active">' +
        sem_bar +
        sort_panel +
        '<div class="output-top-bar">' + aleph_toolbar + bet_toolbar + '</div>' +
        '<div class="export-bar">' +
        f'<a class="btn btn-primary" href="{export_href}"{export_disabled}>{export_label}</a>' +
        '<span class="wif-hint">💡 Drag any exam to another day to preview the domino effect</span>' +
        '</div>' +
        out_body +
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
                exam_html += (
                    f'<div class="exam-block {req} {moed}" title="{title}" '
                    f'style="cursor:grab;" '
                    f'draggable="true" ondragstart="wifDrag(event)" '
                    f'data-course-id="{_e(e["course_id"])}" '
                    f'data-course-name="{_e(e["course_name"])}" '
                    f'data-instructor="{_e(e["instructor"])}" '
                    f'data-requirement="{_e(req)}" '
                    f'data-programs="{progs_str}" '
                    f'data-date="{_e(e["date"])}" '
                    f'data-moed="{_e(moed)}" '
                    f'onclick="showCourseModal(this)">'
                    f'{_e(e["course_id"])} {_e(e["course_name"])}</div>'
                )
            cells += (
                f'<div class="out-cal-day" data-date="{date_str}" data-moed="{_e(moed)}" '
                f'ondragover="wifOver(event)" ondragleave="wifLeave(event)" ondrop="wifDrop(event)">'
                f'<div class="out-day-num">{d}</div>{exam_html}</div>'
            )
            
        blocks.append(
            f'<div class="month-block"><div class="month-label">{_e(month_str)}</div>'
            f'<div class="out-cal-grid">{cells}</div></div>'
        )
    return "".join(blocks)