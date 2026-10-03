"""Authenticated Railway-to-SES bridge. Never log request bodies or credentials."""

import base64
import hashlib
import hmac
import json
import os
import re

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

ses = boto3.client("sesv2", config=Config(
    connect_timeout=3, read_timeout=8,
    retries={"mode": "standard", "total_max_attempts": 1},
))


def response(status, detail):
    return {"statusCode": status, "headers": {
        "content-type": "application/json", "cache-control": "no-store",
    }, "body": json.dumps({"status": detail})}


def handler(event, context):
    if event.get("requestContext", {}).get("http", {}).get("method") != "POST":
        return response(405, "method_not_allowed")
    authorization = event.get("headers", {}).get("authorization", "")
    expected = os.environ["TOKEN_SHA256"]
    supplied = authorization.removeprefix("Bearer ")
    if not authorization.startswith("Bearer ") or not hmac.compare_digest(
        hashlib.sha256(supplied.encode()).hexdigest(), expected
    ):
        return response(401, "unauthorized")
    try:
        raw = event.get("body") or ""
        if len(raw) > 90000:
            return response(413, "message_too_large")
        if event.get("isBase64Encoded"):
            raw = base64.b64decode(raw, validate=True).decode("utf-8")
        payload = json.loads(raw)
        recipient = payload["recipient"]
        subject = payload["subject"]
        body = payload["text"]
        if (not isinstance(recipient, str)
            or not re.fullmatch(r"[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+", recipient)
            or len(recipient) > 254
            or not isinstance(subject, str) or not 1 <= len(subject) <= 200
            or "\r" in subject or "\n" in subject
            or not isinstance(body, str) or not 1 <= len(body) <= 64000):
            return response(400, "invalid_message")
    except (ValueError, KeyError, TypeError, UnicodeError):
        return response(400, "invalid_message")
    # Explicit pilot restriction; SES independently enforces its sandbox rules.
    allowed = {value.strip().lower() for value in os.environ["ALLOWED_RECIPIENTS"].split(",")}
    if recipient.lower() not in allowed:
        return response(403, "recipient_not_enabled")
    try:
        ses.send_email(
            FromEmailAddress="Searchroom <" + os.environ["SENDER"] + ">",
            Destination={"ToAddresses": [recipient]},
            Content={"Simple": {
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
            }},
        )
    except (ClientError, BotoCoreError):
        # Let the encrypted application outbox retry without logging PII.
        return response(503, "temporarily_unavailable")
    return response(202, "accepted")
