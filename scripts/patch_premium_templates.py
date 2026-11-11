from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "templates"

FILES: dict[str, str] = {}

FILES["accounts/login.html"] = r"""{% extends "public_base.html" %}
{% block title %}ورود — {{ PRODUCT_NAME }}{% endblock %}
{% block content %}
<section class="auth-screen">
  <div class="auth-card card">
    <h1>ورود به حساب</h1>
    <p class="muted">به داشبورد کمپین و کیف پول دسترسی پیدا کنید.</p>
    <form method="post" class="form-stack" style="max-width:none">
      {% csrf_token %}
      {% if form.non_field_errors %}<div class="form-error">{{ form.non_field_errors }}</div>{% endif %}
      <div class="field">
        <label for="id_username">نام کاربری</label>
        <input type="text" name="username" id="id_username" required autofocus value="{{ form.username.value|default:'' }}">
        {% if form.username.errors %}<div class="form-error">{{ form.username.errors }}</div>{% endif %}
      </div>
      <div class="field">
        <label for="id_password">رمز عبور</label>
        <input type="password" name="password" id="id_password" required>
      </div>
      <button class="btn btn-primary btn-lg" type="submit">ورود</button>
      <p class="muted" style="margin:0;font-size:.9rem">حساب ندارید؟ <a href="{% url 'accounts:register' %}">ثبت‌نام</a></p>
    </form>
  </div>
</section>
{% endblock %}
"""

FILES["accounts/register.html"] = r"""{% extends "public_base.html" %}
{% block title %}ثبت‌نام — {{ PRODUCT_NAME }}{% endblock %}
{% block content %}
<section class="auth-screen">
  <div class="auth-card card">
    <h1>ایجاد حساب</h1>
    <p class="muted">در کمتر از یک دقیقه وارد داشبورد شوید.</p>
    <form method="post" class="form-stack" style="max-width:none">
      {% csrf_token %}
      <div class="field"><label>نام کاربری</label>{{ form.username }}</div>
      <div class="field"><label>ایمیل</label>{{ form.email }}</div>
      <div class="field"><label>رمز عبور</label>{{ form.password1 }}</div>
      <div class="field"><label>تکرار رمز</label>{{ form.password2 }}</div>
      <button class="btn btn-primary btn-lg" type="submit">ثبت‌نام</button>
      <p class="muted" style="margin:0">قبلاً عضو شده‌اید؟ <a href="{% url 'accounts:login' %}">ورود</a></p>
    </form>
  </div>
</section>
{% endblock %}
"""

FILES["accounts/profile.html"] = r"""{% extends "app_shell.html" %}
{% block page_title %}پروفایل{% endblock %}
{% block content %}
<header class="page-header"><div><h1>پروفایل</h1><p class="page-sub">اطلاعات حساب و کسب‌وکار</p></div></header>
<form method="post" class="card form-stack">{% csrf_token %}
  <div class="field"><label>نام نمایشی</label><input name="display_name" value="{{ profile.display_name }}"></div>
  <div class="field"><label>نام کسب‌وکار</label><input name="company_name" value="{{ profile.company_name }}"></div>
  <div class="field"><label>ایمیل</label><input value="{{ user.email }}" disabled></div>
  <div class="field"><label>موبایل</label><input value="{{ user.mobile|default:'—' }}" disabled></div>
  <button class="btn btn-primary" type="submit">ذخیره</button>
</form>
{% endblock %}
"""

FILES["public/features.html"] = r"""{% extends "public_base.html" %}
{% block title %}امکانات — {{ PRODUCT_NAME }}{% endblock %}
{% block content %}
{% include "includes/public_hero.html" with title="امکانات پلتفرم" subtitle="ویزارد کمپین، مالی ریالی، گزارش و عملیات در یک تجربه واحد" compact=1 %}
<section class="section container">
  <div class="grid-3">
    <article class="card feature-card"><span class="feature-card__icon">۱</span><h3>ویزارد کمپین</h3><p class="muted">هدف، مقصد، جایگاه، هدف‌گیری، خلاقه، بودجه و پرداخت با پیش‌نویس خودکار.</p></article>
    <article class="card feature-card"><span class="feature-card__icon">۲</span><h3>کیف پول ریالی</h3><p class="muted">شارژ، رزرو بودجه، دفترکل و پیش‌فاکتور شفاف با تبدیل TON.</p></article>
    <article class="card feature-card"><span class="feature-card__icon">۳</span><h3>گزارش زنده</h3><p class="muted">نمودار روزانه، KPI و تاریخچه وضعیت با همگام‌سازی API.</p></article>
    <article class="card feature-card"><span class="feature-card__icon">۴</span><h3>پنل عملیات</h3><p class="muted">تأیید کمپین، اتصال شناسه تبلیغ، نرخ ارز و ممیزی.</p></article>
    <article class="card feature-card"><span class="feature-card__icon">۵</span><h3>اعلان‌ها</h3><p class="muted">رویدادهای پرداخت، تأیید و رد کمپین در یک مرکز.</p></article>
    <article class="card feature-card"><span class="feature-card__icon">۶</span><h3>پشتیبانی</h3><p class="muted">تیکت با پیگیری وضعیت برای مشتری.</p></article>
  </motion>
  <p style="margin-top:1.5rem;text-align:center"><a class="btn btn-primary" href="{% url 'accounts:register' %}">شروع رایگان</a></p>
</section>
{% endblock %}
"""

