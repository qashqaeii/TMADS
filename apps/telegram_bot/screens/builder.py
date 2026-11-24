from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from telebot import types

from apps.accounts.models import CustomerProfile
from apps.campaigns.models import Campaign
from apps.core.dates import jalali_datetime_string
from apps.finance.models import WalletLedgerEntry

from ..formatters import escape_html, format_int, format_pct, format_toman, named_site_url
from ..keyboards import attach_nav, inline_grid
from ..navigation import ADMIN_HOME, GUEST_HOME, HOME
from ..permissions import active_customer_link, active_staff_link, user_may_use_admin_panel
from ..services import admin_data, customer_data


@dataclass
class Screen:
    text: str
    keyboard: types.InlineKeyboardMarkup


def _status_label(campaign: Campaign) -> str:
    return campaign.get_status_display()


def build_screen(screen_id: str, *, telegram_user_id: int, session) -> Screen:
    link = active_customer_link(telegram_user_id)
    staff = active_staff_link(telegram_user_id)
    customer = link.customer if link else None

    if screen_id in (GUEST_HOME, "c:guest:link"):
        if screen_id == "c:guest:link":
            return _guest_link_help()
        return _guest_home(link, staff)
    if screen_id == HOME:
        if not customer:
            return _guest_home(link, staff)
        return _customer_dashboard(customer, staff)
    if screen_id == ADMIN_HOME:
        return _admin_home(staff)
    if not customer and screen_id.startswith("c:"):
        return _guest_home(link, staff, note="برای دسترسی، ابتدا حساب گرام‌ادز را متصل کنید.")
    if screen_id.startswith("a:") and not (staff and user_may_use_admin_panel(staff.user)):
        return Screen("⛔️ دسترسی مدیریتی برای این حساب تلگرام فعال نیست.", inline_grid([("🏠 خانه", "nav:home")]))

    if screen_id == "c:dash":
        return _customer_dashboard(customer, staff)
    if screen_id == "c:cmp":
        return _campaigns_menu(customer)
    if screen_id.startswith("c:cmp:l:"):
        parts = screen_id.split(":")
        filt = parts[3] if len(parts) > 3 else "all"
        page = int(parts[5]) if len(parts) > 5 and parts[4] == "p" else 0
        return _campaigns_list(customer, session, filt, page)
    if screen_id.startswith("c:cmp:v:"):
        idx = int(screen_id.split(":")[-1])
        return _campaign_detail(customer, session, idx)
    if screen_id == "c:wallet":
        return _wallet_menu(customer)
    if screen_id == "c:conn":
        return _connections_menu(customer)
    if screen_id == "c:reports":
        return _reports_menu(customer)
    if screen_id == "c:notif":
        return _notifications_menu(customer)
    if screen_id == "c:support":
        return _support_menu(customer)
    if screen_id == "c:ai":
        return _ai_menu(customer)
    if screen_id == "c:settings":
        return _settings_menu(customer, link, session)
    if screen_id == "c:set:disc":
        return _disconnect_confirm(link)
    if screen_id == "c:set:devices":
        return _devices_list(customer)
    if screen_id == "c:set:notify":
        return _notify_prefs(link)

    if screen_id == "a:dash":
        return _admin_dashboard()
    if screen_id == "a:cmp":
        return _admin_campaigns()
    if screen_id == "a:users":
        return _admin_users()
    if screen_id == "a:fin":
        return _admin_finance()
    if screen_id == "a:fund":
        return _admin_funding()
    if screen_id == "a:ads":
        return _admin_review_queue()
    if screen_id == "a:tickets":
        return _admin_tickets()
    if screen_id == "a:stats":
        return _admin_stats()
    if screen_id == "a:svc":
        return _admin_services()

    return _customer_dashboard(customer, staff) if customer else _guest_home(link, staff)


def _guest_link_help() -> Screen:
    lines = [
        "🔗 <b>اتصال حساب</b>",
        "۱. وارد پنل گرام‌ادز شوید",
        "۲. از پروفایل، «اتصال ربات تلگرام» را بزنید",
        "۳. کد یک‌بارمصرف را در ربات با /start ارسال کنید",
        "",
        "رمز عبور یا توکن API را هرگز در چت ربات وارد نکنید.",
    ]
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("پروفایل و اتصال", url=named_site_url("accounts:profile")))
    attach_nav(kb, home=False)
    return Screen("\n".join(lines), kb)


