"""Asking the ASTRA agent 'what version are you?' answers with the device's real agent
version instead of the generic assistant reply."""
from app.services.conversations import _is_version_question
from tests.test_remediation import _enroll


def test_version_question_detection():
    assert _is_version_question("what is your version")
    assert _is_version_question("which version are you running")
    assert _is_version_question("astra version?")
    assert _is_version_question("agent version")
    assert _is_version_question("what version are you")
    # Not about the agent — the OS or another app:
    assert not _is_version_question("what version of windows do i have")
    assert not _is_version_question("update my outlook please")
    assert not _is_version_question("clear my temp files")
    assert not _is_version_question("my pc is slow")


async def test_device_chat_reports_its_agent_version(client, admin_headers):
    enroll = await _enroll(client, admin_headers)   # enrolls reporting agent_version "0.1.0"
    device_headers = {"Authorization": f"Bearer {enroll['device_token']}"}

    resp = await client.post(
        "/api/v1/agent/chat", json={"content": "what is your version?"}, headers=device_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source"] == "version"          # handled directly, not the generic engine reply
    assert "0.1.0" in body["reply"]             # the real reported agent version
    assert "RMD-PC" in body["reply"]            # names the device (default _enroll hostname)
