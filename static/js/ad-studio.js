(function () {
  function debounce(fn, ms) {
    var t;
    return function () {
      clearTimeout(t);
      var args = arguments;
      var self = this;
      t = setTimeout(function () {
        fn.apply(self, args);
      }, ms);
    };
  }

  function dispatchInput(el) {
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function initAutosave(form) {
    var url = form.getAttribute("data-autosave-url");
    var status = document.getElementById("draft-save-status");
    var revisionInput = form.querySelector('input[name="draft_revision"]');
    if (!url || !status || !revisionInput) return;
    var timer = null, pending = null, dirty = false, leaving = false, conflicted = false;

    function show(message, state) {
      status.textContent = message;
      status.dataset.state = state;
    }
    function queue() {
      clearTimeout(timer);
      if (!leaving && !conflicted) timer = setTimeout(save, 1800);
    }
    function save() {
      if (pending || leaving || !dirty || conflicted) return;
      dirty = false;
      show("در حال ذخیره…", "pending");
      var data = new FormData(form);
      data.delete("creative_media");
      data.set("action", "save_draft");
      pending = fetch(url, {method: "POST", body: data, credentials: "same-origin",
        headers: {"X-Requested-With": "XMLHttpRequest"}})
        .then(function(r) {return r.json().then(function(body) {return {ok:r.ok, code:r.status, body:body};});})
        .then(function(res) {
          if (!res.ok) {
            conflicted = res.code === 409;
            show(res.body.message || "ذخیره انجام نشد", "error");
            return false;
          }
          revisionInput.value = res.body.revision;
          var media = form.querySelector('input[name="creative_media"]');
          show(media && media.files.length ? "متن ذخیره شد؛ فایل با ذخیره دستی ثبت می‌شود." :
            dirty ? "تغییرات جدید در انتظار ذخیره…" : "همه تغییرات ذخیره شد", dirty ? "pending" : "ok");
          return true;
        })
        .catch(function() {show("اتصال قطع شد؛ ذخیره ناموفق بود.", "error"); return false;})
        .finally(function() {pending = null; if (dirty && !leaving && !conflicted) queue();});
    }
    function changed(event) {
      if (event.target.matches && event.target.matches("input:not([name]), select:not([name]), textarea:not([name])")) return;
      if (event.target.name === "remove_creative_media") {
        show("حذف فایل با ذخیره دستی ثبت می‌شود.", "pending");
        return;
      }
      if (event.target.type === "file") {
        show("فایل را با ذخیره دستی یا دکمه بعدی ثبت کنید.", "pending");
        return;
      }
      if (leaving || conflicted) return;
      dirty = true;
      queue();
    }
    form.addEventListener("input", changed);
    form.addEventListener("change", changed);
    form.addEventListener("submit", function(event) {
      if (conflicted) {
        event.preventDefault();
        show("نسخه دیگری ذخیره شده است؛ پس از حفظ متن خود صفحه را تازه کنید.", "error");
        return;
      }
      clearTimeout(timer);
      if (pending) {
        event.preventDefault();
        if (leaving) return;
        leaving = true;
        var submitter = event.submitter;
        pending.then(function(ok) {
          leaving = false;
          if (ok) form.requestSubmit(submitter || undefined);
          else show("ذخیره قبلی تأیید نشد؛ دوباره تلاش کنید.", "error");
        });
      } else {
        leaving = true;
      }
    });
  }

  function initStudioMode(form) {
    var mode = form.getAttribute("data-studio-mode") || "simple";
    function apply(m) {
      form.classList.toggle("studio-mode--pro", m === "professional");
      form.classList.toggle("studio-mode--simple", m !== "professional");
    }
    apply(mode);
    form.querySelectorAll('input[name="studio_mode"]').forEach(function (r) {
      r.addEventListener("change", function () {
        apply(r.value);
        dispatchInput(form);
      });
    });
  }

  function initSearchChips(root) {
    var input = root.querySelector("[data-search-chip-input]");
    var list = root.querySelector("[data-search-chip-list]");
    var hidden = root.querySelector("[data-search-chip-hidden]");
    if (!input || !list || !hidden) return;
    var max = parseInt(root.getAttribute("data-max") || "10", 10);
    var chips = [];

    function sync() {
      hidden.value = JSON.stringify(chips);
      list.innerHTML = "";
      chips.forEach(function (q, idx) {
        var li = document.createElement("li");
        li.className = "chip";
        li.textContent = q;
        var btn = document.createElement("button");
        btn.type = "button";
        btn.setAttribute("aria-label", "حذف " + q);
        btn.textContent = "×";
        btn.addEventListener("click", function () {
          chips.splice(idx, 1);
          sync();
          dispatchInput(root);
        });
        li.appendChild(btn);
        list.appendChild(li);
      });
      var counter = root.querySelector("[data-search-counter]");
      if (counter) counter.textContent = chips.length + " از " + max + " عبارت جستجو";
    }

    function addQueries(raw) {
      String(raw || "")
        .split(/[\n,;]+/)
        .forEach(function (part) {
          var q = part.trim().replace(/\s+/g, " ");
          if (!q) return;
          if (
            chips.some(function (c) {
              return c.toLowerCase() === q.toLowerCase();
            })
          )
            return;
          if (chips.length >= max) return;
          chips.push(q);
        });
      sync();
      dispatchInput(root);
    }

    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        addQueries(input.value);
        input.value = "";
      }
    });
    var addButton = root.querySelector("[data-search-add]");
    if (addButton) addButton.addEventListener("click", function() {
      addQueries(input.value); input.value = ""; input.focus();
    });
    input.addEventListener("paste", function (e) {
      var text = (e.clipboardData || window.clipboardData).getData("text");
      if (text && /[\n,;]/.test(text)) {
        e.preventDefault();
        addQueries(text);
        input.value = "";
      }
    });

    try {
      var initial = JSON.parse(hidden.value || "[]");
      if (Array.isArray(initial)) chips = initial.slice(0, max);
    } catch (e) {
      chips = [];
    }
    sync();
  }

  function initAdTextCounter(ta) {
    var out = document.querySelector("[data-ad-text-count]");
    if (!ta || !out) return;
    var max = parseInt(ta.getAttribute("maxlength") || "160", 10);
    var sync = function () {
      var len = (ta.value || "").length;
      out.textContent = len + " از " + max + " کاراکتر";
      out.style.color = len > max ? "var(--danger, #c94b56)" : "";
    };
    ta.addEventListener("input", sync);
    sync();
  }

  function suggestionButton(list, label, note, onPick) {
    var li = document.createElement("li");
    var button = document.createElement("button");
    button.type = "button";
    button.className = "catalog-suggest__item";
    var name = document.createElement("span");
    name.textContent = label;
    button.appendChild(name);
    if (note) {
      var small = document.createElement("small");
      small.textContent = note;
      button.appendChild(small);
    }
    button.addEventListener("click", onPick);
    li.appendChild(button);
    list.appendChild(li);
    return button;
  }

  function appendChip(list, label, remove) {
    var li = document.createElement("li");
    li.className = "chip";
    var text = document.createElement("span");
    text.textContent = label;
    var btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = "×";
    btn.setAttribute("aria-label", "حذف " + label);
    btn.addEventListener("click", remove);
    li.append(text, btn);
    list.appendChild(li);
  }

  function initMultiselect(root) {
    var catalog;
    try { catalog = JSON.parse(root.getAttribute("data-catalog") || "[]"); } catch (_) { catalog = []; }
    if (!Array.isArray(catalog)) catalog = [];
    var kind = root.getAttribute("data-kind");
    var search = root.querySelector("[data-ms-search]");
    var chips = root.querySelector("[data-ms-chips]");
    var fields = root.querySelector("[data-ms-hidden]");
    var results = root.querySelector("[data-ms-results]");
    var status = root.querySelector("[data-ms-status]");
    if (!search || !chips || !fields || !results || !status) return;

    function inputs() { return Array.from(fields.querySelectorAll("input")); }
    function value(item) { return String(kind === "country" ? item.country_code : kind === "topic" ? item.topic_id : item.language_code); }
    function label(item) { return String(item.name_fa || item.name || value(item)); }
    function maximum() {
      var mode = root.closest("form").querySelector('[name="channel_mode"]');
      return kind === "topic" ? 20 : kind === "language" && mode && mode.value === "topics" ? 1 : 8;
    }
    function updateStatus() {
      status.textContent = inputs().length.toLocaleString("fa-IR") + " از " + maximum().toLocaleString("fa-IR") + " انتخاب";
      if (!catalog.length) status.textContent += " · فهرست در دسترس نیست یا نتیجه‌ای ندارد";
      else if (catalog.some(function(item) { return item.verified === false; })) status.textContent += " · پیشنهادهای اولیه؛ تأیید API در انتظار";
      if (inputs().length > maximum()) status.textContent += " · انتخاب اضافی را حذف کنید";
    }
    function syncChips() {
      chips.replaceChildren();
      inputs().forEach(function(inp) {
        var item = catalog.find(function(row) { return value(row) === inp.value; });
        appendChip(chips, item ? label(item) + (item.verified === false ? " (در انتظار تأیید)" : "") : inp.value + " (نیازمند بررسی)", function() {
          inp.remove(); syncChips(); renderOptions(); dispatchInput(root); search.focus();
        });
      });
      updateStatus();
    }
    function closeOptions() {
      results.replaceChildren(); results.hidden = true;
      search.setAttribute("aria-expanded", "false");
    }
    function renderOptions() {
      results.replaceChildren();
      var q = search.value.trim().toLocaleLowerCase();
      var selected = new Set(inputs().map(function(inp) { return inp.value; }));
      var options = catalog.filter(function(item) {
        return !selected.has(value(item)) && (label(item).toLocaleLowerCase().includes(q) || value(item).toLowerCase().includes(q));
      }).slice(0, 12);
      if (inputs().length >= maximum() || !options.length) {
        closeOptions();
        updateStatus();
        if (q && !options.length) status.textContent += " · نتیجه دیگری یافت نشد";
        return;
      }
      options.forEach(function(item) {
        suggestionButton(results, label(item), item.verified === false ? value(item) + " · تأیید نشده" : value(item), function() {
          if (inputs().length >= maximum() || inputs().some(function(n) { return n.value === value(item); })) return;
          var inp = document.createElement("input");
          inp.type = "hidden"; inp.name = root.getAttribute("data-field"); inp.value = value(item);
          fields.appendChild(inp);
          search.value = "";
          syncChips(); closeOptions(); dispatchInput(root); search.focus();
        });
      });
      results.hidden = false;
      search.setAttribute("aria-expanded", "true");
    }
    search.addEventListener("focus", renderOptions);
    search.addEventListener("input", renderOptions);
    search.addEventListener("keydown", function(event) {
      if (event.key === "Escape") closeOptions();
      if (event.key === "ArrowDown") {
        event.preventDefault();
        renderOptions();
        var first = results.querySelector("button");
        if (first) first.focus();
      }
      if (event.key === "Enter") {
        event.preventDefault();
        var buttons = results.querySelectorAll("button");
        if (buttons.length === 1) buttons[0].click();
        else if (buttons.length) buttons[0].focus();
      }
    });
    results.addEventListener("keydown", function(event) {
      if (event.key === "Escape") { closeOptions(); search.focus(); }
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        var buttons = Array.from(results.querySelectorAll("button"));
        var next = buttons.indexOf(document.activeElement) + (event.key === "ArrowDown" ? 1 : -1);
        if (next < 0) search.focus();
        else if (buttons[next]) buttons[next].focus();
      }
    });
    root.addEventListener("focusout", function(event) {
      if (!root.contains(event.relatedTarget)) closeOptions();
    });
    root.closest("form").addEventListener("change", function(event) {
      if (event.target.name === "channel_mode") { closeOptions(); updateStatus(); }
    });
    syncChips();
  }

  function initLineChips(root, opts) {
    var input = root.querySelector(opts.inputSel);
    var addBtn = root.querySelector(opts.addSel);
    var list = root.querySelector(opts.listSel);
    var hidden = root.querySelector(opts.hiddenSel);
    var status = opts.statusSel ? root.querySelector(opts.statusSel) : null;
    if (!input || !list || !hidden) return;
    var items = String(hidden.value || "")
      .split(/\n/)
      .map(function (s) {
        return s.trim();
      })
      .filter(Boolean);

    function sync() {
      hidden.value = items.join("\n");
      list.innerHTML = "";
      items.forEach(function (val, idx) {
        var li = document.createElement("li");
        li.className = "chip";
        li.textContent = val;
        var btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = "×";
        btn.addEventListener("click", function () {
          items.splice(idx, 1);
          sync();
          dispatchInput(root);
        });
        li.appendChild(btn);
        list.appendChild(li);
      });
    }

    function normalize(raw) {
      raw = (raw || "").trim();
      if (!raw) return "";
      if (raw.indexOf("t.me/") >= 0) {
        var m = raw.match(/t\.me\/([A-Za-z0-9_]+)/);
        if (m) return "@" + m[1];
      }
      if (raw.charAt(0) !== "@") raw = "@" + raw.replace(/^@+/, "");
      return raw;
    }

    function add() {
      var v = normalize(input.value);
      if (!v) return;
      if (items.indexOf(v) >= 0) return;
      items.push(v);
      input.value = "";
      sync();
      dispatchInput(root);
      if (opts.resolveUrl && status) {
        status.textContent = "در حال بررسی…";
        fetch(opts.resolveUrl + "?username=" + encodeURIComponent(v.replace(/^@/, "")), {
          credentials: "same-origin",
        })
          .then(function (r) {
            return r.json();
          })
          .then(function (j) {
            if (j.ok && j.bot) status.textContent = "ربات تأیید شد: " + (j.bot.title || v);
            else if (j.ok && j.channel)
              status.textContent = "کانال تأیید شد: " + (j.channel.title || v);
            else status.textContent = j.pending ? "ذخیره شد — تأیید زنده پس از اتصال API" : "ذخیره شد";
          })
          .catch(function () {
            status.textContent = "ذخیره شد";
          });
      }
    }

    if (addBtn) addBtn.addEventListener("click", add);
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        add();
      }
    });
    sync();
  }

  function initBotTargetingSelector(root, resolveUrl) {
    var input = root.querySelector("[data-bot-input]");
    var addBtn = root.querySelector("[data-bot-add]");
    var list = root.querySelector("[data-bot-chip-list]");
    var hidden = root.querySelector("[data-bot-hidden]");
    var hiddenJson = root.querySelector("[data-bot-eligibility-hidden]");
    var preview = root.querySelector("[data-bot-preview]");
    if (!input || !list || !hidden) return;

    var items = [];
    var checks = {};
    var lastResolve = null;
    var inflight = null;

    try {
      checks = JSON.parse(hiddenJson && hiddenJson.value ? hiddenJson.value : "{}") || {};
    } catch (e) {
      checks = {};
    }

    function normalize(raw) {
      raw = (raw || "").trim();
      if (!raw) return "";
      var direct = raw.match(/^@?([A-Za-z0-9_]{3,32})$/);
      if (direct) return "@" + direct[1];
      try {
        var url = new URL(raw.indexOf("://") >= 0 ? raw : "https://" + raw);
        var match = url.pathname.match(/^\/([A-Za-z0-9_]{3,32})\/?$/);
        if (/^https?:$/.test(url.protocol) && ["t.me", "telegram.me"].indexOf(url.hostname) >= 0 && !url.username && !url.password && !url.port && match) {
          return "@" + match[1];
        }
      } catch (_) {}
      return raw;
    }

    function eligibilityClass(state) {
      if (state === "eligible") return "bot-target-card--eligible";
      if (state === "insufficient_audience") return "bot-target-card--blocked";
      if (state === "invalid_bot") return "bot-target-card--invalid";
      return "bot-target-card--pending";
    }

    function syncHidden() {
      hidden.value = items
        .map(function (it) {
          return it.username;
        })
        .join("\n");
      var map = {};
      items.forEach(function (it) {
        map[it.username] = {
          eligibility: it.eligibility,
          message_fa: it.message_fa,
          hard_block: it.hard_block,
          verified: it.verified,
          bot: it.bot || {},
        };
      });
      if (hiddenJson) hiddenJson.value = JSON.stringify(map);
    }

    function textNode(tag, cls, value, dir) {
      var el = document.createElement(tag);
      if (cls) el.className = cls;
      if (dir) el.dir = dir;
      el.textContent = String(value || "");
      return el;
    }

    function appendBotContent(parent, prefix, title, user, message, photo) {
      var img = null;
      try {
        var url = new URL(photo);
        if (url.protocol === "https:") {
          img = document.createElement("img");
          img.className = prefix + "__avatar";
          img.src = url.href;
          img.alt = "";
          img.loading = "lazy";
          img.referrerPolicy = "no-referrer";
        }
      } catch (_) {}
      if (!img) {
        img = textNode("span", prefix + "__avatar " + prefix + "__avatar--empty", "🤖");
        img.setAttribute("aria-hidden", "true");
      }
      var body = document.createElement("div");
      body.className = prefix + "__body";
      body.appendChild(textNode("strong", prefix + "__title", title, "auto"));
      body.appendChild(textNode("span", prefix + "__user", user, "ltr"));
      body.appendChild(textNode("p", prefix + "__status", message));
      parent.append(img, body);
    }

    function renderPreview(payload) {
      if (!preview) return;
      preview.replaceChildren();
      preview.hidden = !payload;
      if (addBtn) addBtn.disabled = true;
      if (!payload) return;
      var bot = payload.bot || {};
      var user = "@" + String(bot.username || payload.username || "").replace(/^@+/, "");
      var state = payload.eligibility || "unknown";
      preview.className = "bot-target-preview " + eligibilityClass(state);
      appendBotContent(preview, "bot-target-preview", bot.title || payload.username, user, payload.message_fa, bot.photo_url);
      if (addBtn) addBtn.disabled = items.length >= 100 || !lastResolve ||
        payload.hard_block || state === "insufficient_audience" || state === "invalid_bot";
    }

    function renderList() {
      list.replaceChildren();
      items.forEach(function (it, idx) {
        var li = document.createElement("li");
        li.className = "bot-target-card " + eligibilityClass(it.eligibility);
        var bot = it.bot || {};
        appendBotContent(li, "bot-target-card", bot.title || it.username, it.username, it.message_fa, bot.photo_url);
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "bot-target-card__remove";
        btn.setAttribute("aria-label", "حذف " + it.username);
        btn.textContent = "×";
        btn.addEventListener("click", function () {
          items.splice(idx, 1);
          renderList();
          syncHidden();
          dispatchInput(root);
        });
        li.appendChild(btn);
        list.appendChild(li);
      });
    }

    function applyResolve(payload, query) {
      if (!payload || normalize(input.value) !== query) return;
      lastResolve = { query: query, payload: payload };
      renderPreview(payload);
    }

    var resolveDebounced = debounce(function () {
      var v = normalize(input.value);
      if (!v) {
        lastResolve = null;
        renderPreview(null);
        return;
      }
      var existing = items.some(function (it) {
        return it.username.toLowerCase() === v.toLowerCase();
      });
      if (existing) {
        renderPreview({
          eligibility: "invalid_bot",
          message_fa: "این ربات قبلاً اضافه شده است.",
          hard_block: true,
          username: v,
        });
        return;
      }
      if (!resolveUrl) return;
      if (inflight && inflight.abort) inflight.abort();
      var ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
      inflight = ctrl;
      fetch(resolveUrl + "?username=" + encodeURIComponent(v), {
        credentials: "same-origin",
        signal: ctrl ? ctrl.signal : undefined,
      })
        .then(function (r) {
          return r.json();
        })
        .then(function (j) {
          applyResolve(j, v);
        })
        .catch(function (err) {
          if (err && err.name === "AbortError") return;
          if (normalize(input.value) === v) {
            applyResolve({
              ok: false,
              username: v,
              eligibility: "api_unavailable",
              message_fa: "بررسی ربات در حال حاضر امکان‌پذیر نیست.",
              hard_block: false,
              verified: false,
            }, v);
          }
        });
    }, 700);

    input.addEventListener("input", function () {
      lastResolve = null;
      if (inflight && inflight.abort) inflight.abort();
      if (addBtn) addBtn.disabled = true;
      renderPreview(input.value.trim() ? {eligibility: "unknown", username: normalize(input.value), message_fa: "در حال بررسی ربات…"} : null);
      resolveDebounced();
    });

    function addCurrent() {
      var v = normalize(input.value);
      if (!v) return;
      if (
        items.some(function (it) {
          return it.username.toLowerCase() === v.toLowerCase();
        })
      ) {
        return;
      }
      var payload =
        lastResolve && lastResolve.query.toLowerCase() === v.toLowerCase() ? lastResolve.payload : null;
      if (!payload || !payload.eligibility) {
        return;
      }
      if (items.length >= 100 || payload.hard_block || payload.eligibility === "insufficient_audience" || payload.eligibility === "invalid_bot") {
        return;
      }
      items.push({
        username: v,
        eligibility: payload.eligibility,
        message_fa: payload.message_fa,
        hard_block: !!payload.hard_block,
        verified: !!payload.verified,
        bot: payload.bot || {},
      });
      input.value = "";
      lastResolve = null;
      renderPreview(null);
      renderList();
      syncHidden();
      dispatchInput(root);
    }

    if (addBtn) addBtn.addEventListener("click", addCurrent);
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        if (addBtn && !addBtn.disabled) addCurrent();
      }
    });

    var seeds = String(hidden.value || "")
      .split(/\n/)
      .map(function (s) {
        return normalize(s.trim());
      })
      .filter(Boolean);
    seeds.forEach(function (uname) {
      var saved = checks[uname] || checks[uname.toLowerCase()] || {};
      items.push({
        username: uname,
        eligibility: saved.eligibility || "unknown",
        message_fa: saved.message_fa || "ربات شناسایی شد؛ واجد شرایط بودن آن هنوز تأیید نشده است.",
        hard_block: !!saved.hard_block,
        verified: !!saved.verified,
        bot: saved.bot || {},
      });
    });
    renderList();
    syncHidden();

    items.forEach(function (it, idx) {
      if (!resolveUrl) return;
      fetch(resolveUrl + "?username=" + encodeURIComponent(it.username), { credentials: "same-origin" })
        .then(function (r) {
          return r.json();
        })
        .then(function (j) {
          if (!j || !j.username) return;
          var currentIndex = items.indexOf(it);
          if (currentIndex < 0) return;
          items[currentIndex] = {
            username: normalize(j.username || it.username),
            eligibility: j.eligibility || it.eligibility,
            message_fa: j.message_fa || it.message_fa,
            hard_block: !!j.hard_block,
            verified: !!j.verified,
            bot: j.bot || it.bot,
          };
          renderList();
          syncHidden();
        })
        .catch(function () {});
    });
  }

  function initScheduleEditor(root) {
    if (!root) return;
    var enabled = root.querySelector("[data-schedule-enabled]");
    var wrap = root.querySelector("[data-schedule-grid-wrap]");
    var hidden = root.querySelector("[data-schedule-json]");
    var summary = root.querySelector("[data-schedule-summary]");
    var masks = [0, 0, 0, 0, 0, 0, 0];

    function load() {
      try {
        var parsed = JSON.parse(hidden.value || "{}");
        if (parsed.week_hours_mask && parsed.week_hours_mask.length === 7) {
          masks = parsed.week_hours_mask.map(function (m) {
            return parseInt(m, 10) || 0;
          });
        }
      } catch (e) {
        masks = [0, 0, 0, 0, 0, 0, 0];
      }
    }

    function persist() {
      hidden.value = JSON.stringify({
        week_hours_mask: masks,
        timezone: parseInt((root.querySelector('[name="schedule_timezone"]') || {}).value || "12600", 10),
        use_viewer_timezone: !!(root.querySelector('[name="schedule_viewer_timezone"]') || {}).checked,
      });
      paint();
      if (summary) summary.textContent = summarize();
      dispatchInput(root);
    }

    function summarize() {
      var days = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه", "شنبه", "یکشنبه"];
      var parts = [];
      masks.forEach(function (mask, d) {
        if (!mask) return;
        var hrs = [];
        for (var h = 0; h < 24; h++) if (mask & (1 << h)) hrs.push(h);
        if (hrs.length) parts.push(days[d] + ": " + hrs.join("، "));
      });
      return parts.length ? parts.join(" · ") : "بازه‌ای انتخاب نشده";
    }

    function paint() {
      root.querySelectorAll(".schedule-cell").forEach(function (btn) {
        var tr = btn.closest("tr");
        var day = parseInt(tr.getAttribute("data-day-index"), 10);
        var hour = parseInt(btn.getAttribute("data-hour"), 10);
        var on = (masks[day] >> hour) & 1;
        btn.classList.toggle("is-on", !!on);
        btn.setAttribute("aria-pressed", on ? "true" : "false");
      });
    }

    load();
    paint();
    var viewer = root.querySelector('[name="schedule_viewer_timezone"]');
    var zone = root.querySelector('[name="schedule_timezone"]');
    function syncZone() { if(zone) zone.disabled=!!(viewer && viewer.checked); }
    if(viewer) viewer.addEventListener("change",function(){syncZone();persist();});
    if(zone) zone.addEventListener("change",persist);
    syncZone();

    var cells = Array.from(root.querySelectorAll(".schedule-cell"));
    cells.forEach(function (cell, index) {
      cell.tabIndex = index === 0 ? 0 : -1;
      cell.addEventListener("focus", function () {
        cells.forEach(function (other) { other.tabIndex = other === cell ? 0 : -1; });
      });
      cell.addEventListener("keydown", function (event) {
        if (event.altKey || event.metaKey) return;
        var next = index;
        var rtl = getComputedStyle(root).direction === "rtl";
        if (event.key === "ArrowRight") next += rtl ? -1 : 1;
        else if (event.key === "ArrowLeft") next += rtl ? 1 : -1;
        else if (event.key === "ArrowDown") next += 24;
        else if (event.key === "ArrowUp") next -= 24;
        else if (event.key === "Home") next = event.ctrlKey ? 0 : Math.floor(index / 24) * 24;
        else if (event.key === "End") next = event.ctrlKey ? cells.length - 1 : Math.floor(index / 24) * 24 + 23;
        else return;
        event.preventDefault();
        cells[Math.max(0, Math.min(cells.length - 1, next))].focus();
      });
    });

    root.querySelectorAll(".schedule-cell").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var tr = btn.closest("tr");
        var day = parseInt(tr.getAttribute("data-day-index"), 10);
        var hour = parseInt(btn.getAttribute("data-hour"), 10);
        masks[day] ^= 1 << hour;
        persist();
      });
    });

    root.querySelectorAll("[data-schedule-preset]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var p = btn.getAttribute("data-schedule-preset");
        if (p === "clear") masks = [0, 0, 0, 0, 0, 0, 0];
        else if (p === "all") masks = [(1 << 24) - 1, (1 << 24) - 1, (1 << 24) - 1, (1 << 24) - 1, (1 << 24) - 1, (1 << 24) - 1, (1 << 24) - 1];
        else if (p === "business") {
          var work = 0;
          for (var h = 9; h < 18; h++) work |= 1 << h;
          masks = [work, work, work, work, work, 0, 0];
        } else if (p === "evening") {
          var ev = 0;
          for (var h2 = 18; h2 < 23; h2++) ev |= 1 << h2;
          masks = [ev, ev, ev, ev, ev, ev, ev];
        }
        if (enabled) enabled.checked = true;
        if (wrap) wrap.hidden = false;
        persist();
      });
    });

    if (enabled) {
      enabled.addEventListener("change", function () {
        if (wrap) wrap.hidden = !enabled.checked;
        if (!enabled.checked) {
          masks = [0, 0, 0, 0, 0, 0, 0];
          persist();
        }
        dispatchInput(root);
      });
    }
  }

  function initChannelMode(form) {
    var select = form.querySelector('[name="channel_mode"]');
    if (!select) return;
    function sync() {
      form.querySelectorAll("[data-channel-modes]").forEach(function(section) {
        var active = section.dataset.channelModes.split(" ").includes(select.value);
        section.hidden = !active;
        section.querySelectorAll("input, textarea, select, button").forEach(function(control) {
          control.disabled = !active;
        });
      });
    }
    select.addEventListener("change", sync);
    sync();
  }

  function initLocationPicker(form) {
    var root = form.querySelector("[data-location-picker]");
    if (!root) return;
    var search = root.querySelector("[data-location-search]");
    var results = root.querySelector("[data-location-results]");
    var chips = root.querySelector("[data-location-chips]");
    var hiddenWrap = root.querySelector("[data-location-hidden]");
    var status = root.querySelector("[data-location-status]");
    var base = form.getAttribute("data-catalog-locations");
    var countryRoot = form.querySelector('[data-field="country_codes"]');
    if (!search || !results || !chips || !hiddenWrap || !base || !status || !countryRoot) return;
    var requestNumber = 0, controller = null;

    function country() {
      var selected = countryRoot.querySelectorAll("[data-ms-hidden] input");
      return selected.length === 1 ? selected[0].value : "";
    }
    function resetResults() {
      requestNumber += 1;
      if (controller) controller.abort();
      results.replaceChildren(); results.hidden = true;
    }
    function renderChips() {
      chips.replaceChildren();
      Array.from(hiddenWrap.querySelectorAll("input")).forEach(function(inp) {
        appendChip(chips, inp.dataset.label || ("موقعیت #" + inp.value), function() {
          inp.remove(); renderChips(); dispatchInput(root);
        });
      });
    }
    var previousCountry = country();
    function countryChanged() {
      var selected = country();
      if (selected !== previousCountry) {
        previousCountry = selected;
        resetResults();
        hiddenWrap.replaceChildren(); renderChips();
        search.value = "";
        status.textContent = "با تغییر کشور، موقعیت‌های قبلی حذف شدند.";
        dispatchInput(root);
      }
      search.disabled = !selected;
      if (!selected) status.textContent = "برای انتخاب شهر، دقیقاً یک کشور انتخاب کنید.";
    }
    countryRoot.addEventListener("input", countryChanged);
    search.disabled = !previousCountry;
    if (!previousCountry) status.textContent = "برای انتخاب شهر، دقیقاً یک کشور انتخاب کنید.";
    renderChips();

    var queryLocations = debounce(function() {
      var selectedCountry = country(), q = search.value.trim();
      if (!selectedCountry || q.length < 2) return;
      var seq = ++requestNumber;
      controller = new AbortController();
      status.textContent = "در حال جستجو…";
      fetch(base + "?country=" + encodeURIComponent(selectedCountry) + "&q=" + encodeURIComponent(q),
        {credentials:"same-origin", signal:controller.signal})
        .then(function(r) { return r.json().then(function(body) {return {ok:r.ok,body:body};}); })
        .then(function(response) {
          if (seq !== requestNumber || country() !== selectedCountry || q !== search.value.trim()) return;
          results.replaceChildren();
          if (!response.ok || !response.body.ok) {
            status.textContent = response.body.message || "فهرست موقعیت‌ها در دسترس نیست.";
            return;
          }
          var items = response.body.items || [];
          var picked = new Set(Array.from(hiddenWrap.querySelectorAll("input")).map(function(inp){return inp.value;}));
          items.filter(function(loc){return loc.verified && loc.country_code === selectedCountry && !picked.has(String(loc.location_id));}).forEach(function(loc) {
            suggestionButton(results, loc.name, loc.region, function() {
              if (country() !== selectedCountry || hiddenWrap.querySelectorAll("input").length >= 20) {
                status.textContent = "حداکثر ۲۰ موقعیت در یک کشور قابل انتخاب است."; return;
              }
              var inp = document.createElement("input");
              inp.type = "hidden"; inp.name = "location_ids"; inp.value = String(loc.location_id); inp.dataset.label = loc.name;
              hiddenWrap.appendChild(inp);
              resetResults(); renderChips(); search.value = ""; status.textContent = "موقعیت اضافه شد.";
              dispatchInput(root); search.focus();
            });
          });
          results.hidden = !results.children.length;
          status.textContent = results.hidden ? "موقعیت دیگری یافت نشد." : "موقعیت موردنظر را انتخاب کنید.";
        })
        .catch(function(err) { if (err.name !== "AbortError" && seq === requestNumber) status.textContent = "ارتباط با فهرست موقعیت‌ها برقرار نشد."; });
    }, 350);
    search.addEventListener("input", function() {
      resetResults();
      status.textContent = search.value.trim().length >= 2 ? "در حال جستجو…" : "حداقل دو حرف بنویسید.";
      queryLocations();
    });
    search.addEventListener("keydown", function(event) {
      if (event.key === "Enter") event.preventDefault();
      if (event.key === "ArrowDown") {
        event.preventDefault(); var first = results.querySelector("button"); if (first) first.focus();
      }
      if (event.key === "Escape") resetResults();
    });
    root.addEventListener("focusout", function(event) {
      if (!root.contains(event.relatedTarget)) resetResults();
    });
  }

  function initPolicyRefresh(form) {
    var url = form.getAttribute("data-policy-preview-url");
    var panel = form.querySelector("[data-policy-panel]");
    var btn = form.querySelector("[data-policy-refresh]");
    var status = form.querySelector("[data-policy-refresh-status]");
    if (!url || !panel) return;

    var pending = null;
    var retryTimer = null;
    var requestSeq = 0;
    var severityLabel = {
      blocked: "نیازمند اصلاح",
      review_required: "نیازمند بررسی",
      warning: "هشدار",
      info: "راهنما",
    };

    function toPersianDigits(value) {
      return String(value == null ? 0 : value).replace(/\d/g, function (d) {
        return "۰۱۲۳۴۵۶۷۸۹"[d];
      });
    }

    function setStatus(text) {
      if (status) status.textContent = text || "";
    }

    function updateCounts(counts) {
      var map = counts || {};
      panel.querySelectorAll("[data-policy-count]").forEach(function (el) {
        var key = el.getAttribute("data-policy-count");
        var value = toPersianDigits(map[key] || 0);
        var strong = el.querySelector("strong");
        if (strong) {
          strong.textContent = value;
          return;
        }
        var labels = {
          blocked: "مسدود",
          review_required: "بررسی",
          warning: "هشدار",
        };
        el.textContent = (labels[key] || key) + ": " + value;
      });
    }

    function updateFindings(findings) {
      var list = panel.querySelector("[data-policy-findings]");
      if (!list) return;
      list.replaceChildren();
      var items = findings || [];
      if (!items.length) {
        var empty = document.createElement("li");
        empty.className = "policy-findings__empty";
        empty.textContent = "مورد مهمی یافت نشد. می‌توانید ادامه دهید.";
        list.appendChild(empty);
        return;
      }
      items.forEach(function (finding) {
        var li = document.createElement("li");
        var severity = finding.severity || "info";
        li.className = "policy-findings__item policy-findings__item--" + severity;

        var top = document.createElement("div");
        top.className = "policy-findings__top";
        var badge = document.createElement("span");
        badge.className = "policy-findings__badge";
        badge.textContent = severityLabel[severity] || severity;
        top.appendChild(badge);
        var clause = finding.source_clause_label || "";
        if (clause) {
          var clauseEl = document.createElement("span");
          clauseEl.className = "policy-findings__clause";
          clauseEl.textContent = clause;
          top.appendChild(clauseEl);
        }
        li.appendChild(top);

        if (finding.rule_title_fa) {
          var ruleTitle = document.createElement("p");
          ruleTitle.className = "policy-findings__rule-title";
          ruleTitle.textContent = finding.rule_title_fa;
          li.appendChild(ruleTitle);
        }

        var message = document.createElement("p");
        message.className = "policy-findings__message";
        message.textContent = finding.message_fa || "";
        li.appendChild(message);

        if (finding.suggestion_fa) {
          var hint = document.createElement("p");
          hint.className = "policy-findings__hint";
          hint.textContent = finding.suggestion_fa;
          li.appendChild(hint);
        }

        var links = document.createElement("div");
        links.className = "policy-findings__links";
        if (finding.field_key) {
          var targetId = "field-" + finding.field_key;
          if (document.getElementById(targetId)) {
            var jump = document.createElement("a");
            jump.className = "policy-findings__jump";
            jump.href = "#" + targetId;
            jump.setAttribute("data-policy-jump", finding.field_key);
            jump.textContent = "رفتن به فیلد";
            links.appendChild(jump);
          }
        }
        if (finding.guide_url) {
          var ruleLink = document.createElement("a");
          ruleLink.className = "policy-findings__rule";
          ruleLink.href = finding.guide_url;
          ruleLink.target = "_blank";
          ruleLink.rel = "noopener";
          ruleLink.textContent = finding.guide_label || "مشاهده قانون";
          links.appendChild(ruleLink);
        }
        if (finding.source_url && finding.source_url !== finding.guide_url) {
          var sourceLink = document.createElement("a");
          sourceLink.className = "policy-findings__source";
          sourceLink.href = finding.source_url;
          sourceLink.target = "_blank";
          sourceLink.rel = "noopener";
          sourceLink.textContent = "منبع رسمی";
          links.appendChild(sourceLink);
        }
        if (links.childNodes.length) li.appendChild(links);

        list.appendChild(li);
      });
    }

    function focusPolicyField(fieldKey) {
      if (!fieldKey) return false;
      var target = document.getElementById("field-" + fieldKey);
      if (!target) return false;
      target.scrollIntoView({ behavior: "smooth", block: "center" });
      target.classList.add("is-policy-focus");
      var focusable = target.matches("input, textarea, select, button")
        ? target
        : target.querySelector("input:not([type='hidden']), textarea, select, button");
      if (focusable && typeof focusable.focus === "function") {
        try {
          focusable.focus({ preventScroll: true });
        } catch (err) {
          focusable.focus();
        }
      }
      window.clearTimeout(focusPolicyField._timer);
      focusPolicyField._timer = window.setTimeout(function () {
        target.classList.remove("is-policy-focus");
      }, 2200);
      return true;
    }

    panel.addEventListener("click", function (event) {
      var jump = event.target.closest("[data-policy-jump]");
      if (!jump || !panel.contains(jump)) return;
      var key = jump.getAttribute("data-policy-jump");
      if (!focusPolicyField(key)) return;
      event.preventDefault();
    });

    function refresh(options) {
      var opts = options || {};
      if (pending && !opts.force) return;
      clearTimeout(retryTimer);
      var seq = ++requestSeq;
      panel.setAttribute("aria-busy", "true");
      panel.classList.add("is-refreshing");
      setStatus("در حال بررسی…");
      var data = new FormData(form);
      data.delete("creative_media");
      pending = fetch(url, { method: "POST", body: data, credentials: "same-origin" })
        .then(function (r) {
          return r.json().then(function (body) {
            return { ok: r.ok, status: r.status, body: body };
          });
        })
        .then(function (response) {
          if (seq !== requestSeq) return;
          var body = response.body || {};
          if (response.status === 429 || body.retry) {
            setStatus(body.message || "چند لحظه بعد دوباره…");
            retryTimer = setTimeout(function () {
              refresh({ force: true });
            }, 1200);
            return;
          }
          if (!response.ok || !body.ok) {
            setStatus(body.message || "بررسی ناموفق");
            return;
          }
          updateCounts(body.counts);
          updateFindings(body.findings);
          var blocked = (body.counts && body.counts.blocked) || 0;
          var review = (body.counts && body.counts.review_required) || 0;
          setStatus(
            body.ready
              ? "از نظر ساختاری آماده‌ست."
              : toPersianDigits(blocked) + " مسدود · " + toPersianDigits(review) + " نیازمند بررسی"
          );
        })
        .catch(function () {
          if (seq === requestSeq) setStatus("بررسی ناموفق");
        })
        .finally(function () {
          if (seq === requestSeq) {
            pending = null;
            panel.removeAttribute("aria-busy");
            panel.classList.remove("is-refreshing");
          }
        });
    }

    var scheduleRefresh = debounce(function () {
      refresh();
    }, 700);

    if (btn) {
      btn.addEventListener("click", function () {
        refresh({ force: true });
      });
    }

    form.addEventListener("input", function (event) {
      var target = event.target;
      if (!target || !target.name) return;
      if (target.type === "file" || target.name === "creative_media" || target.name === "website_photo") return;
      scheduleRefresh();
    });
    form.addEventListener("change", function (event) {
      var target = event.target;
      if (!target || !target.name) return;
      if (target.type === "file") return;
      scheduleRefresh();
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var form = document.querySelector(".studio-form");
    if (!form) return;
    initAutosave(form);
    initStudioMode(form);
    form.querySelectorAll("[data-creative-template-text]").forEach(function(btn) {
      btn.addEventListener("click", function() {
        var text = form.querySelector('[name="ad_text"]');
        var cta = form.querySelector('[name="cta_label"]');
        if (text) {text.value = btn.dataset.creativeTemplateText; dispatchInput(text);}
        if (cta) {cta.value = btn.dataset.creativeTemplateCta || ""; dispatchInput(cta);}
      });
    });
    initPolicyRefresh(form);
    initLocationPicker(form);
    document.querySelectorAll("[data-search-chips]").forEach(initSearchChips);
    document.querySelectorAll("[data-multiselect]").forEach(initMultiselect);
    initChannelMode(form);
    document.querySelectorAll("[data-schedule-editor]").forEach(initScheduleEditor);
    document.querySelectorAll("[data-bot-selector]").forEach(function (el) {
      initBotTargetingSelector(el, form.getAttribute("data-resolve-bot"));
    });
    document.querySelectorAll("[data-channel-selector]").forEach(function (el) {
      initLineChips(el, {
        inputSel: "[data-channel-input]",
        addSel: "[data-channel-add]",
        listSel: "[data-channel-chip-list]",
        hiddenSel: "[data-channel-hidden]",
        resolveUrl: form.getAttribute("data-resolve-channel"),
      });
    });
    var adText = document.querySelector("[data-ad-text-counter]");
    if (adText) initAdTextCounter(adText);
  });
})();
