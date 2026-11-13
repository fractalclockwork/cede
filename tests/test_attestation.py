"""Tests for the generalized attestation module (DS-9)."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from cede.attestation import (
    attestation_failure_reason,
    banner_prefix_ok,
    digest_banner_line,
    digest_token,
    expected_digest_value,
    resolve_banner_prefix,
)


class TestDigestToken:
    def test_extracts_token(self) -> None:
        buf = b"CEDE hello_lab rp2 ok digest=deadbeef1234 (i2c"
        assert digest_token(buf) == b"deadbeef1234"

    def test_extracts_complex_token(self) -> None:
        buf = b"noise\nCEDE hello_lab ok digest=t12345678_abcd1234 (i2c target 0x43)\n"
        assert digest_token(buf) == b"t12345678_abcd1234"

    def test_returns_none_when_missing(self) -> None:
        buf = b"CEDE hello_lab rp2 ok no digest here"
        assert digest_token(buf) is None

    def test_case_insensitive(self) -> None:
        buf = b"CEDE hello_lab ok DIGEST=ABC123\n"
        assert digest_token(buf) == b"ABC123"


class TestBannerPrefixOk:
    def test_pico_banner(self) -> None:
        buf = b"CEDE hello_lab rp2 ok digest=abc123"
        assert banner_prefix_ok(buf, "CEDE hello_lab rp2 ok") is True

    def test_uno_banner(self) -> None:
        buf = b"CEDE hello_lab ok digest=abc123"
        assert banner_prefix_ok(buf, "CEDE hello_lab ok") is True

    def test_missing_banner(self) -> None:
        buf = b"random garbage output"
        assert banner_prefix_ok(buf, "CEDE hello_lab rp2 ok") is False


class TestDigestBannerLine:
    def test_finds_line(self) -> None:
        buf = b"noise\nCEDE hello_lab ok digest=t12345678_abcd1234 (i2c target 0x43)\nmore noise"
        line = digest_banner_line(buf, "CEDE hello_lab ok")
        assert line == "CEDE hello_lab ok digest=t12345678_abcd1234 (i2c target 0x43)"

    def test_returns_none_without_match(self) -> None:
        buf = b"no matching line here\n"
        assert digest_banner_line(buf, "CEDE hello_lab ok") is None

    def test_case_insensitive_prefix(self) -> None:
        buf = b"cede hello_lab ok digest=abc\n"
        assert digest_banner_line(buf, "CEDE hello_lab ok") == "cede hello_lab ok digest=abc"


class TestAttestationFailureReason:
    def test_passes_on_correct_banner_and_digest(self) -> None:
        buf = b"CEDE hello_lab rp2 ok digest=deadbeef1234 (i2c"
        result = attestation_failure_reason(buf, banner_prefix="CEDE hello_lab rp2 ok", digest_must_equal="deadbeef1234")
        assert result is None

    def test_fails_missing_banner(self) -> None:
        buf = b"wrong output"
        result = attestation_failure_reason(buf, banner_prefix="CEDE hello_lab rp2 ok")
        assert result is not None
        assert "missing banner prefix" in result

    def test_fails_missing_digest(self) -> None:
        buf = b"CEDE hello_lab rp2 ok no digest"
        result = attestation_failure_reason(buf, banner_prefix="CEDE hello_lab rp2 ok")
        assert result is not None
        assert "digest=<id>" in result

    def test_fails_digest_mismatch(self) -> None:
        buf = b"CEDE hello_lab ok digest=aaaa (i2c"
        result = attestation_failure_reason(buf, banner_prefix="CEDE hello_lab ok", digest_must_equal="bbbb")
        assert result is not None
        assert "mismatch" in result

    def test_passes_without_digest_enforcement(self) -> None:
        buf = b"CEDE hello_lab rp2 ok digest=anything"
        result = attestation_failure_reason(buf, banner_prefix="CEDE hello_lab rp2 ok", digest_must_equal="")
        assert result is None

    def test_digest_comparison_case_insensitive(self) -> None:
        buf = b"CEDE hello_lab ok digest=ABCdef123"
        result = attestation_failure_reason(buf, banner_prefix="CEDE hello_lab ok", digest_must_equal="abcdef123")
        assert result is None

    def test_gateway_banner(self) -> None:
        buf = b"CEDE hello_gateway ok digest=abc123deadbeef\n"
        result = attestation_failure_reason(buf, banner_prefix="CEDE hello_gateway ok", digest_must_equal="abc123deadbeef")
        assert result is None


class TestExpectedDigestValue:
    def test_cli_arg_wins(self) -> None:
        assert expected_digest_value("fromcli") == "fromcli"

    def test_env_fallback(self) -> None:
        with patch.dict(os.environ, {"CEDE_EXPECT_DIGEST": "fromenv"}):
            assert expected_digest_value("") == "fromenv"

    def test_empty_when_nothing_set(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            assert expected_digest_value("") == ""


class TestResolveBannerPrefix:
    def test_explicit_prefix(self) -> None:
        result = resolve_banner_prefix(app_banner_prefix="CEDE hello_lab rp2 ok")
        assert result == "CEDE hello_lab rp2 ok"

    def test_constructed_from_app_and_target(self) -> None:
        result = resolve_banner_prefix(application_id="hello_lab", target_type_name="rp2")
        assert result == "CEDE hello_lab rp2 ok"

    def test_app_only(self) -> None:
        result = resolve_banner_prefix(application_id="hello_lab")
        assert result == "CEDE hello_lab ok"

    def test_fallback(self) -> None:
        result = resolve_banner_prefix()
        assert result == "CEDE ok"
