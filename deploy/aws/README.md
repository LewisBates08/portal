# AWS pilot deployment — implementation in progress

These files are an unfinished deployment draft, not a ready-to-apply release.
The AWS Agent Toolkit setup was requested during implementation and is now
installed locally. Restart Codex to load its MCP server before continuing.

Selected architecture: London (`eu-west-2`), EC2 `t3.small`, private PostgreSQL 17
RDS `db.t4g.micro`, HTTPS through Caddy, SES, S3 backups, ECR and SSM.
Monthly ceiling: GBP75 including tax and temporary staging. Alert recipient:
lewisbates2008@outlook.com. The local AWS profile is `searchroom`; it currently
uses a root sign-in, so establish a dedicated deployment role before provisioning.
No AWS application resources have been created.

Remaining implementation and validation:
- Finish host control.py (secure configuration, database role initialization,
  migrations, digest deployment, backups, metrics and failure handling).
- Add the GitHub OIDC release workflow using successful readiness artifacts.
- Format and validate Terraform, lock providers, test host scripts and CI.
- Replace the old DigitalOcean deployment documentation and env example.
- Review current AWS pricing against the budget before setting cost_reviewed.
- Resolve tracked recoverycodes.txt without exposing its content.
- Provision staging, configure secrets outside Terraform, verify DNS, SES,
  HTTPS, permissions, restore and reboot behaviour before production.

DNS access is not yet available. The DNS administrator will need A records for
`portal.radiumsearch.com` and `staging.portal.radiumsearch.com`, pointing to each
environment's Terraform `host_ip` output. SES also needs the generated domain
verification TXT and DKIM CNAME records. Do not invent IP addresses or publish
DNS records before provisioning and reviewing the actual outputs.