def _guest_home(link, staff, note: str = "") -> Screen:
    product = settings.PRODUCT_NAME
    lines = [
        f"👋 به ربات رسمی <b>{escape_html(product)}</b> خوش آمدید.",
        "حساب تلگرام خود را به پنل گرام‌ادز وصل کنید و کمپین‌ها را از همین‌جا مدیریت کنید.",
    ]
    if note:
        lines.append(escape_html(note))
    if link:
        lines.append("✅ اتصال فعال است — از «خانه» وارد داشبورد شوید.")
    buttons = []
    if staff and user_may_use_admin_panel(staff.user):
        buttons.append(("🛠 پنل مدیریت", "nav:admin"))
    buttons.append(("🔗 راهنمای اتصال", "c:guest:link"))
    buttons.append(("🌐 ورود به سایت", named_site_url("accounts:login")))
    kb = inline_grid([(t, d if d.startswith("http") or d.startswith("c:") or d.startswith("nav:") else f"url:{d}") for t, d in buttons], columns=1)
    # fix url buttons
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔗 راهنمای اتصال", callback_data="go:c:guest:link"))
    kb.add(types.InlineKeyboardButton("🌐 ورود به سایت", url=named_site_url("accounts:login")))
    if staff and user_may_use_admin_panel(staff.user):
        kb.add(types.InlineKeyboardButton("🛠 پنل مدیریت", callback_data="nav:admin"))
    attach_nav(kb, back=False, home=False)
    return Screen("\n".join(lines), kb)


def _customer_dashboard(customer: CustomerProfile, staff) -> Screen:
    snap = customer_data.dashboard_snapshot(customer)
    lines = [
        "📊 <b>داشبورد گرام‌ادز</b>",
        "خلاصه فعالیت تبلیغاتی و وضعیت حساب شما.",
        "",
        f"📢 کمپین‌های فعال: {format_int(snap['active_count'])}",
        f"⏳ در انتظار بررسی: {format_int(snap['pending_review'])}",
        f"💰 موجودی کیف پول: {format_toman(snap['wallet_available_irr'])} تومان",
        f"👁 بازدید: {format_int(snap['impressions'])}  ·  👆 کلیک: {format_int(snap['clicks'])}",
        f"🔔 اعلان خوانده‌نشده: {format_int(snap['unread_notifications'])}",
    ]
    pairs = [
        ("📢 کمپین‌ها", "go:c:cmp"),
        ("💳 کیف پول", "go:c:wallet"),
        ("📈 گزارش‌ها", "go:c:reports"),
        ("🏦 حساب تبلیغاتی", "go:c:conn"),
        ("🔔 اعلان‌ها", "go:c:notif"),
        ("🧠 دستیار هوشمند", "go:c:ai"),
        ("🎫 پشتیبانی", "go:c:support"),
        ("⚙️ تنظیمات", "go:c:settings"),
    ]
    if staff and user_may_use_admin_panel(staff.user):
        pairs.append(("🛠 پنل مدیریت", "nav:admin"))
    kb = inline_grid(pairs)
    attach_nav(kb, back=False)
    return Screen("\n".join(lines), kb)


def _campaigns_menu(customer: CustomerProfile) -> Screen:
    counts = customer_data.campaign_counts(customer)
    lines = [
        "📢 <b>کمپین‌های من</b>",
        "فهرست، وضعیت و جزئیات کمپین‌های تبلیغاتی.",
        "",
        f"همه: {format_int(counts['all'])}  ·  فعال: {format_int(counts['active'])}",
        f"در انتظار: {format_int(counts['pending'])}  ·  متوقف: {format_int(counts['paused'])}",
    ]
    kb = inline_grid(
        [
            ("📋 همه کمپین‌ها", "go:c:cmp:l:all:p:0"),
            ("🟢 فعال", "go:c:cmp:l:active:p:0"),
            ("⏳ در انتظار", "go:c:cmp:l:pending:p:0"),
            ("⏸ متوقف", "go:c:cmp:l:paused:p:0"),
            ("⛔️ ردشده", "go:c:cmp:l:rejected:p:0"),
        ]
    )
    kb.add(types.InlineKeyboardButton("➕ ایجاد کمپین", url=named_site_url("campaigns:wizard_new")))
    attach_nav(kb)
    return Screen("\n".join(lines), kb)