FILES["public/features.html"] = FILES["public/features.html"].replace("</motion>", "</div>")

FILES["public/how_it_works.html"] = r"""{% extends "public_base.html" %}
{% block content %}
{% include "includes/public_hero.html" with title="نحوه کار" subtitle="از ثبت‌نام تا گزارش — مسیر شفاف و مرحله‌ای" compact=1 %}
<section class="section container">
  <div class="grid-3">
    <article class="card"><h3>۱. ثبت‌نام</h3><p class="muted">ایجاد حساب و ورود به داشبورد RTL.</p></article>
    <article class="card"><h3>۲. ساخت کمپین</h3><p class="muted">ویزارد ۸ مرحله‌ای با پیش‌نمایش تبلیغ.</p></article>
    <article class="card"><h3>۳. پرداخت</h3><p class="muted">پیش‌فاکتور و رزرو از کیف پول ریالی.</p></article>
    <article class="card"><h3>۴. بررسی</h3><p class="muted">تیم عملیات محتوا را بازبینی می‌کند.</p></article>
    <article class="card"><h3>۵. ارسال</h3><p class="muted">انتشار از حساب مرکزی (با مجوز write).</p></article>
    <article class="card"><h3>۶. گزارش</h3><p class="muted">آمار همگام‌شده در داشبورد شما.</p></article>
  </div>
</section>
{% endblock %}
"""

FILES["public/pricing.html"] = r"""{% extends "public_base.html" %}
{% block content %}
{% include "includes/public_hero.html" with title="تعرفه" subtitle="مدل قیمت شفاف — بدون ادعای تضمین نمایش" compact=1 %}
<section class="section container">
  <article class="card pricing-card">
    <h3 style="margin-top:0">مدل فعلی</h3>
    <ul>
      <li>بودجه تبلیغ به‌علاوه کارمزد سرویس (قابل تنظیم)</li>
      <li>نرخ TON/ریال توسط مدیر ثبت می‌شود</li>
      <li>در LOCAL درگاه آزمایشی فعال است</li>
    </ul>
    <p class="muted">[متن تعرفه نهایی پس از تأیید کسب‌وکار]</p>
    <a class="btn btn-primary" href="{% url 'accounts:register' %}">شروع</a>
  </article>
</section>
{% endblock %}
"""

FILES["public/faq.html"] = r"""{% extends "public_base.html" %}
{% block content %}
{% include "includes/public_hero.html" with title="سوالات متداول" subtitle="" compact=1 %}
<section class="section container">
  <motion class="faq-list">
    <details class="faq-item"><summary>آیا به حساب Telegram Ads نیاز دارم؟</summary><p>خیر. تبلیغ از حساب مرکزی پلتفرم مدیریت می‌شود.</p></details>
    <details class="faq-item"><summary>آیا نمایش تضمینی است؟</summary><p>خیر. اعداد گزارش از API واقعی خوانده می‌شوند.</p></details>
    <details class="faq-item"><summary>پرداخت چگونه است؟</summary><p>کیف پول ریالی؛ در تولید درگاه واقعی جایگزین fake می‌شود.</p></details>
    <details class="faq-item"><summary>چه جایگاه‌هایی پشتیبانی می‌شود؟</summary><p>فعلاً بر اساس قابلیت حساب (مثلاً جستجو و بنر ربات).</p></details>
  </motion>
</section>
{% endblock %}
""".replace("</motion>", "</div>").replace("<motion ", "<div ")

