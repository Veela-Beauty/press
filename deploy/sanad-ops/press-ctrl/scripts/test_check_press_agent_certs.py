"""Tests for check-press-agent-certs.py — the issuer + expiry logic."""

import datetime as dt
import importlib.util
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location(
    "check_press_agent_certs", HERE / "check-press-agent-certs.py"
)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def make_cert(*, issuer_org: str, days_until_expiry: int) -> dict:
    expiry = dt.datetime.utcnow() + dt.timedelta(days=days_until_expiry)
    return {
        "issuer": [
            (("countryName", "US"),),
            (("organizationName", issuer_org),),
            (("commonName", "E7"),),
        ],
        "notAfter": expiry.strftime("%b %d %H:%M:%S %Y GMT"),
    }


def test_le_cert_with_60_days_left_is_ok():
    cert = make_cert(issuer_org="Let's Encrypt", days_until_expiry=60)
    with patch.object(MOD, "probe_cert", return_value=cert):
        assert MOD.issues_for("test", "example.com") == []


def test_self_signed_cert_is_flagged():
    cert = make_cert(issuer_org="Self Signed", days_until_expiry=60)
    with patch.object(MOD, "probe_cert", return_value=cert):
        findings = MOD.issues_for("test", "example.com")
        assert any("NOT Let's Encrypt" in f for f in findings)


def test_le_cert_expiring_in_5_days_is_flagged():
    cert = make_cert(issuer_org="Let's Encrypt", days_until_expiry=5)
    with patch.object(MOD, "probe_cert", return_value=cert):
        findings = MOD.issues_for("test", "example.com")
        assert any("expires in 5 days" in f for f in findings)


def test_le_cert_already_expired_is_flagged():
    cert = make_cert(issuer_org="Let's Encrypt", days_until_expiry=-3)
    with patch.object(MOD, "probe_cert", return_value=cert):
        findings = MOD.issues_for("test", "example.com")
        assert any("EXPIRED 3 days ago" in f for f in findings)
