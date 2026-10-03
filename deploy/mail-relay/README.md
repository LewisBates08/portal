# Searchroom email relay

This CloudFormation stack sends the application's encrypted outbox messages
through SES in London. Railway holds a random bearer credential; Lambda holds
only its SHA-256 digest and uses a role limited to `ses:SendEmail` from the
configured sender. No AWS access keys are stored in Railway.

`template.json` embeds `handler.py` in `Resources.Relay.Properties.Code.ZipFile`.
Keep those copies identical when changing the handler. Validate with cfn-lint
1.57.1, cfn-guard 3.2.1 using `security.guard`, the handler tests, and AWS
CloudFormation validation before deploying. The custom Guard rules check this
stack's constraints; they are not a comprehensive compliance certification.

Parameters: `Sender`, comma-separated `AllowedRecipients`, and `TokenSha256`.
Deploy with `CAPABILITY_IAM`; read `RelayUrl` from stack outputs. Never put the
bearer credential in a template, command argument, commit, or deployment log.
Use a dedicated deployment role for routine ongoing administration.

The function URL is publicly reachable but rejects sending without the private
bearer credential. It accepts one approved recipient per request, pins the
sender, rejects malformed input, and returns only a generic provider error.
The application follows no redirects and retries failures through its outbox.
Provider acceptance does not prove inbox delivery, and a timeout after provider
acceptance can cause a duplicate on retry.

## Pilot operation

Sender and recipient are `batesyboys@outlook.com`. SES is still in its sandbox;
the relay and portal also enforce this recipient allowlist. An Outlook address
can be verified for testing, but this stack cannot configure Outlook's domain
authentication. Before sending to clients, obtain SES production access and
configure an owned, authenticated sending domain, then deliberately update both
allowlists and the stack's sender parameter as appropriate.

The Railway `mail` service runs `python /app/bootstrap.py python -m
app.operations mail-loop` continuously, using private references to the portal's
database, encryption and relay configuration. It needs no public domain or HTTP
healthcheck. To test through the real queue without creating an account, run
`python /app/bootstrap.py python -m app.operations mail-test --recipient
batesyboys@outlook.com` once. Remove a one-time test pre-deploy command afterwards.

For failures, inspect deployment-specific Railway worker logs for
`mail_delivery_failed`; `app.operations check` detects exhausted retries.
CloudWatch keeps Lambda logs for 14 days and an Errors alarm for unhandled
runtime failures. That alarm has no notification destination and does not detect
every SES rejection. No CloudTrail trail was configured by this deployment.
Lambda, SES, logs, the alarm and the Railway worker can incur usage charges.

To rotate the relay credential, pause mail delivery, generate a new random
credential, update the stack with its hash and the private Railway variable
with the credential, then redeploy the worker and resume delivery. Do not print
the old credential. To disable email, set `MAIL_ENABLED=false` on both services.
