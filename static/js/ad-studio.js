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
        btn.setAttribute("aria-label", "حذف");
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

  function initMultiselect(root) {
    var catalog = [];
    try {
      catalog = JSON.parse(root.getAttribute("data-catalog") || "[]");
    } catch (e) {
      catalog = [];
    }
    var kind = root.getAttribute("data-kind") || "";
    var search = root.querySelector("[data-ms-search]");
    var chipsEl = root.querySelector("[data-ms-chips]");
    var hiddenWrap = root.querySelector("[data-ms-hidden]");
    if (!search || !chipsEl || !hiddenWrap) return;

    function selectedValues() {
      return Array.prototype.map.call(
        hiddenWrap.querySelectorAll("input[type=hidden]"),
        function (inp) {
          return inp.value;
        }
      );
    }

    function labelFor(item) {
      if (kind === "country")
        return (item.name_fa || item.name || item.country_code) + " (" + item.country_code + ")";
      if (kind === "topic") return (item.name || "") + " #" + item.topic_id;
      return (item.name || item.language_code) + " (" + item.language_code + ")";
    }

    function valueFor(item) {
      if (kind === "country") return item.country_code;
      if (kind === "topic") return String(item.topic_id);
      return item.language_code;
    }

    function syncChips() {
      chipsEl.innerHTML = "";
      selectedValues().forEach(function (val) {
        var li = document.createElement("li");
        li.className = "chip";
        li.textContent = val;
        var btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = "×";
        btn.addEventListener("click", function () {
          hiddenWrap.querySelectorAll('input[value="' + val + '"]').forEach(function (n) {
            n.remove();
          });
          syncChips();
          dispatchInput(root);
        });
        li.appendChild(btn);
        chipsEl.appendChild(li);
      });
    }

    var runSearch = debounce(function () {
      var q = (search.value || "").trim().toLowerCase();
      if (q.length < 1) return;
      var picked = selectedValues();
      catalog
        .filter(function (item) {
          var label = labelFor(item).toLowerCase();
          return label.indexOf(q) >= 0 || valueFor(item).toLowerCase().indexOf(q) >= 0;
        })
        .slice(0, 8)
        .forEach(function (item) {
          var val = valueFor(item);
          if (picked.indexOf(val) >= 0) return;
          if (kind === "country" && picked.length >= 8) return;
          var inp = document.createElement("input");
          inp.type = "hidden";
          inp.name = root.getAttribute("data-field");
          inp.value = val;
          hiddenWrap.appendChild(inp);
          syncChips();
          dispatchInput(root);
          search.value = "";
        });
    }, 280);

    search.addEventListener("input", runSearch);
    search.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        runSearch();
      }
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
        timezone: parseInt(root.getAttribute("data-timezone") || "12600", 10),
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

  function initLocationPicker(form) {
    var root = form.querySelector("[data-location-picker]");
    if (!root) return;
    var search = root.querySelector("[data-location-search]");
    var results = root.querySelector("[data-location-results]");
    var chips = root.querySelector("[data-location-chips]");
    var hiddenWrap = root.querySelector("[data-location-hidden]");
    var base = form.getAttribute("data-catalog-locations");
    if (!search || !results || !chips || !hiddenWrap || !base) return;

    function countries() {
      var ms = form.querySelector('[data-field="country_codes"]');
      if (!ms) return "";
      var inp = ms.querySelector("[data-ms-hidden] input");
      return inp ? inp.value : "";
    }

    var queryLocations = debounce(function () {
      var country = countries();
      var q = (search.value || "").trim();
      if (!country || q.length < 2) {
        results.innerHTML = "";
        return;
      }
      fetch(base + "?country=" + encodeURIComponent(country) + "&q=" + encodeURIComponent(q), {
        credentials: "same-origin",
      })
        .then(function (r) {
          return r.json();
        })
        .then(function (j) {
          results.innerHTML = "";
          (j.items || []).forEach(function (loc) {
            var li = document.createElement("li");
            li.className = "catalog-suggest__item";
            li.textContent = (loc.name || "") + (loc.region ? " — " + loc.region : "");
            li.addEventListener("click", function () {
              var exists = hiddenWrap.querySelector('input[value="' + loc.location_id + '"]');
              if (!exists) {
                var inp = document.createElement("input");
                inp.type = "hidden";
                inp.name = "location_ids";
                inp.value = loc.location_id;
                hiddenWrap.appendChild(inp);
                var chip = document.createElement("li");
                chip.className = "chip";
                chip.textContent = loc.name + " (#" + loc.location_id + ")";
                chips.appendChild(chip);
                dispatchInput(root);
              }
              search.value = "";
              results.innerHTML = "";
            });
            results.appendChild(li);
          });
        });
    }, 350);

    search.addEventListener("input", queryLocations);
  }

  function initPolicyRefresh(form) {
    var url = form.getAttribute("data-policy-preview-url");
    var btn = form.querySelector("[data-policy-refresh]");
    var status = form.querySelector("[data-policy-refresh-status]");
    if (!url || !btn) return;
    btn.addEventListener("click", function () {
      if (status) status.textContent = "در حال بررسی…";
      var data = new FormData(form);
      data.delete("creative_media");
      fetch(url, { method: "POST", body: data, credentials: "same-origin" })
        .then(function (r) {
          return r.json();
        })
        .then(function (j) {
          if (!j.ok) {
            if (status) status.textContent = j.message || "خطا";
            return;
          }
          var blocked = (j.counts && j.counts.blocked) || 0;
          var review = (j.counts && j.counts.review_required) || 0;
          if (status)
            status.textContent = j.ready
              ? "از نظر ساختاری آماده است."
              : blocked + " مسدود · " + review + " نیازمند بررسی";
        })
        .catch(function () {
          if (status) status.textContent = "بررسی ناموفق";
        });
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
