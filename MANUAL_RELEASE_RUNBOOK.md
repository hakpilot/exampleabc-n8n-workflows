# ExampleABC — Manual, One-Time n8n Outreach Release
**Operating standard established October 27, 2026**

## Outcome and audit trail

- **Batch 06 (#56–75): 20/20 sent**, Google Sheets `Batch06 Control!B2 = COMPLETE`. n8n manual workflow execution **#1435**, Gmail API sender `hyder@exampleabc.com`.
- **Batch 07 (#76–95): 20/20 sent**, `Batch07 Control!B2 = COMPLETE`.
- Gmail Sent and Sheets each contain 40 unique Gmail message IDs, with all Prospects and Email Drafts records marked **Sent**.
- The new batch release procedures did **not** resend the 31 October 26 follow-ups.
- The workflow checked the **actual Gmail From, sole To, empty CC/BCC headers after each of the 40 sends**. Independent full RFC822 header inspection was also performed on samples from both batches.
- Gmail acceptance is proof of submission, **not proof of inbox delivery**. Monitor for replies, hard bounces, opt-outs, and spam complaints before follow-ups.

## The two completed manual-release workflows (do not execute again)

1. [One-time Batch06](https://auto.exampleabc.com/workflow/d8ZjZSHB7ZiF4BDn)
2. [One-time Batch07](https://auto.exampleabc.com/workflow/0yJUcevQZnlL95VV)

Original **LOCKED** workflows remain unmodified backups. The disabled October 27 GitHub schedule is not part of this working manual procedure. Never reenable the expired schedule.

## Simple control model for *future* batches

| Control state in `BatchNN Control!B2` | Meaning |
|---|---|
| `HOLD` | Drafts may be prepared and reviewed, but no external sending is permitted. |
| `APPROVE BATCH NN` | Human approved precisely the recipients and contents frozen for this batch. |
| `RUNNING` | Single-use release consumed approval before sending; **do not run again**, even if UI later reports an error. |
| `COMPLETE` | All expected Gmail IDs are recorded in the batch ledger. Permanently close the release. |

### Repeatable operating procedure

1. Research new prospects, screen duplicate addresses and prior Gmail correspondence, and draft personalized subject/body/opt-out. Put them in existing `Prospects`, `Email Drafts`, and a new `BatchNN Send Log`. Keep `HOLD`.
2. Conduct **read-only** n8n preflight, verify exact recipient count and absence of previous Gmail threads, and freeze the reviewed recipient/subject/body hashes.
3. Build **new** manually triggered one-time workflow from the validated locked template using a new batch ID, prospect range, control sheet and send log. No scheduled or webhook triggers. Preserve all recipient/sender/opt-out, history, Gmail headers and ledger gates. Use `scripts/deploy_manual_one_time_batches.py` as the working pattern; update the configuration for the *new* batch, **not** these completed workflows.
4. Deploy without executing, inspect the editor. The one-time workflow has exactly **one** Gmail API POST and only the expected Google Sheets writers; sending nodes should be **enabled only in this separate manual-release copy**, not in locked backups.
5. Set the new batch's `Control!B2` dropdown to `APPROVE BATCH NN`. Open the manual release in n8n, click **Execute workflow once**, and wait for its final result. It must change the control to `RUNNING` first.
6. Verify **COMPLETE**, exact unique Gmail IDs for each prospect, `Prospects` and `Email Drafts` status sent, and actual Gmail RFC822 From/To/CC/BCC. If an error occurs, **do not execute again**: reconcile Gmail Sent against the ledger; then create a separate recovery plan for only *unsent* contacts.
7. After successful send, monitor replies, bounces and opt-outs and plan eligible follow-ups on their proper due dates. Do not blindly send follow-ups to already-contacted or opted-out prospects.

### Permanent sender safeguards

- Gmail API raw MIME: `From: Hyder Khan <hyder@exampleabc.com>`.
- To: **one approved prospect only**; never add `hyder@exampleabc.com`, `hyder@hiratechnologies.net`, or personal Gmail as a duplicate recipient.
- Never use n8n native Gmail Reply/Reply All for prospect follow-ups (the October 26 issue).
- After each Gmail API send, read message metadata and verify actual **From**, **one exact To**, and **empty CC/BCC** before logging or advancing to the next prospect.
- Save message ID, thread ID and time; update `Prospects` and `Email Drafts`; only then advance the loop.
- On follow-ups, use explicit MIME Reply headers (`In-Reply-To`, `References`) and original Gmail `threadId`, with fresh opt-out suppression checks.

### Controls we should **not** recreate

- A hard-coded execution clock that silently makes manual sending impossible after a deadline.
- A separate scheduled safety task that disables a fully approved manual release without reconciling current user approval.
- An opaque, manually toggled set of six disabled send/log nodes on the production backup.
- Separate scripts that send duplicates because one ledger was not reconciled.

**Key principle:** Make `HOLD` an easy business-control dropdown, and make `RUNNING/COMPLETE` hard one-time safety latches. Keep the compliance-critical sender, recipient and deduplication checks non-optional. Distinguish user-controlled operational switches from platform-level permissions.