def _campaigns_list(customer: CustomerProfile, session, filt: str, page: int) -> Screen:
    items, total, page_size = customer_data.campaign_page(customer, filter_key=filt, page=page)
    filt_labels = {"all": "همه", "active": "فعال", "pending": "در انتظار", "paused": "متوقف", "rejected": "ردشده"}
    lines = [
        f"📢 <b>کمپین‌ها — {filt_labels.get(filt, filt)}</b>",
        f"صفحه {format_int(page + 1)} از {format_int(max(1, (total + page_size - 1) // page_size))}",
        "",
    ]
    session.context = {**(session.context or {}), "cmp_items": [str(c.pk) for c in items]}
    session.save(update_fields=["context", "updated_at"])
    pairs = []
    for i, c in enumerate(items):
        title = c.name or "کمپین بدون نام"
        pairs.append((f"{_status_label(c)[:12]} · {title[:22]}", f"go:c:cmp:v:{i}"))
    kb = inline_grid(pairs, columns=1)
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton("◀️ قبلی", callback_data=f"go:c:cmp:l:{filt}:p:{page - 1}"))
    if (page + 1) * page_size < total:
        nav.append(types.InlineKeyboardButton("بعدی ▶️", callback_data=f"go:c:cmp:l:{filt}:p:{page + 1}"))
    if nav:
        kb.row(*nav)
    attach_nav(kb)
    if not items:
        lines.append("موردی برای نمایش نیست.")
    return Screen("\n".join(lines), kb)


def _campaign_detail(customer: CustomerProfile, session, idx: int) -> Screen:
    ids = (session.context or {}).get("cmp_items") or []
    if idx < 0 or idx >= len(ids):
        return Screen("کمپین یافت نشد.", inline_grid([("بازگشت", "nav:back")]))
    from uuid import UUID

    campaign = Campaign.objects.filter(customer=customer, pk=UUID(ids[idx])).first()
    if not campaign:
        return Screen("کمپین یافت نشد.", inline_grid([("بازگشت", "nav:back")]))
    lines = [
        f"📌 <b>{escape_html(campaign.name or 'کمپین')}</b>",
        f"وضعیت: {escape_html(_status_label(campaign))}",
        f"بودجه: {format_toman(campaign.budget_irr)} تومان",
        f"آخرین به‌روزرسانی: {jalali_datetime_string(campaign.updated_at)}",
    ]
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("جزئیات در سایت", url=named_site_url("campaigns:detail", campaign.pk)))
    kb.add(types.InlineKeyboardButton("آمار روزانه", url=named_site_url("campaigns:intraday", campaign.pk)))
    attach_nav(kb)
    return Screen("\n".join(lines), kb)


def _wallet_menu(customer: CustomerProfile) -> Screen:
    snap = customer_data.wallet_snapshot(customer)
    w = snap["wallet"]
    lines = [
        "💳 <b>کیف پول و مالی</b>",
        "موجودی واقعی و میانبر تراکنش‌ها.",
        "",
        f"💰 موجودی: {format_toman(w.available_irr)} تومان",
        f"🔒 رزرو شده: {format_toman(w.reserved_irr)} تومان",
    ]
    if snap["recent"]:
        lines.append("")
        lines.append("<b>آخرین تراکنش‌ها:</b>")
        for e in snap["recent"][:3]:
            sign = "+" if e.entry_type == WalletLedgerEntry.EntryType.DEPOSIT else "−"
            lines.append(f"{sign}{format_toman(e.amount_irr)} — {e.get_entry_type_display()}")
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("💳 کیف پول", url=named_site_url("finance:wallet")))
    kb.add(types.InlineKeyboardButton("➕ افزایش موجودی", url=named_site_url("finance:topup")))
    kb.add(types.InlineKeyboardButton("📜 تراکنش‌ها", url=named_site_url("finance:transactions")))
    kb.add(types.InlineKeyboardButton("🧾 فاکتورها", url=named_site_url("finance:invoices")))
    attach_nav(kb)
    return Screen("\n".join(lines), kb)


