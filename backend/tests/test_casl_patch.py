"""
Regression tests for the CASL global patch (utils/casl_patch.py).
Verifies that Resend.Emails.send is wrapped so every outbound email
automatically gets the CASL footer.
"""
import sys
import os
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_casl_patch_installs_on_resend():
    import resend
    from utils.casl_patch import install_casl_patches
    # Remove any previous patch marker so we can test clean install
    if hasattr(resend.Emails, "_aurem_casl_patched"):
        delattr(resend.Emails, "_aurem_casl_patched")

    install_casl_patches()
    assert getattr(resend.Emails, "_aurem_casl_patched", False) is True


def test_casl_patch_injects_footer_into_html():
    import resend
    from utils.casl_patch import install_casl_patches

    install_casl_patches()

    # Stub the underlying send so we don't hit the network
    captured = {}
    def spy(params):
        captured["params"] = params
        return {"id": "stub-id"}
    # Replace the RAW callable inside the patched send by re-patching its inner _orig_send
    # via temporarily swapping the Emails.send (the patched wrapper calls _orig_send
    # captured at patch time, so we swap _orig_send through a re-import trick):
    # easier: directly test by calling the patched send — since install_casl_patches
    # captured the real send, we install a NEW patch against our spy below.
    # Undo patch and re-patch after substituting send.
    if hasattr(resend.Emails, "_aurem_casl_patched"):
        delattr(resend.Emails, "_aurem_casl_patched")
    resend.Emails.send = spy
    install_casl_patches()

    resend.Emails.send({
        "from": "a@b", "to": ["customer@test.com"],
        "subject": "t", "html": "<p>Hello</p>",
    })

    html_out = (captured.get("params") or {}).get("html", "")
    assert "Unsubscribe" in html_out
    assert "AUREM Intelligence" in html_out
    assert "CASL Section 6(6)" in html_out


def test_casl_patch_is_idempotent():
    """Calling install_casl_patches twice must not double-wrap emails."""
    import resend
    from utils.casl_patch import install_casl_patches

    # Start clean
    if hasattr(resend.Emails, "_aurem_casl_patched"):
        delattr(resend.Emails, "_aurem_casl_patched")

    captured = {}
    def spy(params):
        captured["params"] = params
        return {"id": "stub"}
    resend.Emails.send = spy
    install_casl_patches()
    install_casl_patches()  # should be a no-op

    resend.Emails.send({
        "from": "a@b", "to": ["x@y.com"],
        "subject": "t", "html": "<p>Hi</p>",
    })
    html_out = (captured.get("params") or {}).get("html", "")
    # Footer contains "unsubscribe" twice (URL + visible label) — count the FOOTER markers
    # to prove we only appended ONE footer block, not two.
    assert html_out.count("CASL Section 6(6)") == 1
    assert html_out.count("<hr style=") == 1


def test_casl_patch_wraps_plaintext_too():
    import resend
    from utils.casl_patch import install_casl_patches

    if hasattr(resend.Emails, "_aurem_casl_patched"):
        delattr(resend.Emails, "_aurem_casl_patched")

    captured = {}
    def spy(params):
        captured["params"] = params
        return {"id": "stub"}
    resend.Emails.send = spy
    install_casl_patches()

    resend.Emails.send({
        "from": "a@b", "to": ["x@y.com"],
        "subject": "t", "text": "Plain body",
    })
    text_out = (captured.get("params") or {}).get("text", "")
    assert "Unsubscribe" in text_out