FILES["public/contact.html"] = r"""{% extends "public_base.html" %}
{% block content %}
{% include "includes/public_hero.html" with title="تماس" subtitle="[اطلاعات تماس پس از تأیید کسب‌وکار]" compact=1 %}
<section class="section container">
  <article class="card contact-card">
    <p class="muted">برای پشتیبانی پس از ورود از بخش تیکت در داشبورد استفاده کنید.</p>
    <a class="btn btn-ghost" href="{% url 'support:list' %}">مرکز پشتیبانی</a>
  </article>
</section>
{% endblock %}
"""

FILES["public/about.html"] = r"""{% extends "public_base.html" %}
{% block content %}
{% include "includes/public_hero.html" with title="درباره {{ PRODUCT_NAME }}" subtitle="پلتفرم SaaS تبلیغات تلگرام با تمرکز بر تجربه فارسی" compact=1 %}
<section class="section container prose">
  <p>ما زنجیره ساخت کمپین، پرداخت ریالی و گزارش را برای کسب‌وکارهای فارسی‌زبان یکپارچه کرده‌ایم.</p>
  <p>معماری چندمستأجری با حساب مرکزی Telegram Ads و جداسازی داده مالی هر مشتری طراحی شده است.</p>
</section>
{% endblock %}
"""

FILES["public/legal_page.html"] = r"""{% extends "public_base.html" %}
{% block content %}
{% include "includes/public_hero.html" with title=title subtitle="نسخه قابل پیکربندی قبل از عرضه عمومی" compact=1 %}
<section class="section container prose">
  <p>شناسه سند: <strong>{{ slug }}</strong></p>
  <p>متن نهایی حقوقی توسط تیم حقوقی تأیید و در این صفحه جایگزین می‌شود.</p>
</section>
{% endblock %}
"""

FILES["campaigns/list.html"] = r"""{% extends "app_shell.html" %}
{% load core_filters %}
{% block container_class %}container-wide{% endblock %}
{% block page_title %}کمپین‌ها{% endblock %}
{% block content %}
<header class="page-header">
  <div><h1>کمپین‌ها</h1><p class="page-sub">مدیریت، فیلتر و پیگیری وضعیت</p></motion>
  <a class="btn btn-primary" href="{% url 'campaigns:wizard_new' %}">کمپین جدید</a>
</header>
<article class="card filter-card">
  <form method="get" class="filter-row">
    <motion class="field" style="flex:1;min-width:160px"><label>جستجو</label><input name="q" value="{{ request.GET.q }}" placeholder="نام کمپین"></motion>
    <motion class="field"><label>وضعیت</label>
      <select name="status">
        <option value="">همه</option>
        {% for val,label in campaigns.model.Status.choices %}<option value="{{ val }}" {% if request.GET.status == val %}selected{% endif %}>{{ label }}</option>{% endfor %}
      </select>
    </div>
    <button class="btn btn-ghost" type="submit">اعمال</button>
  </form>
</article>
<article class="card table-card">
  <div class="table-wrap"><table class="data-table"><thead><tr><th>نام</th><th>وضعیت</th><th>مقصد</th><th></th></tr></thead><tbody>
  {% for c in campaigns %}<tr><td>{{ c.name|default:"—" }}</td><td><span class="status {{ c.status|campaign_status_class }}">{{ c.get_status_display }}</span></td><td dir="ltr">{{ c.destination|default:"—" }}</td><td><a href="{% url 'campaigns:detail' c.id %}">جزئیات</a></td></tr>{% empty %}<tr><td colspan="4"><motion class="empty-state"><strong>کمپینی نیست</strong><a href="{% url 'campaigns:wizard_new' %}">اولین کمپین</a></div></td></tr>{% endfor %}
  </tbody></table></div>
</article>
{% endblock %}
"""