def _connections_menu(customer: CustomerProfile) -> Screen:
    snap = customer_data.connections_snapshot(customer)
    lines = ["🏦 <b>حساب تبلیغاتی تلگرام</b>", "اتصال BYOA یا حساب مدیریت‌شده پلتفرم.", ""]
    if not snap["connections"]:
        lines.append("هنوز حسابی متصل نشده — اتصال امن فقط از پنل سایت انجام می‌شود.")
    for c in snap["connections"][:4]:
        lines.append(f"• {c.get_connection_type_display()} — {c.get_status_display()}")
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("مدیریت اتصال‌ها", url=named_site_url("accounts:telegram_connection")))
    kb.add(types.InlineKeyboardButton("حساب تبلیغ‌دهنده", url=named_site_url("accounts:related_account")))
    attach_nav(kb)
    return Screen("\n".join(lines), kb)


def _reports_menu(customer: CustomerProfile) -> Screen:
    snap = customer_data.reports_snapshot(customer)
    lines = [
        "📈 <b>گزارش‌ها</b>",
        "آمار تجمیعی کمپین‌های شما.",
        "",
        f"فعال: {format_int(snap['active_count'])}",
        f"بازدید: {format_int(snap['impressions'])}  ·  کلیک: {format_int(snap['clicks'])}",
        f"CTR: {format_pct(float(snap['ctr'] or 0))}",
    ]
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("داشبورد وب", url=named_site_url("dashboard:home")))
    kb.add(types.InlineKeyboardButton("فهرست کمپین‌ها", url=named_site_url("campaigns:list")))
    attach_nav(kb)
    return Screen("\n".join(lines), kb)


def _notifications_menu(customer: CustomerProfile) -> Screen:
    snap = customer_data.notifications_snapshot(customer)
    lines = ["🔔 <b>اعلان‌ها</b>", f"خوانده‌نشده: {format_int(snap['unread'])}", ""]
    for n in snap["items"][:6]:
        mark = "•" if not n.is_read else "◦"
        lines.append(f"{mark} {escape_html(n.title[:48])}")
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("مشاهده در سایت", url=named_site_url("dashboard:notifications")))
    attach_nav(kb)
    return Screen("\n".join(lines), kb)


def _support_menu(customer: CustomerProfile) -> Screen:
    snap = customer_data.support_snapshot(customer)
    lines = [
        "🎫 <b>پشتیبانی</b>",
        f"تیکت‌های باز: {format_int(snap['open_count'])}",
        "",
    ]
    for t in snap["recent"][:4]:
        lines.append(f"• {escape_html(t.subject[:40])} — {escape_html(t.get_status_display())}")
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("تیکت جدید", url=named_site_url("support:create")))
    kb.add(types.InlineKeyboardButton("تیکت‌های من", url=named_site_url("support:list")))
    attach_nav(kb)
    return Screen("\n".join(lines), kb)


def _ai_menu(customer: CustomerProfile) -> Screen:
    lines = [
        "🧠 <b>دستیار هوشمند</b>",
        "تولید متن، تحلیل و بهینه‌سازی — با همان سقف مصرف پنل وب.",
        "برای اجرای AI، در سایت روی کمپین موردنظر وارد شوید.",
    ]
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("➕ کمپین جدید + AI", url=named_site_url("campaigns:wizard_new")))
    kb.add(types.InlineKeyboardButton("کمپین‌های من", url=named_site_url("campaigns:list")))
    attach_nav(kb)
    return Screen("\n".join(lines), kb)


def _settings_menu(customer: CustomerProfile, link, session) -> Screen:
    lines = [
        "⚙️ <b>حساب و تنظیمات</b>",
        f"نام: {escape_html(customer)}",
        f"تلگرام: {'متصل ✅' if link else 'متصل نیست'}",
    ]
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("👤 پروفایل سایت", url=named_site_url("accounts:profile")))
    kb.add(types.InlineKeyboardButton("📱 دستگاه‌های متصل", callback_data="go:c:set:devices"))
    kb.add(types.InlineKeyboardButton("🔕 تنظیم اعلان‌ها", callback_data="go:c:set:notify"))
    kb.add(types.InlineKeyboardButton("⛓ قطع اتصال تلگرام", callback_data="go:c:set:disc"))
    attach_nav(kb)
    return Screen("\n".join(lines), kb)


def _disconnect_confirm(link) -> Screen:
    lines = ["⚠️ <b>قطع اتصال</b>", "پیام‌های ربات دیگر به این حساب ارسال نمی‌شود.", "ادامه می‌دهید؟"]
    kb = inline_grid(
        [
            ("✅ بله، قطع شود", "act:disc:yes"),
            ("❌ خیر", "nav:back"),
        ],
        columns=2,
    )
    attach_nav(kb, home=True, back=False)
    return Screen("\n".join(lines), kb)


