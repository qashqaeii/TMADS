from __future__ import annotations

import re

from telead.limits import AD_TEXT_MAX

from apps.policies.constants import FindingSeverity, SOURCE_GUIDELINES
from apps.policies.services.rules_registry import rule_meta
from apps.policies.services.types import PolicyFindingDTO

_URL_SHORTENER_HOSTS = (
    "bit.ly",
    "tinyurl.com",
    "goo.gl",
    "t.co",
    "ow.ly",
    "is.gd",
    "buff.ly",
    "rebrand.ly",
)
_TME_IN_TEXT = re.compile(
    r"(?:@([A-Za-z0-9_]{4,32})|(?:https?://)?(?:t\.me|telegram\.me)/([A-Za-z0-9_]{4,32})(?:/\S+)?)",
    re.IGNORECASE,
)
_IP_HOST = re.compile(r"^\d{1,3}(\.\d{1,3}){3}")


def _meta_finding(rule_id: str, **kwargs) -> PolicyFindingDTO:
    meta = rule_meta(rule_id)
    return PolicyFindingDTO(
        rule_id=rule_id,
        source_document=meta.get("document", ""),
        source_clause=meta.get("clause", ""),
        source_url=meta.get("url", SOURCE_GUIDELINES),
        **kwargs,
    )


def check_ad_text(target_type: str, ad_text: str | None) -> list[PolicyFindingDTO]:
    if target_type == "search":
        return []
    text = (ad_text or "").strip()
    findings: list[PolicyFindingDTO] = []
    if not text:
        return findings

    if len(text) > AD_TEXT_MAX:
        findings.append(
            _meta_finding(
                "TG-FMT-001",
                severity=FindingSeverity.BLOCKED,
                field_key="ad_text",
                message_fa="متن تبلیغ از سقف مجاز این نوع تبلیغ بیشتر است. لطفاً آن را کوتاه‌تر کنید.",
                suggestion_fa="متن را حداکثر تا ۱۶۰ کاراکتر (شامل فاصله) کوتاه کنید.",
            )
        )

    if "\n" in text or "\r" in text:
        findings.append(
            _meta_finding(
                "TG-EDI-002",
                severity=FindingSeverity.BLOCKED,
                field_key="ad_text",
                message_fa="برای این نوع تبلیغ، متن باید در یک خط نوشته شود.",
                suggestion_fa="خطوط جدا را به جمله‌های کوتاه با فاصله تبدیل کنید.",
            )
        )

    if re.search(r"(^|\s)[•\-\*]\s", text) or re.search(r"(^|\s)\d+[\.\)]\s", text):
        findings.append(
            _meta_finding(
                "TG-EDI-002",
                severity=FindingSeverity.BLOCKED,
                field_key="ad_text",
                message_fa="لیست گلوله‌ای یا شماره‌دار در متن تبلیغ مجاز نیست.",
            )
        )

    letters = [c for c in text if c.isalpha()]
    if letters:
        upper = sum(1 for c in letters if c.isupper())
        if upper / len(letters) > 0.45 and len(letters) >= 8:
            findings.append(
                _meta_finding(
                    "TG-EDI-002",
                    severity=FindingSeverity.WARNING,
                    field_key="ad_text",
                    message_fa="استفاده بیش از حد از حروف بزرگ ممکن است باعث رد شدن تبلیغ شود.",
                    suggestion_fa="فقط کلمات کلیدی کوتاه را با حرف بزرگ بنویسید.",
                )
            )

    if text.count("!") + text.count("?") >= 4:
        findings.append(
            _meta_finding(
                "TG-EDI-002",
                severity=FindingSeverity.WARNING,
                field_key="ad_text",
                message_fa="استفاده زیاد از علامت تعجب یا سؤال ممکن است باعث رد شدن تبلیغ شود.",
            )
        )

    symbol_chars = sum(1 for c in text if not c.isalnum() and not c.isspace())
    if len(text) >= 12 and symbol_chars / len(text) > 0.35:
        findings.append(
            _meta_finding(
                "TG-EDI-002",
                severity=FindingSeverity.WARNING,
                field_key="ad_text",
                message_fa="استفاده زیاد از نمادها ممکن است باعث رد شدن تبلیغ شود.",
            )
        )

    emoji_pattern = re.compile(
        "["
        "\U0001F300-\U0001FAFF"
        "\u2600-\u27BF"
        "]",
        flags=re.UNICODE,
    )
    emojis = emoji_pattern.findall(text)
    if len(emojis) >= 6:
        findings.append(
            _meta_finding(
                "TG-EDI-002",
                severity=FindingSeverity.WARNING,
                field_key="ad_text",
                message_fa="استفاده زیاد از اموجی ممکن است باعث رد شدن تبلیغ شود.",
            )
        )

    if len(text.split()) >= 6:
        words = text.lower().split()
        if len(words) != len(set(words)) and max(words.count(w) for w in set(words)) >= 3:
            findings.append(
                _meta_finding(
                    "TG-EDI-002",
                    severity=FindingSeverity.WARNING,
                    field_key="ad_text",
                    message_fa="تکرار بیش از حد واژه‌ها ممکن است متن را مبهم نشان دهد.",
                )
            )

    return findings


