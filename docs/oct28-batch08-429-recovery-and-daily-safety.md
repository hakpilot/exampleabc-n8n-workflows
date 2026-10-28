# ExampleABC Oct 28 2026 outbound incident and safe recovery
## Reconciled sends
Batch08 prospect IDs 96–145: 50/50 have Status SENT and distinct Gmail message IDs in Batch08 Send Log. The controlling run was started at 08:00 America/New_York and n8n execution 1473 failed **after Gmail sends** on the node "Re-read Batch07 Ledger After Loop" because Google Sheets returned HTTP 429. Do NOT rerun this batch. Control may remain RUNNING until reconciliation is addressed; SENT ledger takes precedence over stale control status.
Individually confirmed same-day followups: #7 Kim (Gmail id 1a1826ae0cc460fa; From hyder@exampleabc.com, To kim@jimcarlsautobody.com); #25 Jenn (Gmail id 1a1826afdf3f0582; From hyder@exampleabc.com, To jenn@mccabeelectric.net). Do NOT resend.
Two new hard bounces, already recorded in Contact Exceptions: #139 mark@1stclasshomeimprovement.com domain NXDOMAIN; #145 favio@aquapainting.com SMTP 550. Maintain also #77 unsubscribe, #87 and #92 hard bounces, #24 decline.

## Required remediation
1. Refuse any send when a prospect-step already has Gmail message ID OR Gmail history shows sent correspondence, irrespective of Batch control RUNNING/ERROR. Use a persistent idempotency key prospect_id+recipient+touch_step, and a claim before send; on uncertain provider outcome reconcile Gmail instead of retrying.
2. Avoid per-message Google Sheets reads/writes: read Prospects, Drafts, Exceptions and send log ONCE per batch with bounded ranges, cache in workflow, and flush logged results in batches. If provider transaction returns Gmail ID, append to persistent ledger as early as practical; distinguish Gmail accepted from delivered. Rate limiting: exponential backoff with jitter respecting Retry-After; 429 should hold final reconciliation, not trigger any resend of already accepted messages.
3. Fix wrong-sheet references: Batch08 currently references Batch07 in node names for ledger post-check. Confirm exact sheet ID/title before write; never depend on a different batch's 20-count invariants.
4. Separate daily pipeline phases: (A) verified local-business research, 30/day target and duplicate crosscheck; (B) current-eligible first-touch sends, explicit From hyder@exampleabc.com and single To; (C) daily FU1-FU4 according to W:Z fixed A-2/B-3/C-4 allocation and sent timestamps; (D) daily Gmail inbound/bounce/unsubscribe scan and per-prospect checklist/report.
5. Stop-on-any-human-reply; permanently suppress opt-out/decline; hold hard bounces; review soft bounces and OOO; never text an opted-out contact.
6. Use timezone America/New_York, Mon-Fri 8AM. Daily trigger must be published after safe dry run, not merely saved in STAGING. Existing STAGING v2 only contains a Schedule Trigger and a Set node; it does NOT perform research or send emails.
7. QA on personal internal-only inbox before activation: From/To/MIME, Reply-To and threadId, original message subject, correct provider IDs, pre-send duplicate check, bounce/opt-out after sending but before following up, partial failure/resume with 429 injected, daily run with zero qualifying contacts.

Status: incident documented; automated daily n8n pipeline not deployed nor activated by this update.
