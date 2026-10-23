# ExampleABC Outreach Automation — Operator Guide

**Status as of October 23, 2026:** This repository contains safe, locked workflow packages for n8n. They are **not production-approved** and cannot send outreach while sender nodes remain disabled. The Google Sheets approval controls both default to `HOLD`.

## What is prepared

- **Batch 06:** 20 initial personalized outreach emails, prospects #56–75, in the existing Google Sheets tracker. Original `Email Drafts` and `Prospects` rows remain unsent. The review workflow was directly imported into n8n on October 23. Locked deployment JSON: `ExampleABC_Batch06_FINAL_REVIEW_SENDING_LOCKED.json`.
- **Batches 03–04:** 16 first follow-ups with verified Gmail original message/thread IDs. The review spreadsheet tabs are `Batch34 Followup Control` and `Batch34 Followup Log`. The four known exceptions (#24, #25, #29, #31) are **not included**. Locked workflow file: `ExampleABC_Batch34_Followups_THREAD_REPLIES_LOCKED.json`.
- Separate internal QA has confirmed a single Gmail send to `hyder@exampleabc.com` and an n8n-to-Sheets update of the `Automation QA` row. The **complete batch loop/send/reconciliation pipeline is not end-to-end verified yet**.

## One-time stable deployment setup (no secrets in source files)

1. In `https://auto.exampleabc.com`, open **Settings → n8n API → Create API Key**. Prefer the minimum available scopes: `credential:list`, `workflow:list`, `workflow:read`, `workflow:create`, `workflow:update`. If scoped keys are not supported by the n8n edition, protect the key as full-access.
2. In GitHub open `hakpilot/exampleabc-n8n-workflows` → **Settings → Secrets and variables → Actions → New repository secret**. Set **Name** to `N8N_API_KEY` and **Secret** to the entire n8n key. Never enter it in a chat or commit it in a file.
3. After setup, push a reviewed change to **one of the two whitelisted locked workflow JSONs**, or go to GitHub **Actions → Deploy ExampleABC LOCKED n8n Workflows → Run workflow (both)**.
4. Read the GitHub Actions result. The deployer only creates/updates *inactive LOCKED* workflows, resolves existing n8n OAuth credential IDs by exact name, verifies all mail sends/replies and sheet writes are deactivated, and prints the resulting n8n links. It does not execute a workflow.

## Final review and launch — NOT YET ENABLED

**Do not change the approval cells or enable sender nodes yet.**

The completion checklist for each batch is:
- Confirm the n8n send/reply credential is `hyder@exampleabc.com`; the Sheets credential is `ExampleABC Google Sheets`. Never use a Jafaria account.
- Confirm recipient addresses, full message bodies, original thread IDs for follow-ups, bounces, opt-outs, and replies immediately before launching.
- Pass a controlled self-only end-to-end test of one-item loop, five-second spacing, Gmail message-ID capture, and reliable Sheets writeback.
- For follow-ups, verify the **Reply** operation stays in the intended *existing* thread and does not direct the reply solely to the user's own address; this behavior requires a real sent-thread QA.
- Only after an explicit final batch review may the separately reviewed live sender be enabled.
- A production operator then changes the correct Control tab approval from `HOLD` to the exact approval option and manually executes the **approved live workflow exactly once**. The workflow consumes approval, sends sequentially, records Gmail IDs first, and updates original rows. Never retry an interrupted send until Gmail Sent and the log are reconciled.

## Rules

- **No prospect email is sent on importing these locked files.**
- Gmail API acceptance is not proof of delivery. Monitor bounce replies and explicit opt-outs.
- Never respond to `Tindall & Ranson (#24)` after an explicit no-interest; do not use hard-bounced addresses.
- Keep Batch 06 initial outreach separate from Batch 03/04 replies.
- Keep the source repository free of credentials and personal OAuth tokens.
