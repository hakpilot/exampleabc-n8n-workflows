# ExampleABC Follow-up A/B Test and Daily Exception Handling
Status: DESIGN / READ-ONLY rollout. NO automated outbound emails authorized by this file.
Date: 2026-10-27

## Cohort and assignment
- Initial eligible pool: Batch06 prospects 56-75, Batch07 prospects 76-95.
- Within each batch, allocate 10 to Arm A and 10 to Arm B using a fixed, auditable seeded shuffle; never rerandomize a contact.
- Arm A: first follow-up (FU1) and second follow-up (FU2).
- Arm B: FU1, FU2, and third follow-up (FU3).
- Do not enroll known hard bounces, opt-outs, negative replies or active discussions. Preserve exclusion reason and randomized denominator for intent-to-treat analysis.
- Target review dates: FU1 2026-11-02, FU2 2026-11-09, FU3 2026-11-17 (ET; Arm B only). These are review dates, NOT automatic send dates.
- Earlier Batches 01–05 remain in their existing completed sequences; do not send additional touches until reviewed under a separate migration plan.

## Required per-prospect fields
prospect_id, cohort_batch, normalized_recipient, company, experiment_arm,
original_message_id, original_thread_id, followup_step, last_send_at,
next_review_date, state, suppression_reason, last_exception_checked_at,
latest_provider_message_id, positive_reply, booked_call, proposal, deposit.

## Daily read-only reconciliation at 8:30 AM America/New_York on weekdays
1. Read Gmail threads and sender notification inbox since last successful scan,
   with overlapping lookback to avoid missing delayed bounces.
2. Read exact recipient and original Gmail message ID from send log.
3. Detect delivery status notifications, including mailer-daemon and postmaster;
   parse status code and match to prospect and address.
4. Human response: pause sequence for classification and owner response.
5. Hard bounce (5xx/NXDOMAIN/no such recipient): mark BOUNCED-HOLD; suppress
   the recipient from future sends until a *verified* new address is approved.
6. Soft bounce (4xx): TEMP-HOLD, investigate before retry; do not blindly resend.
7. Unsubscribe/stop/not interested: permanently suppress.
8. Automatic OOO reply: hold for review; don't treat it as positive response.
9. Compare actual Gmail SENT and message IDs against send log, report mismatches.
10. Return dashboard: eligible due today, upcoming, replies, bounces,
    unsubscribes, call bookings, gaps and exceptions. No send action.

## Two existing October 27 exceptions
- Prospect #87 The Home X: hello@thehomex.com. SMTP 550 5.1.1 / 5.4.1
  rejected; mailer notice id 1a17dc1f5dc07f1a. Suppress pending verification.
- Prospect #92 Flow Rite Contractors: sales@flowritenj.com. MX lookup NXDOMAIN,
  notice id 1a17dbc5803ca352. Suppress pending verified new domain/address.

## Future send gate (disabled)
- EXACT FROM hyder@exampleabc.com and approved reply address, verified at MIME
  header level; reject unapproved underlying sender identity.
- EXACT TO one designated prospect; no reply-all, CC or accidental self-address.
- In-Reply-To, References and Gmail thread ID match original conversation.
- Check reply, bounce, opt-out, negative outcome again immediately before send.
- Acquire idempotent lock keyed by prospect_id+sequence_step; reconcile history
  before retrying any ambiguous provider result.
- Only emit Gmail message ID after provider confirms acceptance; record
  accepted != delivered. Preserve accurate postal address and easy opt-out.
- Failure in any check => HOLD and notify, not an automatic override.

## Experimental readout
Primary: qualified positive replies and booked discovery calls per randomized
prospect; secondary: meetings held, proposal, paid deposit, opt-outs and hard
bounces. Include denominators and exclusions; compare incremental value of FU3.
With only 20 per arm, results are directional, not statistically definitive.

## Deployment checklist
[ ] Assign the two arms in the live tracker and persist.
[ ] Create per-prospect daily review tracker.
[ ] Deploy and test n8n read-only daily workflow.
[ ] Confirm all Gmail and Sheets exception reconciliations.
[ ] Review sender identity, threading and idempotency before enabling any sends.
