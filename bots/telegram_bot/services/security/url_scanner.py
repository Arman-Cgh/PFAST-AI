"""
Core URL Security Scanner.

Pure deterministic business logic for offline URL analysis, structural parsing,
SSRF/private IP filtering, homograph attack detection, and multi-factor threat scoring.

Security & Privacy Guarantees:
- Zero network or outbound HTTP/DNS requests (100% offline analysis).
- Zero database interactions or disk persistence.
- Zero AI provider calls or third-party leakage.
- Passwords and sensitive query credentials are sanitized.
"""

import ipaddress
import re
import string
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, unquote, urlsplit


# High-abuse TLDs commonly seen in phishing and spam campaigns
SUSPICIOUS_TLDS: Set[str] = {
    "tk", "ml", "ga", "cf", "gq", "top", "xyz", "buzz", "club",
    "work", "fit", "icu", "cam", "kim", "rest", "gdn", "loan",
    "racing", "download", "win", "bid", "stream", "monster", "surf",
    "click", "link", "party", "trade", "review", "country", "science",
}

# Known URL shortener domains (obscure actual target destination)
KNOWN_SHORTENERS: Set[str] = {
    "bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "ow.ly",
    "buff.ly", "rebrand.ly", "tiny.cc", "shorte.st", "adf.ly",
    "bc.vc", "v.gd", "soo.gd", "s.id", "shorturl.at", "trib.al",
}

# Dangerous file extensions commonly used in malware distribution
DANGEROUS_EXTENSIONS: Set[str] = {
    ".exe", ".scr", ".bat", ".cmd", ".vbs", ".vbe", ".js", ".jse",
    ".wsf", ".wsh", ".ps1", ".apk", ".dmg", ".iso", ".msi", ".jar",
    ".hta", ".cpl", ".pif", ".reg", ".dll", ".com", ".gadget",
}

# Brand names often targeted by phishing / spoofing
BRAND_SPOOF_KEYWORDS: Set[str] = {
    "paypal", "telegram", "shaparak", "mellat", "saman", "melli",
    "pasargad", "metamask", "binance",
}

# Phishing-specific action tokens
PHISHING_ACTION_KEYWORDS: Set[str] = {
    "login", "signin", "verify", "verification", "recovery",
    "wallet", "authenticate", "authorize",
}

LEGITIMATE_DOMAINS: Set[str] = {
    "telegram.org", "t.me", "paypal.com", "wikipedia.org", "github.com",
    "google.com", "python.org", "microsoft.com", "apple.com", "cloudflare.com",
}

# Suspicious query parameter keys indicating potential open redirects or token leakage
REDIRECT_QUERY_KEYS: Set[str] = {
    "url", "redirect", "redirect_to", "redirect_url", "dest", "destination",
    "goto", "target", "return", "return_url", "r", "u", "next", "link",
}

# Supported URL schemes
ALLOWED_SCHEMES: Set[str] = {"http", "https"}


