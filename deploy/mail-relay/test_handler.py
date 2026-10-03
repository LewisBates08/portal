import hashlib
import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError


def load_handler():
    spec = importlib.util.spec_from_file_location("relay", Path(__file__).with_name("handler.py"))
    module = importlib.util.module_from_spec(spec)
    with patch("boto3.client", return_value=Mock()) as factory:
        spec.loader.exec_module(module)
    return module


relay = load_handler()
TOKEN = "test-relay-token-" * 4


def event(**payload):
    return {"requestContext": {"http": {"method": "POST"}},
            "headers": {"authorization": "Bearer " + TOKEN},
            "body": json.dumps({"recipient": "pilot@example.com", "subject": "Account action",
                                "text": "Private account action", **payload})}


def setup_function():
    relay.ses.reset_mock()
    relay.ses.send_email.side_effect = None
    os.environ["TOKEN_SHA256"] = hashlib.sha256(TOKEN.encode()).hexdigest()
    os.environ["SENDER"] = "sender@example.com"
    os.environ["ALLOWED_RECIPIENTS"] = "pilot@example.com"


def test_rejects_unauthenticated_without_sending():
    request = event()
    request["headers"] = {}
    assert relay.handler(request, None)["statusCode"] == 401
    relay.ses.send_email.assert_not_called()


def test_pins_sender_and_accepts_only_approved_recipient():
    assert relay.handler(event(sender="attacker@example.com"), None)["statusCode"] == 202
    args = relay.ses.send_email.call_args.kwargs
    assert args["FromEmailAddress"] == "Searchroom <sender@example.com>"
    assert args["Destination"] == {"ToAddresses": ["pilot@example.com"]}
    relay.ses.reset_mock()
    assert relay.handler(event(recipient="other@example.com"), None)["statusCode"] == 403
    relay.ses.send_email.assert_not_called()


def test_invalid_payload_never_sends():
    for payload in ({"recipient": "a@example.com,b@example.com"}, {"subject": "x\r\nBcc: bad"}, {"text": "x" * 64001}):
        assert relay.handler(event(**payload), None)["statusCode"] == 400
    relay.ses.send_email.assert_not_called()


def test_provider_failure_is_retryable_and_redacted():
    relay.ses.send_email.side_effect = ClientError(
        {"Error": {"Code": "MessageRejected", "Message": "private-recipient"}}, "SendEmail")
    result = relay.handler(event(), None)
    assert result["statusCode"] == 503
    assert "private-recipient" not in result["body"]