def _notify_prefs(link) -> Screen:
    lines = [
        "🔕 <b>تنظیم اعلان‌های ربات</b>",
        "انواع رویدادهایی که از طریق تلگرام دریافت می‌کنید.",
    ]
    if link:
        try:
            p = link.notification_prefs
            lines += [
                "",
                f"{'✅' if p.campaign_status else '◻️'} وضعیت کمپین",
                f"{'✅' if p.payment_events else '◻️'} پرداخت و کیف پول",
                f"{'✅' if p.budget_alerts else '◻️'} هشدار بودجه",
                f"{'✅' if p.support_replies else '◻️'} پاسخ پشتیبانی",
            ]
        except Exception:
            lines.append("تنظیمات پیش‌فرض فعال است.")
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("تنظیم در سایت", url=named_site_url("accounts:profile")))
    attach_nav(kb)
    return Screen("\n".join(lines), kb)


def _devices_list(customer: CustomerProfile) -> Screen:
    from ..services.link import customer_active_links

    links = customer_active_links(customer)
    lines = ["📱 <b>دستگاه‌های متصل</b>", ""]
    for row in links:
        uname = f"@{row.telegram_username}" if row.telegram_username else f"ID {row.telegram_user_id}"
        lines.append(f"• {escape_html(uname)} — {jalali_datetime_string(row.linked_at)}")
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("اتصال دستگاه جدید", url=named_site_url("accounts:profile")))
    attach_nav(kb)
    return Screen("\n".join(lines), kb)


def _admin_home(staff) -> Screen:
    if not staff or not user_may_use_admin_panel(staff.user):
        return Screen("⛔️ دسترسی مدیریتی ندارید.", inline_grid([("🏠 خانه", "nav:home")]))
    ov = admin_data.ops_overview()
    lines = [
        "🛠 <b>پنل مدیریت گرام‌ادز</b>",
        "کنترل عملیات روزانه از تلگرام (اطلاعات حساس فقط در چت خصوصی).",
        "",
        f"👥 مشتریان: {format_int(ov['customer_count'])}",
        f"📢 کمپین در صف: {format_int(ov['pending_campaigns'])}",
        f"🎫 تیکت باز: {format_int(ov['open_tickets'])}",
    ]
    kb = inline_grid(
        [
            ("📊 داشبورد", "go:a:dash"),
            ("📢 کمپین‌ها", "go:a:cmp"),
            ("👥 مشتریان", "go:a:users"),
            ("💳 مالی", "go:a:fin"),
            ("🔄 انتقال نامطمئن", "go:a:fund"),
            ("✅ صف بررسی", "go:a:ads"),
            ("🎫 تیکت‌ها", "go:a:tickets"),
            ("📈 آمار", "go:a:stats"),
            ("🖥 وضعیت سرویس", "go:a:svc"),
        ],
        columns=2,
    )
    if _ops_url_exists():
        kb.add(types.InlineKeyboardButton("🌐 پنل عملیات", url=named_site_url("operations:overview")))
    attach_nav(kb, back=False)
    kb.row(types.InlineKeyboardButton("🏠 پنل مشتری", callback_data="nav:home"))
    return Screen("\n".join(lines), kb)


def _ops_url_exists():
    try:
        named_site_url("operations:overview")
        return True
    except Exception:
        return False


def _admin_dashboard() -> Screen:
    ov = admin_data.ops_overview()
    wl = ov["wallet_liabilities"]
    avail = int(wl.get("available") or 0)
    res = int(wl.get("reserved") or 0)
    lines = [
        "📊 <b>داشبورد مدیریتی</b>",
        f"سفارش‌ها: {format_int(ov['order_count'])}",
        f"بازپرداخت باز: {format_int(ov['open_refunds'])}",
        f"انتقال نامطمئن: {format_int(ov['uncertain_funding'])}",
        f"عملیات تبلیغ معلق: {format_int(ov['remote_pending'])}",
        "",
        f"بدهی کیف پول — آزاد: {format_toman(avail)} · رزرو: {format_toman(res)} تومان",
    ]
    kb = types.InlineKeyboardMarkup()
    if _ops_url_exists():
        kb.add(types.InlineKeyboardButton("پنل عملیات", url=named_site_url("operations:overview")))
    attach_nav(kb)
    return Screen("\n".join(lines), kb)