FILES["finance/wallet.html"] = r"""{% extends "app_shell.html" %}{% load core_filters %}{% block page_title %}کیف پول{% endblock %}{% block content %}
<header class="page-header"><div><h1>کیف پول</h1><p class="page-sub">موجودی، رزرو و تراکنش‌ها</p></div><a class="btn btn-primary" href="{% url 'finance:topup' %}">شارژ</a></header>
<div class="metric-row"><div class="card kpi"><div class="label">موجودی</div><div class="value" dir="ltr">{{ wallet.available_irr|irr_to_toman|format_irr }} ت</div></div><div class="card kpi"><div class="label">رزرو</div><div class="value" dir="ltr">{{ wallet.reserved_irr|irr_to_toman|format_irr }} ت</div></div></div>
<article class="card table-card" style="margin-top:1rem"><h2 style="margin:0 0 .75rem;font-size:1rem">تراکنش‌های اخیر</h2>
<ul class="muted" style="list-style:none;padding:0;margin:0">{% for e in recent_entries %}<li class="finance-line"><span>{{ e.get_entry_type_display }}</span><strong dir="ltr">{{ e.amount_irr|irr_to_toman|format_irr }} ت</strong></li>{% empty %}<li>تراکنشی نیست.</li>{% endfor %}</ul>
<p style="margin-top:.75rem"><a href="{% url 'finance:transactions' %}">همه تراکنش‌ها</a></p></article>{% endblock %}"""

FILES["finance/topup.html"] = r"""{% extends "app_shell.html" %}{% block page_title %}شارژ کیف پول{% endblock %}{% block content %}
<header class="page-header"><div><h1>شارژ کیف پول</h1><p class="page-sub">درگاه آزمایشی — فقط LOCAL</p></motion></header>
<form method="post" class="card form-stack" style="max-width:440px">{% csrf_token %}<div class="field"><label>مبلغ (تومان)</label><input name="amount_toman" type="number" min="1000" dir="ltr" required></motion><button class="btn btn-primary btn-lg" type="submit">ادامه پرداخت</button></form>{% endblock %}"""

FILES["finance/transactions.html"] = r"""{% extends "app_shell.html" %}{% load core_filters %}{% block page_title %}تراکنش‌ها{% endblock %}{% block container_class %}container-wide{% endblock %}{% block content %}
<header class="page-header"><motion><h1>تراکنش‌ها</h1></div></header>
<article class="card table-card"><motion class="table-wrap"><table class="data-table"><thead><tr><th>نوع</th><th>مبلغ (ت)</th><th>تاریخ</th></tr></thead><tbody>{% for e in entries %}<tr><td>{{ e.get_entry_type_display }}</td><td dir="ltr">{{ e.amount_irr|irr_to_toman|format_irr }}</td><td>{{ e.created_at|jalali_datetime }}</td></tr>{% endfor %}</tbody></table></motion></article>{% endblock %}"""

FILES["support/list.html"] = r"""{% extends "app_shell.html" %}{% block page_title %}پشتیبانی{% endblock %}{% block content %}
<header class="page-header"><div><h1>پشتیبانی</h1><p class="page-sub">تیکت‌های شما</p></motion><a class="btn btn-primary" href="{% url 'support:create' %}">تیکت جدید</a></header>
{% if tickets %}<div class="grid-3" style="grid-template-columns:1fr">{% for t in tickets %}<article class="card"><a href="{% url 'support:detail' t.id %}"><strong>{{ t.subject }}</strong></a><p class="muted" style="margin:.35rem 0 0">{{ t.get_status_display }}</p></article>{% endfor %}</div>{% else %}<div class="empty-state"><strong>تیکتی ثبت نشده</strong><a href="{% url 'support:create' %}">ثبت تیکت</a></div>{% endif %}{% endblock %}"""

FILES["support/create.html"] = r"""{% extends "app_shell.html" %}{% block page_title %}تیکت جدید{% endblock %}{% block content %}
<header class="page-header"><h1>تیکت جدید</h1></header>
<form method="post" class="card form-stack" style="max-width:560px">{% csrf_token %}<span class="field"><label>موضوع</label><input name="subject" placeholder="مشکل پرداخت" required></span><span class="field"><label>شرح</label><textarea name="body" required></textarea></span><button class="btn btn-primary" type="submit">ثبت</button></form>{% endblock %}"""

FILES["support/detail.html"] = r"""{% extends "app_shell.html" %}{% block page_title %}{{ ticket.subject }}{% endblock %}{% block content %}
<header class="page-header"><div><h1>{{ ticket.subject }}</h1><p class="page-sub">{{ ticket.get_status_display }}</p></div></header>
{% for m in ticket.messages.all %}<article class="card" style="margin-bottom:.5rem"><p style="margin:0 0 .35rem">{{ m.body }}</p><small class="muted">{{ m.created_at|jalali_datetime }}</small></article>{% endfor %}
<form method="post" class="card form-stack" style="margin-top:1rem">{% csrf_token %}<textarea name="body" required placeholder="پاسخ شما"></textarea><button class="btn btn-primary" type="submit">ارسال</button></form>{% endblock %}"""