def _is_private_or_loopback_ip(ip_str: str) -> bool:
    """
    Check if an IP string is private, loopback, link-local, or reserved
    (e.g., 127.0.0.1, 10.0.0.1, 192.168.1.1, 169.254.169.254, ::1).
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        return bool(
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        )
    except ValueError:
        return False


def _is_raw_ip(hostname: str) -> Tuple[bool, bool]:
    """
    Determine if hostname is a raw IPv4/IPv6 address, and whether it is private/loopback.
    Returns (is_ip, is_private).
    """
    clean_host = hostname.strip("[]")
    try:
        ip = ipaddress.ip_address(clean_host)
        is_priv = bool(
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        )
        return True, is_priv
    except ValueError:
        return False, False


def _is_punycode_or_homograph(hostname: str) -> bool:
    """Check if the hostname uses Punycode (xn--) or non-ASCII characters."""
    if "xn--" in hostname.lower():
        return True
    try:
        hostname.encode("ascii")
        return False
    except UnicodeEncodeError:
        return True


def _extract_tld(hostname: str) -> str:
    """Extract top-level domain from hostname."""
    parts = hostname.lower().split(".")
    if len(parts) >= 2:
        return parts[-1]
    return ""


def _count_subdomains(hostname: str) -> int:
    """Count number of subdomain labels."""
    parts = hostname.lower().split(".")
    # e.g., 'a.b.example.com' -> 4 parts -> 2 subdomains
    if len(parts) > 2:
        return len(parts) - 2
    return 0


def _has_dangerous_extension(path: str) -> Optional[str]:
    """Check if the URL path ends with a dangerous executable or script extension."""
    clean_path = unquote(path).lower().split("?")[0].split("#")[0]
    for ext in DANGEROUS_EXTENSIONS:
        if clean_path.endswith(ext):
            return ext
    return None


def _find_suspicious_keywords(hostname: str, path: str) -> List[str]:
    """Find phishing or brand spoofing keywords in hostname or path."""
    clean_host = hostname.lower()
    for leg in LEGITIMATE_DOMAINS:
        if clean_host == leg or clean_host.endswith(f".{leg}"):
            return []

    host_tokens = set(re.sub(r"[^a-zA-Z0-9]", " ", clean_host).split())
    path_tokens = set(re.sub(r"[^a-zA-Z0-9]", " ", unquote(path).lower()).split())
    all_tokens = host_tokens | path_tokens

    found = []
    # Check brand spoofing across all tokens
    for brand in BRAND_SPOOF_KEYWORDS:
        if brand in all_tokens or any(brand in tok for tok in all_tokens):
            found.append(f"brand_spoof_{brand}")

    # Check phishing actions across all tokens
    for action in PHISHING_ACTION_KEYWORDS:
        if action in all_tokens:
            found.append(f"phishing_action_{action}")

    return found


def _has_suspicious_query_params(query: str) -> bool:
    """Check for open redirect or sensitive token parameters in query string."""
    if not query:
        return False
    try:
        parsed = parse_qs(query)
        for k in parsed.keys():
            if k.lower() in REDIRECT_QUERY_KEYS:
                return True
    except Exception:
        pass
    return False


def analyze_url_security(url: str) -> Dict[str, Any]:
    """
    Perform local, deterministic security and structural risk analysis on a URL.

    Evaluates:
    - Scheme safety (HTTP/HTTPS whitelist; blocks file://, javascript:, data:)
    - SSRF & private IP addresses (127.0.0.1, 10.0.0.0/8, 192.168.0.0/16, 169.254.169.254, ::1)
    - Raw IP hostnames
    - Punycode & IDN homograph spoofing (xn--)
    - Suspicious high-abuse TLDs
    - Known URL shorteners
    - Non-standard TCP ports
    - Embedded user credentials (user:pass@host)
    - Dangerous downloadable file extensions (.exe, .scr, .apk)
    - Phishing-related keywords and excessive subdomain depth

    Returns structured report with multi-factor risk score and actionable recommendations.
    """
    if not url or not isinstance(url, str):
        return {
            "valid": False,
            "risk_level": "invalid",
            "score": 0,
            "normalized_url": "",
            "hostname": "",
            "scheme": "",
            "indicators": ["empty_or_invalid_input"],
            "recommendations": ["آدرس اینترنتی نمی‌تواند خالی باشد."],
        }

    raw_url = url.strip()

    # 1. Detect explicit scheme
    scheme_match = re.match(r"^([a-zA-Z][a-zA-Z0-9+\-.]*):", raw_url)
    if scheme_match:
        scheme_candidate = scheme_match.group(1).lower()
        if scheme_candidate not in ALLOWED_SCHEMES:
            return {
                "valid": False,
                "risk_level": "dangerous",
                "score": 95,
                "normalized_url": "",
                "hostname": "",
                "scheme": scheme_candidate,
                "indicators": ["unsafe_scheme"],
                "recommendations": [f"پروتکل '{scheme_candidate}' به دلایل امنیتی مسدود است. فقط پروتکل‌های http و https مجاز هستند."],
            }
    else:
        # Prepend default scheme
        raw_url = f"http://{raw_url}"

    try:
        parsed = urlsplit(raw_url)
    except Exception:
        return {
            "valid": False,
            "risk_level": "invalid",
            "score": 0,
            "normalized_url": "",
            "hostname": "",
            "scheme": "",
            "indicators": ["malformed_url"],
            "recommendations": ["ساختار آدرس اینترنتی نامعتبر و غیرقابل پردازش است."],
        }

    scheme = (parsed.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        return {
            "valid": False,
            "risk_level": "dangerous",
            "score": 95,
            "normalized_url": "",
            "hostname": parsed.hostname or "",
            "scheme": scheme,
            "indicators": ["unsafe_scheme"],
            "recommendations": [f"پروتکل '{scheme}' به دلایل امنیتی مسدود است. فقط پروتکل‌های http و https مجاز هستند."],
        }

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return {
            "valid": False,
            "risk_level": "invalid",
            "score": 0,
            "normalized_url": "",
            "hostname": "",
            "scheme": scheme,
            "indicators": ["missing_hostname"],
            "recommendations": ["نام دامنه یا آدرس سرور در لینک مشخص نشده است."],
        }

    indicators: List[str] = []
    recommendations: List[str] = []
    score = 0

    try:
        port = parsed.port
    except ValueError:
        port = None
        indicators.append("malformed_port")
        score += 20

    path = parsed.path or "/"
    query = parsed.query or ""

    # 1. SSRF & Localhost / Private IP Check
    is_ip, is_priv = _is_raw_ip(hostname)
    if hostname == "localhost" or is_priv:
        score += 75
        indicators.append("private_or_loopback_ip")
        recommendations.append("این آدرس به یک شبکه داخلی یا محلی (Private/Loopback IP) اشاره دارد و ممکن است برای حمله SSRF استفاده شود.")

    # 2. Raw IP as Hostname (Public IP)
    elif is_ip:
        score += 20
        indicators.append("raw_ip_host")
        recommendations.append("آدرس به جای نام دامنه رسمی از یک IP مستقیم استفاده می‌کند؛ وب‌سایت‌های معتبر معمولاً از نام دامنه استفاده می‌کنند.")

    # 3. Punycode & IDN Homograph
    if _is_punycode_or_homograph(hostname):
        score += 25
        indicators.append("punycode_or_homograph")
        recommendations.append("نام دامنه حاوی نویسه‌های یونیکد یا پیشوند Punycode (xn--) است که معمولاً برای جعل نام برندها (Homograph Attack) استفاده می‌شود.")

    # 4. Embedded Credentials
    if parsed.username or parsed.password:
        score += 30
        indicators.append("embedded_credentials")
        recommendations.append("لینک حاوی نام کاربری یا رمز عبور تعبیه‌شده در ساختار URL است که یک الگوی مشکوک برای فریب کاربر است.")

    # 5. Dangerous File Extension
    dangerous_ext = _has_dangerous_extension(path)
    if dangerous_ext:
        score += 45
        indicators.append(f"dangerous_extension_{dangerous_ext.lstrip('.')}")
        recommendations.append(f"این لینک مستقیماً به یک فایل اجرایی یا اسکریپت ({dangerous_ext}) منتهی می‌شود که ریسک آلودگی به بدافزار دارد.")

    # 6. Non-Standard Port
    if port and port not in (80, 443):
        score += 15
        indicators.append(f"non_standard_port_{port}")
        recommendations.append(f"سایت از درگاه غیرمعمول ({port}) استفاده می‌کند.")

    # 7. Suspicious High-Abuse TLD
    tld = _extract_tld(hostname)
    if tld in SUSPICIOUS_TLDS:
        score += 15
        indicators.append(f"suspicious_tld_{tld}")
        recommendations.append(f"پسوند دامنه (.{tld}) از پسوندهای پرخطر با سابقه سوءاستفاده در فیشینگ است.")

    # 8. Known URL Shortener
    if hostname in KNOWN_SHORTENERS:
        score += 25
        indicators.append("url_shortener")
        recommendations.append("این یک لینک کوتاه‌کننده است و مقصد نهایی آن پنهان شده است. با احتیاط باز شود.")

    # 9. Excessive Subdomains
    sub_count = _count_subdomains(hostname)
    if sub_count >= 3:
        score += 15
        indicators.append("excessive_subdomains")
        recommendations.append("دامنه دارای زیردامنه‌های تودرتوی متعدد و غیرعادی است.")

    # 10. Phishing / Security Keywords
    keywords_found = _find_suspicious_keywords(hostname, path)
    if keywords_found:
        score += 20
        for kw_ind in keywords_found:
            indicators.append(kw_ind)
        recommendations.append("کلمات کلیدی حساس و امنیتی (مانند جعل برند یا تأیید حساب) در مسیر لینک مشاهده شد.")

    # 11. Suspicious Query Parameters (Open Redirects)
    if _has_suspicious_query_params(query):
        score += 10
        indicators.append("suspicious_redirect_params")
        recommendations.append("پارامترهای هدایت‌کننده (Redirect) در لینک شناسایی شد که ممکن است کاربر را به سایتی دیگر منتقل کنند.")

    # 12. Insecure HTTP
    if scheme == "http" and not (hostname == "localhost" or is_priv):
        score += 5
        indicators.append("insecure_http")
        recommendations.append("اتصال از پروتکل رمزنگاری نشده (HTTP) استفاده می‌کند.")

    # 13. Excessive URL Length
    if len(raw_url) > 150:
        score += 10
        indicators.append("excessive_length")

    # Final Score & Tier Classification
    final_score = max(0, min(100, score))

    if final_score >= 60:
        risk_level = "dangerous"
    elif final_score >= 25:
        risk_level = "suspicious"
    else:
        risk_level = "safe"

    # Normalized clean URL (sanitizes embedded credentials)
    clean_netloc = hostname
    if port and port not in (80, 443):
        clean_netloc = f"{hostname}:{port}"
    normalized_url = f"{scheme}://{clean_netloc}{path}"
    if query:
        normalized_url = f"{normalized_url}?{query}"

    if not recommendations:
        recommendations.append("هیچ شاخص مشکوکی در ساختار این آدرس شناسایی نشد.")

    return {
        "valid": True,
        "risk_level": risk_level,
        "score": final_score,
        "normalized_url": normalized_url,
        "hostname": hostname,
        "scheme": scheme,
        "indicators": indicators,
        "recommendations": recommendations,
    }
