# IMPORTANT: October 26, 2026 Gmail Sender Incident — SAFETY HOLD

**This section supersedes the prior release instructions below. DO NOT trigger any user-facing outreach release yet.**

- On October 26, 31 follow-up emails were sent by a Gmail OAuth credential with the underlying HIRA account, yielding actual `From: hyder@hiratechnologies.net` and reply-all `To` that included the business alias or HIRA address alongside the prospect. All 31 send ledger Gmail IDs are retained and marked as incident in the tracker. **Do not resend them.**
- The remaining 20 Batch06 initial emails (#56–75) are **unsent; approval remains HOLD**.
- The Gmail OAuth credential's allowed HTTP request domains have been changed to **Specific Domains: gmail.googleapis.com** (not all domains), enabling restricted official Gmail API operations.
- **QA11 PASSED:** self-only API test with exact RFC822 `From: hyder@exampleabc.com`, `To: hakpilot@gmail.com` and empty CC/BCC, confirmed from actual MIME. Sent message `1a17a3419cc3fa7b`.
- **QA12 PASSED:** self-only reply with RFC822 `From: hyder@exampleabc.com`, `To: hakpilot@gmail.com`, preserved `threadId: 1a17a3419cc3fa7b`, and correct In-Reply-To / References headers. Sent message `1a17a367120dcc41`.
- The three LOCKED production source workflows are now replaced with **explicit Gmail API raw-MIME sender nodes** in place of n8n native Gmail Send/Reply. The follow-up workflows also read the original RFC822 metadata to construct the Reply headers. **All HTTP POST sends and Sheets writes remain disabled**; their n8n deployments passed source validation.
- The offline safety/JS syntax validation passed via GitHub Actions run **40409298161**.
- All three future release scripts contain a hard-coded fail-closed `INCIDENT_20261026_SENDER_SAFETY_HOLD` at function entry; older approval artifacts or old documentation must not be used to launch. Before re-enabling outreach, run a controlled self-only integrated test of the new production path, then receive a **fresh user approval** and perform complete Monday-or-later Gmail and Sheet status reconciliation. No partial batch may be retried blindly.

**Workflow links**: [Batch06 27-node locked](https://auto.exampleabc.com/workflow/oOTxtl5hkMW3I9ZNntQE4), [Batch34 26-node locked](https://auto.exampleabc.com/workflow/4zgYbHHOcmxaXuQ1), [Batch05 26-node locked](https://auto.exampleabc.com/workflow/emudjS3OMOY3yfep).

---

# ExampleABC Sales Outreach Automation — Final Review & Launch

**Updated and verified Monday, October 26, 2026.** The Google Sheets/n8n/Gmail integration is deployed. Prospect sending is still **LOCKED** pending the owner's explicit review and approval.

## Queued Batches

| Batch | Scope | Approval control | Send log |
|---|---|---|---|
| Initial Batch 06 | 20 initial messages, Prospects #56–75 | `Batch06 Control!B2` = `HOLD` | `Batch06 Send Log` |
| First follow-ups from Batches 03–04 | 16 messages replying to original Oct 14–15 threads | `Batch34 Followup Control!B2` = `HOLD` | `Batch34 Followup Log` |
| Batch 05 first follow-ups | 15 messages replying to Oct 20 original threads #41–55 | `Batch05 Followup Control!B2` = `HOLD` | `Batch05 Followup Log` |

**Tracker**: https://docs.google.com/spreadsheets/d/1DyUlbmRlapp3fZTVSX8pLat0oPNPDKowA7qgCzsyqzY/edit

Review initial message **subjects, recipients, full bodies, opt-out wording** in `Email Drafts` rows **57–76** and compare against `Batch06 Send Log`.

Review follow-up bodies in `Email Drafts` column H for 16 IDs in `Batch34 Followup Log` and 15 IDs in `Batch05 Followup Log`. Four exceptions (#24, #25, #29, #31) are excluded. Do not contact an explicit refusal, unmonitored inbox or hard-bounced address. Followups must be replies in existing threads, not new initial emails.

## Already Verified (All QA runs are temporarily activated then shut down)

1. **QA4:** Two paced messages from the verified ExampleABC Gmail OAuth to the business's **own ExampleABC inbox**, each with a confirmed Gmail ID and n8n-to-**Automation QA** Google Sheets writeback; passes.
2. **QA5:** Original ExampleABC Gmail message to the user's **own personal Gmail** `hakpilot@gmail.com`, followed by a Gmail Reply preserving the same Gmail thread; the intended recipient was present. Reply-all also added an internal HIRA copy; passes with this known behavior.
3. **QA6:** Live read-only preflight executed inside n8n on Batch06: exactly 20 candidates and zero prior Gmail correspondence; passes.
4. **QA7:** Live read-only original-thread checks inside n8n across 16 older follow-ups: expected thread and message, SENT label and recipient all verified; passes.
5. **QA8:** Live read-only original-thread checks inside n8n across 15 Batch05 follow-ups: all 15 original Oct 20 emails/threads, SENT label and recipient verified; passes.
6. **GitHub Actions** securely deploys locked workflows using repository secret `N8N_API_KEY`, binding existing **tested ExampleABC** Gmail and Sheets OAuth references. A separate offline validation of future one-time release scripts and embedded JavaScript succeeds. No API keys, OAuth tokens or passwords are committed in this repository.

## Production Source Workflows (LOCKED)

- [Batch06 initial outreach](https://auto.exampleabc.com/workflow/oOTxtl5hkMW3I9ZNntQE4): 26 nodes, all Gmail Sends and Sheets writes disabled; no schedule or active triggers
- [Batch34 original-thread followups](https://auto.exampleabc.com/workflow/4zgYbHHOcmxaXuQ1): 24 nodes, all Gmail Replies and Sheets writes disabled
- [Batch05 original-thread followups](https://auto.exampleabc.com/workflow/emudjS3OMOY3yfep): 24 nodes, all Gmail Replies and Sheets writes disabled

Both have a strict approval gate, duplicate/status/draft/exception checks, single-item looping with 5-second pacing, Gmail confirmation, per-message ledger writeback, original status updates, and a final re-read of the entire send log before claiming completion.

## Owner Final Approval — Required BEFORE Any Prospect Sending

After reading the actual subjects, recipients and complete bodies, the owner can approve each batch **separately** in ChatGPT:

- **Initial batch:** `I APPROVE BATCH 06: SEND 20 INITIAL EMAILS`
- **Older follow-ups:** `I APPROVE BATCH 34: SEND 16 FIRST FOLLOWUPS`
- **Batch05 follow-ups:** `I APPROVE BATCH 05: SEND 15 FIRST FOLLOWUPS`

Specify desired send timing (for example "today" or "Monday morning"). Until that explicit approval, **keep BOTH control cells on HOLD**; do not click Execute, activate workflows, create approved release files, or send prospects through QA.

Once approval is given, ChatGPT re-reads Google Sheets and Gmail, calculates a recipient fingerprint over the approved exact IDs/addresses, confirms the approval still applies, then changes only that batch's control cell to its exact approval option and creates **one corresponding version-controlled release request**:

- `release_requests/Batch06_Approved.json` → [.github/workflows/batch06_approved_release.yml](.github/workflows/batch06_approved_release.yml)
- `release_requests/Batch34_Followups_Approved.json` → [.github/workflows/batch34_approved_followups_release.yml](.github/workflows/batch34_approved_followups_release.yml)
- `release_requests/Batch05_Followups_Approved.json` → [.github/workflows/batch05_approved_followups_release.yml](.github/workflows/batch05_approved_followups_release.yml)

The release job creates a **distinct, signed-webhook, single-use** production workflow from the verified locked source and enables its sender/writeback nodes only in that one release copy. It verifies the approved contact fingerprint at runtime, the live one-use Google Sheets approval control, and the current Gmail/thread/suppression status **before** messaging. Each accepted Gmail message/reply is logged before the next item, with 5-second pacing. On completion (or any error), the job deactivates the release webhook; its execution and logs remain auditable. **No one needs to send messages manually.**

### Failure / Partial-Send Rule

If an execution fails or times out, **do not replay the release request or manually click Execute**. Approval is consumed to `RUNNING` before sending. First reconcile Gmail Sent with the batch's send log and original Prospect/Draft statuses; manually resolve any uncertain send before deciding a safe recovery. A successful Gmail API response is not proof of delivery; monitor bounces and opt-out replies.

**No queued prospects have been sent by this automation as of Monday October 26, 2026, noon Eastern.**