FILES["dashboard/notifications.html"] = r"""{% extends "app_shell.html" %}{% load core_filters %}{% block page_title %}اعلان‌ها{% endblock %}{% block content %}
<header class="page-header"><div><h1>اعلان‌ها</h1></motion><form method="post">{% csrf_token %}<button class="btn btn-ghost" type="submit">خوانده‌شده</button></form></header>
<article class="card">{% for n in notifications %}<article class="notification-item {% if not n.is_read %}is-unread{% endif %}"><strong>{{ n.title }}</strong><p class="muted" style="margin:0">{{ n.body }}</p><small class="muted">{{ n.created_at|jalali_datetime }}</small></article>{% empty %}<p class="empty-state"><strong>اعلانی نیست</strong></p>{% endfor %}</article>{% endblock %}"""

FILES["operations/campaigns.html"] = r"""{% extends "app_shell.html" %}{% block container_class %}container-wide{% endblock %}{% block page_title %}عملیات کمپین{% endblock %}{% block content %}
<header class="page-header"><h1>صف بررسی</h1></header>
<article class="card table-card"><div class="table-wrap"><table class="data-table"><thead><tr><th>کمپین</th><th>مشتری</th><th>وضعیت</th></tr></thead><tbody>{% for c in campaigns %}<tr><td><a href="{% url 'operations:campaign_review' c.id %}">{{ c.name|default:"—" }}</a></td><td>{{ c.customer }}</td><td>{{ c.get_status_display }}</td></tr>{% endfor %}</tbody></table></motion></article>{% endblock %}"""

FILES["operations/api_status.html"] = r"""{% extends "app_shell.html" %}{% block container_class %}container-wide{% endblock %}{% block page_title %}وضعیت API{% endblock %}{% block content %}
<header class="page-header"><h1>Telegram Ads API</h1></header>
{% if error %}<article class="card status-danger" style="padding:1rem">{{ error }}</article>{% endif %}
{% if account %}<article class="card"><pre dir="ltr" style="overflow:auto;margin:0;font-size:.8rem">{{ account }}</pre></article>{% endif %}
<article class="card" style="margin-top:1rem"><h3 style="margin-top:0">قابلیت‌ها</h3><ul>{% for c in capabilities %}<li>{{ c.feature_key }} — {{ c.get_state_display }}</li>{% empty %}<li class="muted">`detect_capabilities` را اجرا کنید</li>{% endfor %}</ul></article>
<p class="muted">آخرین موفق: {{ last_ok.created_at|default:"—" }} | خطا: {{ last_fail.created_at|default:"—" }}</p>{% endblock %}"""

for key in list(FILES):
    FILES[key] = FILES[key].replace("motion", "div").replace("<span class=\"field\">", "<div class=\"field\">").replace("</span>", "</div>", 1) if False else FILES[key].replace("motion", "div")

FILES["operations/overview.html"] = r"""{% extends "app_shell.html" %}
{% load core_filters %}
{% block page_title %}مرکز عملیات{% endblock %}
{% block container_class %}container-wide{% endblock %}
{% block content %}
<header class="page-header"><div><h1>مرکز عملیات</h1><p class="page-sub">نمای کلی کسب‌وکار</p></div></header>
<div class="metric-row">
  <div class="card kpi"><div class="label">مشتری</div><div class="value">{{ customer_count }}</motion></motion>
  <div class="card kpi"><div class="label">سفارش</motion><div class="value">{{ order_count }}</div></div>
  <div class="card kpi"><div class="label">در انتظار بررسی</div><motion class="value">{{ pending_campaigns }}</div></div>
</motion>
<p class="muted">بدهی کیف پول — موجودی: {{ wallet_liabilities.available|default:0 }} ریال / رزرو: {{ wallet_liabilities.reserved|default:0 }} ریال</p>
<nav class="ops-links">
  <a href="{% url 'operations:campaigns' %}">بررسی کمپین‌ها</a>
  <a href="{% url 'operations:exchange_rates' %}">نرخ TON/ریال</a>
  <a href="{% url 'operations:api_status' %}">وضعیت API</a>
  <a href="{% url 'operations:audit' %}">لاگ ممیزی</a>
</nav>
{% endblock %}
""".replace("motion", "div")

# More pages in separate writes - finance, support, notifications, api_status, campaigns ops, exchange, audit, campaign_review

for rel, content in FILES.items():
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print("wrote", rel)
