"""R0-03 (F-04 / U-14) — SSRF guard for outbound fetches of untrusted URLs.

All DNS resolution is faked via the injectable ``resolver`` — no test performs
a real network request.
"""

import pytest

from packages.shared.ssrf_validator import (
    SSRFBlockedError,
    assert_safe_url,
    check_url,
    is_safe_url,
)


def resolver_returning(*ips):
    def _resolve(hostname):
        return list(ips)

    return _resolve


def fake_dns(monkeypatch, ip="93.184.216.34"):
    """Fake A-record resolution at the socket boundary for any hostname."""
    import socket as _socket

    from packages.shared import ssrf_validator

    def _getaddrinfo(host, *args, **kwargs):
        return [(_socket.AF_INET, _socket.SOCK_STREAM, 6, "", (ip, 0))]

    monkeypatch.setattr(ssrf_validator.socket, "getaddrinfo", _getaddrinfo)


def resolver_failing():
    def _resolve(hostname):
        raise OSError(f"no DNS for {hostname}")

    return _resolve


class TestSchemeAllowlist:
    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "gopher://10.0.0.1",
            "ftp://example.com/file",
            "javascript:alert(1)",
            "data:text/html,hello",
        ],
    )
    def test_rejects_non_http_schemes(self, url):
        decision = check_url(url, resolver=resolver_returning("93.184.216.34"))
        assert not decision.allowed
        assert "not allowed" in decision.reason

    @pytest.mark.parametrize("url", ["http://example.com/a", "https://example.com/a"])
    def test_allows_http_https(self, url):
        assert check_url(url, resolver=resolver_returning("93.184.216.34")).allowed


class TestLiteralIps:
    @pytest.mark.parametrize(
        "ip",
        [
            "10.0.0.1",
            "10.255.255.255",
            "172.16.0.1",
            "172.31.255.255",
            "192.168.1.1",
            "169.254.169.254",  # cloud metadata endpoint
            "127.0.0.1",
            "127.8.8.8",
            "0.0.0.0",
            "::1",
            "fc00::1",
            "fe80::1",
            "ff02::1",
        ],
    )
    def test_rejects_private_and_reserved_literals(self, ip):
        decision = check_url(f"https://{ip}/x")
        assert not decision.allowed, decision.reason

    def test_allows_public_literal(self):
        assert check_url("https://93.184.216.34/x").allowed

    def test_metadata_hostname_pointing_internal(self):
        # A public-looking hostname whose DNS points at the metadata endpoint.
        decision = check_url(
            "http://internal-metadata.example.com/latest",
            resolver=resolver_returning("169.254.169.254"),
        )
        assert not decision.allowed


class TestDNSSemantics:
    def test_all_records_checked_not_just_first(self):
        decision = check_url(
            "http://mixed.example.com",
            resolver=resolver_returning("93.184.216.34", "192.168.0.5"),
        )
        assert not decision.allowed
        assert "192.168.0.5" in decision.reason

    def test_unresolvable_hostname_rejected(self):
        decision = check_url("http://does-not-exist.invalid", resolver=resolver_failing())
        assert not decision.allowed
        assert "cannot resolve" in decision.reason

    def test_assert_raises_on_unresolvable(self):
        with pytest.raises(SSRFBlockedError):
            assert_safe_url("http://does-not-exist.invalid", resolver=resolver_failing())

    def test_no_hostname_rejected(self):
        assert not check_url("https:///path-only").allowed

    def test_malformed_url_rejected(self):
        assert not check_url("https://[bad-ipv6").allowed


class TestGuardAwareness:
    def test_assert_safe_url_raises_on_private(self, monkeypatch):
        monkeypatch.delenv("ENRICH_SSRF_GUARD", raising=False)
        with pytest.raises(SSRFBlockedError):
            assert_safe_url("http://10.0.0.1/x")

    def test_assert_safe_url_noop_when_disabled(self, monkeypatch):
        monkeypatch.setenv("ENRICH_SSRF_GUARD", "0")
        assert assert_safe_url("http://10.0.0.1/x") is None

    def test_is_safe_url_true_when_disabled(self, monkeypatch):
        monkeypatch.setenv("ENRICH_SSRF_GUARD", "0")
        assert is_safe_url("file:///etc/passwd") is True

    def test_guard_default_on(self, monkeypatch):
        monkeypatch.delenv("ENRICH_SSRF_GUARD", raising=False)
        from packages.shared import ssrf_validator

        assert ssrf_validator.ssrf_guard_enabled() is True


class TestSocialScraperWiring:
    """The guard runs before any HTTP request in the social fetchers."""

    def test_facebook_fetch_blocked_for_internal_url(self, monkeypatch):
        import packages.enrichment.social_scraper as ss

        called = {"http": False}

        def _no_http(*args, **kwargs):
            called["http"] = True
            raise AssertionError("HTTP request attempted for internal URL")

        monkeypatch.setattr(ss.httpx, "get", _no_http)
        result = ss._fetch_facebook_og("http://169.254.169.254/latest/meta-data")
        assert result is None
        assert called["http"] is False

    def test_instagram_fetch_blocked_for_internal_url(self, monkeypatch):
        import packages.enrichment.social_scraper as ss

        def _no_http(*args, **kwargs):
            raise AssertionError("HTTP request attempted for internal URL")

        monkeypatch.setattr(ss.httpx, "get", _no_http)
        result = ss._fetch_instagram_profile("http://127.0.0.1:8080/profile")
        assert result is None


class TestImageFallbackExtractionBoundary:
    """Photo URLs entering artifacts are filtered at extraction."""

    def test_internal_urls_dropped(self, monkeypatch):
        from packages.enrichment.image_fallback import get_image_urls_from_enrichment

        monkeypatch.delenv("ENRICH_SSRF_GUARD", raising=False)
        fake_dns(monkeypatch)  # public hostnames resolve; literal IPs checked directly
        data = {
            "photos": [
                "https://cdn.photos-server.com/photo1.jpg",
                "http://192.168.1.10/photos/internal.jpg",
                "http://169.254.169.254/meta.jpg",
            ]
        }
        urls = get_image_urls_from_enrichment(data)
        assert urls == ["https://cdn.photos-server.com/photo1.jpg"]

    def test_public_urls_kept(self, monkeypatch):
        from packages.enrichment.image_fallback import get_image_urls_from_enrichment

        monkeypatch.delenv("ENRICH_SSRF_GUARD", raising=False)
        fake_dns(monkeypatch)
        data = {"photos": ["https://cdn.photos-server.com/photo1.jpg"]}
        assert get_image_urls_from_enrichment(data) == ["https://cdn.photos-server.com/photo1.jpg"]

    def test_guard_off_preserves_legacy_behavior(self, monkeypatch):
        from packages.enrichment.image_fallback import get_image_urls_from_enrichment

        monkeypatch.setenv("ENRICH_SSRF_GUARD", "0")
        data = {"photos": ["http://localhost:9000/x.jpg"]}
        assert get_image_urls_from_enrichment(data) == []
