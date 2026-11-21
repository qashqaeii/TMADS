(function () {
  "use strict";

  function node(tag, cls, text) {
    var el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text !== undefined) el.textContent = text;
    return el;
  }

  function renderCreative(root, payload, editor, status) {
    if (!editor || !Array.isArray(payload.variants)) return;
    payload.variants.forEach(function (text, index) {
      if (typeof text !== "string") return;
      var card = node("article", "tm-ai-option");
      var head = node("div", "tm-ai-option-head");
      head.append(
        node("strong", "", "پیشنهاد " + (index + 1).toLocaleString("fa-IR")),
        node("small", "", Array.from(text).length.toLocaleString("fa-IR") + " / ۱۶۰")
      );
      var copy = node("p", "", text);
      var apply = node("button", "btn btn-ghost", "انتخاب متن");
      apply.type = "button";
      apply.addEventListener("click", function () {
        editor.value = text;
        editor.dispatchEvent(new Event("input", { bubbles: true }));
        editor.dispatchEvent(new Event("change", { bubbles: true }));
        status.textContent = "پیشنهاد در پیش‌نویس قرار گرفت؛ پیش از ادامه آن را بررسی کنید.";
        editor.focus();
      });
      card.append(head, copy, apply);
      root.append(card);
    });
  }

  function renderAnalysis(root, payload) {
    if (typeof payload.summary !== "string" || !Array.isArray(payload.actions)) return;
    var summary = node("article", "tm-ai-option tm-ai-summary");
    summary.append(node("strong", "", "جمع‌بندی"), node("p", "", payload.summary));
    if (payload.as_of) {
      var date = new Date(payload.as_of);
      if (!isNaN(date.getTime())) {
        summary.append(node(
          "small",
          "tm-ai-hint",
          "زمان آخرین آمار: " + date.toLocaleString("fa-IR", { timeZone: "Asia/Tehran" })
        ));
      }
    }
    root.append(summary);
    var actions = node("div", "tm-ai-actions");
    payload.actions.forEach(function (item, index) {
      if (!item || typeof item.title !== "string" || typeof item.body !== "string") return;
      var row = node("article", "tm-ai-option tm-ai-action");
      var number = node("span", "tm-ai-action-number", (index + 1).toLocaleString("fa-IR"));
      var body = node("div", "");
      body.append(node("strong", "", item.title), node("p", "", item.body));
      row.append(number, body);
      actions.append(row);
    });
    root.append(actions);
  }

  function renderPlanner(root, payload, form, status) {
    var plan = payload.plan;
    if (!plan || typeof plan.campaign_name !== "string" || typeof plan.target_type !== "string") return;
    var card = node("article", "tm-ai-option tm-ai-plan");
    var head = node("div", "tm-ai-option-head");
    head.append(
      node("strong", "", plan.campaign_name),
      node("span", "tm-ai-plan-target", plan.target_type_label || "پیشنهاد هدف‌گیری")
    );
    card.append(head);
    var grid = node("div", "tm-ai-plan-grid");
    [
      ["دلیل پیشنهاد", plan.reason],
      ["تصویر مخاطب", plan.audience_summary],
      ["جهت محتوای تبلیغ", plan.creative_direction]
    ].forEach(function (item) {
      if (typeof item[1] !== "string" || !item[1]) return;
      var block = node("div", "tm-ai-plan-item");
      block.append(node("strong", "", item[0]), node("p", "", item[1]));
      grid.append(block);
    });
    if (grid.childElementCount) card.append(grid);
    if (Array.isArray(plan.missing_information) && plan.missing_information.length) {
      var missing = node("div", "tm-ai-plan-missing");
      missing.append(node("strong", "", "مواردی که بهتر است مشخص کنید"));
      var list = node("ul", "");
      plan.missing_information.forEach(function (item) {
        if (typeof item === "string" && item) list.append(node("li", "", item));
      });
      missing.append(list);
      card.append(missing);
    }
    var apply = node("button", "btn btn-primary", "اعمال پیشنهاد روی پیش‌نویس");
    apply.type = "button";
    apply.addEventListener("click", function () {
      var name = form && form.querySelector('[name="campaign_name"]');
      var target = form && Array.from(form.querySelectorAll('[name="target_type"]')).find(function (input) {
        return input.value === plan.target_type;
      });
      if (!name || !target) {
        status.textContent = "فیلدهای پیش‌نویس برای اعمال پیشنهاد در دسترس نیستند.";
        return;
      }
      name.value = plan.campaign_name;
      name.dispatchEvent(new Event("input", { bubbles: true }));
      name.dispatchEvent(new Event("change", { bubbles: true }));
      target.checked = true;
      target.dispatchEvent(new Event("change", { bubbles: true }));
      status.textContent = "پیشنهاد روی پیش‌نویس اعمال شد؛ مقصد و تنظیمات هدف‌گیری را خودتان تکمیل و بررسی کنید.";
      name.focus();
    });
    card.append(apply);
    root.append(card);
  }

  function renderOptimization(root, payload) {
    if (typeof payload.summary !== "string" || !Array.isArray(payload.recommendations)) return;
    var summary = node("article", "tm-ai-option tm-ai-summary");
    summary.append(node("strong", "", "جمع‌بندی بهینه‌سازی"), node("p", "", payload.summary));
    root.append(summary);
    var recommendations = node("div", "tm-ai-actions tm-ai-optimization-list");
    payload.recommendations.forEach(function (item) {
      if (!item || typeof item.title !== "string" || typeof item.reason !== "string") return;
      var card = node("article", "tm-ai-option tm-ai-optimization-item");
      var head = node("div", "tm-ai-option-head");
      head.append(
        node("strong", "", item.title),
        node("span", "tm-ai-priority", item.priority_label || "پیشنهاد")
      );
      card.append(head, node("p", "", item.reason), node("small", "tm-ai-hint", item.next_step || ""));
      recommendations.append(card);
    });
    if (recommendations.childElementCount) root.append(recommendations);
  }

  function init(root) {
    var button = root.querySelector("[data-ai-generate]");
    var label = root.querySelector("[data-ai-label]");
    var status = root.querySelector("[data-ai-status]");
    var results = root.querySelector("[data-ai-results]");
    var form = root.closest("form") || root.querySelector("form");
    var csrf = form && form.querySelector("[name=csrfmiddlewaretoken]");
    var editor = form && form.querySelector('[name="ad_text"]');
    var brief = root.querySelector("[data-ai-brief]");
    var audience = root.querySelector("[data-ai-audience]");
    var goal = root.querySelector("[data-ai-goal]");

    if (!button || !label || !status || !results || !csrf || !root.dataset.aiUrl) return;
    [brief, audience, goal].filter(Boolean).forEach(function (field) {
      ["input", "change"].forEach(function (event) {
        field.addEventListener(event, function (e) { e.stopPropagation(); });
      });
    });
    root.hidden = false;

    button.addEventListener("click", async function () {
      if (button.disabled) return;
      var kind = root.dataset.tmAi;
      if (kind === "planner" && (!brief || !brief.value.trim())) {
        status.textContent = "ابتدا توضیح کوتاهی درباره محصول یا خدمت وارد کنید.";
        if (brief) brief.focus();
        return;
      }
      if (kind === "creative" && editor && !editor.value.trim() && brief && !brief.value.trim()) {
        status.textContent = "توضیح کوتاهی وارد کنید.";
        brief.focus();
        return;
      }

      var original = label.textContent;
      button.disabled = true;
      label.textContent = "در حال آماده‌سازی…";
      root.setAttribute("aria-busy", "true");
      status.textContent = "در حال دریافت پیشنهاد…";
      results.hidden = true;
      results.replaceChildren();

      var data = new URLSearchParams();
      if (brief) data.set("brief", brief.value);
      if (audience) data.set("audience", audience.value);
      if (goal) data.set("goal", goal.value);
      if (editor) data.set("current", editor.value);
      data.set("csrfmiddlewaretoken", csrf.value);

      var controller = new AbortController();
      var timeout = setTimeout(function () { controller.abort(); }, 30_000);
      try {
        var response = await fetch(root.dataset.aiUrl, {
          method: "POST",
          body: data,
          credentials: "same-origin",
          signal: controller.signal,
          headers: { "Accept": "application/json" }
        });
        var payload = await response.json();
        if (!response.ok || !payload.ok) {
          status.textContent = payload.message || "دریافت پیشنهاد ممکن نیست.";
          return;
        }

        if (kind === "creative") renderCreative(results, payload, editor, status);
        if (kind === "analysis") renderAnalysis(results, payload);
        if (kind === "planner") renderPlanner(results, payload, form, status);
        if (kind === "optimization") renderOptimization(results, payload);

        if (!results.childElementCount) {
          status.textContent = "پیشنهاد قابل استفاده‌ای دریافت نشد.";
          return;
        }
        results.hidden = false;
        if (kind !== "planner" || !status.textContent.includes("اعمال شد")) {
          status.textContent = payload.cached
            ? "نتیجه ذخیره‌شده نمایش داده شد."
            : "پیشنهاد آماده است؛ پیش از استفاده آن را بررسی کنید.";
        }
      } catch (error) {
        status.textContent = controller.signal.aborted
          ? "زمان پاسخ‌گویی تمام شد؛ دوباره تلاش کنید."
          : "ارتباط با دستیار برقرار نشد. بدون دستیار ادامه دهید.";
      } finally {
        clearTimeout(timeout);
        button.disabled = false;
        label.textContent = original;
        root.removeAttribute("aria-busy");
      }
    });
  }

  function boot() {
    document.querySelectorAll("[data-tm-ai]").forEach(init);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
