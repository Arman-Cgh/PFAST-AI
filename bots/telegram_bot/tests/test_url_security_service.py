import pytest
from unittest.mock import patch

from services.security.url_scanner import (
    analyze_url_security,
)


# ==============================================================================
# 1. Basic & Scheme Validation Tests
# ==============================================================================

def test_valid_legitimate_urls():
    safe_urls = [
        "https://google.com",
        "https://github.com/torvalds/linux",
        "https://en.wikipedia.org/wiki/Computer_security",
        "https://python.org",
    ]
    for u in safe_urls:
        res = analyze_url_security(u)
        assert res["valid"] is True
        assert res["risk_level"] == "safe"
        assert res["score"] < 25
        assert len(res["indicators"]) == 0 or res["indicators"] == []


def test_empty_and_malformed_inputs():
    assert analyze_url_security("")["valid"] is False
    assert analyze_url_security(None)["valid"] is False
    assert analyze_url_security("   ")["valid"] is False


def test_unsafe_schemes_blocked():
    unsafe_schemes = [
        "javascript:alert(1)",
        "data:text/html,<script>alert('XSS')</script>",
        "file:///etc/passwd",
        "ftp://ftp.example.com/file.zip",
        "gopher://gopher.example.com",
    ]
    for u in unsafe_schemes:
        res = analyze_url_security(u)
        assert res["valid"] is False
        assert res["risk_level"] == "dangerous"
        assert "unsafe_scheme" in res["indicators"]
        assert res["score"] >= 90


# ==============================================================================
# 2. SSRF & Private / Loopback IP Tests
# ==============================================================================

def test_localhost_and_private_ips_detected():
    ssrf_targets = [
        "http://localhost/admin",
        "http://127.0.0.1:8000/api",
        "http://10.0.0.1/config",
        "http://172.16.0.5/secret",
        "http://192.168.1.1/router",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/debug",
    ]
    for u in ssrf_targets:
        res = analyze_url_security(u)
        assert res["valid"] is True
        assert res["risk_level"] == "dangerous"
        assert "private_or_loopback_ip" in res["indicators"]
        assert res["score"] >= 70


# ==============================================================================
# 3. Individual Indicators & Combinations
# ==============================================================================

def test_raw_public_ip():
    res = analyze_url_security("http://45.33.32.156/page")
    assert "raw_ip_host" in res["indicators"]
    # Single indicator should be suspicious, not dangerous
    assert res["risk_level"] == "suspicious"
    assert res["score"] < 60


def test_punycode_homograph_detection():
    res = analyze_url_security("https://xn--e1afmkfd.xn--p1ai/")
    assert "punycode_or_homograph" in res["indicators"]


def test_suspicious_tlds():
    res = analyze_url_security("https://free-gifts.tk/")
    assert any(ind.startswith("suspicious_tld") for ind in res["indicators"])


def test_url_shorteners():
    res = analyze_url_security("https://bit.ly/3xXyz99")
    assert "url_shortener" in res["indicators"]
    assert res["risk_level"] == "suspicious"


def test_non_standard_ports():
    res = analyze_url_security("https://example.com:8080/dashboard")
    assert "non_standard_port_8080" in res["indicators"]


def test_embedded_credentials():
    res = analyze_url_security("https://admin:secret123@example.com/vault")
    assert "embedded_credentials" in res["indicators"]
    assert res["score"] >= 30


def test_dangerous_file_extensions():
    res = analyze_url_security("https://example.com/downloads/malware.exe")
    assert any(ind.startswith("dangerous_extension") for ind in res["indicators"])
    assert res["score"] >= 45


def test_excessive_subdomains():
    res = analyze_url_security("https://a.b.c.d.e.example.com/login")
    assert "excessive_subdomains" in res["indicators"]


def test_phishing_keywords():
    res = analyze_url_security("https://telegram-verify-account-security.com/")
    assert any("brand_spoof" in ind or "phishing_action" in ind for ind in res["indicators"])


def test_combined_high_risk_attack_url():
    # Combination: Raw IP + Non-standard Port + Phishing keyword + Executable file
    attack_url = "http://45.33.32.156:8080/telegram_verification_tool.exe"
    res = analyze_url_security(attack_url)
    assert res["risk_level"] == "dangerous"
    assert res["score"] >= 80
    assert "raw_ip_host" in res["indicators"]
    assert "non_standard_port_8080" in res["indicators"]
    assert any("brand_spoof" in ind or "phishing_action" in ind for ind in res["indicators"])
    assert any(ind.startswith("dangerous_extension") for ind in res["indicators"])


# ==============================================================================
# 4. Zero Network & Pure Offline Verification
# ==============================================================================

def test_zero_network_calls_guaranteed():
    with patch("socket.socket") as mock_socket, patch("http.client.HTTPConnection") as mock_http:
        res = analyze_url_security("https://some-unresolved-domain-123456789.xyz:8888/login.scr")
        assert res["valid"] is True
        assert res["risk_level"] == "dangerous"
        mock_socket.assert_not_called()
        mock_http.assert_not_called()