def _admin_campaigns() -> Screen:
    ov = admin_data.ops_overview()
    lines = ["📢 <b>مدیریت کمپین‌ها</b>", f"در انتظار بررسی: {format_int(ov['pending_campaigns'])}", ""]
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("صف بررسی کمپین", url=named_site_url("operations:campaigns")))
    attach_nav(kb)
    return Screen("\n".join(lines), kb)


def _admin_users() -> Screen:
    ov = admin_data.ops_overview()
    lines = ["👥 <b>کاربران و مشتریان</b>", f"تعداد مشتریان: {format_int(ov['customer_count'])}", ""]
    kb = types.InlineKeyboardMarkup()
    if _ops_url_exists():
        kb.add(types.InlineKeyboardButton("پنل عملیات", url=named_site_url("operations:overview")))
    attach_nav(kb)
    return Screen("\n".join(lines), kb)


def _admin_finance() -> Screen:
    ov = admin_data.ops_overview()
    lines = [
        "💳 <b>گزارش‌های مالی</b>",
        f"بازپرداخت‌های باز: {format_int(ov['open_refunds'])}",
        "",
        "عملیات مالی حساس فقط از پنل عملیات با تأیید مجوز انجام شود.",
    ]
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("بازپرداخت‌ها", url=named_site_url("operations:refunds")))
    kb.add(types.InlineKeyboardButton("تطبیق انتقال", url=named_site_url("operations:funding_transfers")))
    kb.add(types.InlineKeyboardButton("نرخ ارز", url=named_site_url("operations:exchange_rates")))
    attach_nav(kb)
    return Screen("\n".join(lines), kb)


def _admin_funding() -> Screen:
    ov = admin_data.ops_overview()
    lines = ["🔄 <b>انتقال‌های نیازمند تطبیق</b>", f"نامطمئن: {format_int(ov['uncertain_funding'])}", ""]
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("صف تطبیق", url=named_site_url("operations:funding_transfers")))
    attach_nav(kb)
    return Screen("\n".join(lines), kb)


def _admin_review_queue() -> Screen:
    ov = admin_data.ops_overview()
    lines = [
        "✅ <b>صف بررسی تبلیغات</b>",
        f"عملیات معلق: {format_int(ov['remote_pending'])}",
        "",
        "تأیید و ارسال حساس فقط از پنل عملیات وب انجام شود.",
    ]
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("عملیات ریموت", url=named_site_url("operations:remote_operations")))
    kb.add(types.InlineKeyboardButton("بررسی کمپین‌ها", url=named_site_url("operations:campaigns")))
    attach_nav(kb)
    return Screen("\n".join(lines), kb)


def _admin_tickets() -> Screen:
    ov = admin_data.ops_overview()
    tickets = admin_data.recent_open_tickets()
    lines = ["🎫 <b>تیکت‌های پشتیبانی</b>", f"باز: {format_int(ov['open_tickets'])}", ""]
    if tickets:
        lines.append("<b>آخرین تیکت‌های باز:</b>")
        for t in tickets:
            who = escape_html(str(t.customer)[:24])
            lines.append(f"• {escape_html(t.subject[:36])} — {who}")
    else:
        lines.append("تیکت بازی در صف نیست.")
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("پنل عملیات", url=named_site_url("operations:overview")))
    attach_nav(kb)
    return Screen("\n".join(lines), kb)


def _admin_stats() -> Screen:
    ov = admin_data.ops_overview()
    lines = [
        "📈 <b>آمار</b>",
        f"سفارش‌ها: {format_int(ov['order_count'])}",
        f"مشتریان: {format_int(ov['customer_count'])}",
        f"کمپین در صف: {format_int(ov['pending_campaigns'])}",
    ]
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("گزارش حساب تلگرام", url=named_site_url("operations:telegram_account")))
    attach_nav(kb)
    return Screen("\n".join(lines), kb)


def _admin_services() -> Screen:
    lines = [
        "🖥 <b>وضعیت سرویس‌ها</b>",
        "مانیتورینگ کامل از پنل عملیات وب.",
        "در تلگرام فقط خلاصه و هشدار نمایش داده می‌شود.",
    ]
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("کنترل از وب", url=named_site_url("operations:overview")))
    kb.add(types.InlineKeyboardButton("گزارش API", url=named_site_url("operations:remote_operations")))
    attach_nav(kb)
    return Screen("\n".join(lines), kb)