def check_text_links(ad_text: str | None, promote_url: str) -> list[PolicyFindingDTO]:
    if not ad_text:
        return []
    findings: list[PolicyFindingDTO] = []
    matches = list(_TME_IN_TEXT.finditer(ad_text))
    if len(matches) > 1:
        findings.append(
            _meta_finding(
                "TG-LNK-003",
                severity=FindingSeverity.BLOCKED,
                field_key="ad_text",
                message_fa="در متن تبلیغ بیش از یک لینک مجاز نیست.",
            )
        )
    if not matches:
        return findings

    promote_user = _username_from_promote(promote_url)
    for m in matches:
        inner = (m.group(1) or m.group(2) or "").lower()
        if promote_user and inner and inner != promote_user:
            findings.append(
                _meta_finding(
                    "TG-LNK-003",
                    severity=FindingSeverity.BLOCKED,
                    field_key="ad_text",
                    message_fa="لینک داخل متن باید به همان مقصد دکمهٔ تبلیغ برود.",
                )
            )
            break

    for host in _URL_SHORTENER_HOSTS:
        if host in ad_text.lower():
            findings.append(
                _meta_finding(
                    "TG-LNK-003",
                    severity=FindingSeverity.BLOCKED,
                    field_key="ad_text",
                    message_fa="استفاده از کوتاه‌کنندهٔ لینک در متن تبلیغ مجاز نیست.",
                )
            )
            break

    if re.search(r"https?://\d{1,3}(\.\d{1,3}){3}", ad_text):
        findings.append(
            _meta_finding(
                "TG-LNK-003",
                severity=FindingSeverity.BLOCKED,
                field_key="ad_text",
                message_fa="آدرس IP به‌جای لینک مقصد مجاز نیست.",
            )
        )
    return findings


def _username_from_promote(url: str) -> str:
    from urllib.parse import urlparse

    raw = (url or "").strip()
    if raw.startswith("@"):
        return raw.lstrip("@").lower()
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").strip("/")
    if "t.me" in host or "telegram.me" in host:
        return path.split("/")[0].lower() if path else ""
    return ""


def check_promote_url_format(promote_url: str, *, allow_external: bool = False) -> list[PolicyFindingDTO]:
    from urllib.parse import urlparse

    from apps.telegram_ads.targeting.normalize import parse_promote_url

    findings: list[PolicyFindingDTO] = []
    norm, errors = parse_promote_url(promote_url)
    if errors:
        findings.append(
            _meta_finding(
                "TG-DST-004",
                severity=FindingSeverity.BLOCKED,
                field_key="destination",
                message_fa=errors[0],
            )
        )
        return findings

    parsed = urlparse(norm)
    host = (parsed.netloc or "").lower()
    if host in _URL_SHORTENER_HOSTS or _IP_HOST.match(host):
        findings.append(
            _meta_finding(
                "TG-LNK-003",
                severity=FindingSeverity.BLOCKED,
                field_key="destination",
                message_fa="فرمت لینک مقصد (کوتاه‌کننده یا IP) پذیرفته نمی‌شود.",
            )
        )

    is_telegram = parsed.hostname in {"t.me","telegram.me","www.t.me","www.telegram.me"} or parsed.scheme == "tg"
    if not is_telegram and not allow_external:
        findings.append(
            _meta_finding(
                "TG-GSG-008",
                severity=FindingSeverity.REVIEW_REQUIRED,
                field_key="destination",
                message_fa="مقصد وب‌سایت ممکن است فقط برای برخی قالب‌های حساب مجاز باشد؛ نیازمند تأیید عملیات.",
                requires_manual_review=True,
            )
        )
    return findings
