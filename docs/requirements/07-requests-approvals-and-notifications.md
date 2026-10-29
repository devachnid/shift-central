# 07 — Requests, approvals and notifications

All notifications go by **email and phone push notification** (NOTIF-01).

## Leave request workflow

1. A staff member opens "request time off" (phone or PC), picks the type and dates (whole days, half day, or start/end times) and can overtype the description.
2. Before sending they see their **balance before and after**, and **the cost of each day** (REQ-02).
3. If they don't have enough balance, or any date is in a **blackout period**, they cannot send it (REQ-05, REQ-08).
4. Every manager with access to their team is **notified** and the request appears on the **"waiting for approval"** list (REQ-12).
5. If still waiting after **3 working days**, those managers get a **reminder** (REQ-13).
6. One manager approves or declines. The staff member is **notified** (REQ-14).
7. On approval, each day is costed from the shift, then the shift is **removed** (or **shortened** for part days) (ROTA-10).

## Requirements

**REQ-01** — Staff request their own leave; **a manager must approve it**. Managers can book leave for anyone; a manager's booking is **approved straight away**.

**REQ-02** — While requesting, staff see **their balance before and after**, with the cost of each day. They are not shown who else is off or their shifts on that screen (they can see colleagues' leave elsewhere).

**REQ-03** — One level of approval. Any manager with access to the person's team can approve (PEOPLE-04, 05).

**REQ-04** — Managers can approve each other's requests but **not their own**. The practice manager's own leave is recorded without approval.

**REQ-05** — Staff cannot request more than their balance; managers can override (LEAVE-20, LV-24).

**REQ-06** — Requests are **never approved automatically**.

**REQ-07** — Staff can request **2027 leave from the day the app opens to them, before 1 January 2027**.

**REQ-08** — **Blackout periods**: managers set date ranges, for one or more teams or everyone. Staff **cannot request** leave in them; managers **can still book** leave there.

**REQ-09** — Sickness, maternity, paternity, adoption, KIT days, dependants' leave, unauthorised absence, jury service and bank holidays are **recorded by managers**, not requested (LEAVE-25).

**REQ-10** — **Cancelling approved leave:** the staff member requests cancellation; **a manager approves** it. Once approved, the hours go back on their balance, the **original shift is restored**, and the staff member and managers are notified.

**REQ-11** — Leave clashes between the GP rota app and the new system are allowed and **flagged to managers** (ROTA-GP-04).

## Notifications

**NOTIF-01** — Every notification below is sent by **email and push notification** to the phone app.

| ID | Event | Who | When |
|---|---|---|---|
| REQ-12 | New leave or cancellation request | All managers with access to that team | Straight away; also on the "waiting for approval" list |
| REQ-13 | Request still waiting | Same managers | After **3 working days** (setting managers can change) |
| REQ-14 | Leave or cancellation approved / declined | The staff member | Straight away |
| NOTIF-02 | Rota changes | Each affected staff member — **one summary each** | Only when a manager presses **"notify staff"** (ROTA-09) |
| NOTIF-03 | Open shift posted | Whoever the manager chooses (team, teams, everyone) | When posted |
| NOTIF-04 | Open shift claim approved | The claimant | Straight away |
| NOTIF-05 | Sickness trigger reached (new level) | Managers | Straight away |
| NOTIF-06 | Leaving date entered | Managers | Straight away, and again **1 week before** the last day |
| NOTIF-07 | Return from long sickness or maternity/adoption/similar leave | Managers | On return, with remaining leave |
| NOTIF-08 | Year end | Managers | Start of new leave year: everyone with leave or TOIL left |
| NOTIF-09 | Leave booked on a placeholder, and again when recalculated | Managers | At booking and when the rota is set |
| NOTIF-10 | GP rota clash between the apps | Managers | When detected |
| NOTIF-11 | Hours change leaves a negative balance | Managers | When the change is entered |
| NOTIF-12 | Sickness entry joins on to an existing one | The manager entering it | On screen, at entry |

## Swaps and open shifts

**REQ-15** — Swaps: staff agree between themselves; a **manager changes the rota** and then notifies staff as usual.

**REQ-16** — Open shifts: posted by a manager; claimed by staff; **approved by a manager** (ROTA-11).

## Not needed, on purpose

- Maximum number off at once; notice periods for requesting or cancelling.
- Showing who else is off, or the person's shifts, on the request screen.
- Multi-level approval; delegation of approval.
- Automatic approval.
- Swap requests in the system.
- Daily digest emails; text messages (SMS).
- Return-to-work interview reminders (recorded outside the system).
