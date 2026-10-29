# 10 — Migration and go-live

**MIG-01** — **Nothing is imported** from FindMyShift or Breathe. Managers set up staff, departments, colours, allowances and rotas by hand.

**MIG-02** — Key dates:

| Date | What happens |
|---|---|
| **As soon as possible — early December 2026 at the latest** | System ready for managers to start setting up data |
| Before Christmas 2026 | Staff can request 2027 leave in the app (REQ-07) |
| **1 January 2027** | **Full launch.** Rotas and allowances start (start of the 2027 leave year). All features in place (see `11`) |
| ~24 January 2027 | First payroll report due (PAY-02) |

**MIG-03** — **No opening balances** are needed: everyone starts 2027 on their full allowance.

**MIG-04** — **2026 carry-over** is typed in by managers in January 2027 as a manual adjustment, logged with the reason "carried over from FindMyShift 2026".

**MIG-05** — A **past schedule section, visible to managers only**, for entering **2026 sickness by hand** (from about July 2026) with **start and end dates only** (no hours). These entries count towards instances of absence and triggers from day one; they do not affect leave balances or payroll.
*Why:* the rolling 6-month triggers must be right from launch.

**MIG-06** — **No parallel running.** FindMyShift is being retired; it is effectively not in use because of its incorrect leave calculations.

**MIG-07** — **No staff training.** Staff must be able to pick the system up themselves.

## Risks

- **Timeline.** Every feature is required for 1 January 2027, with about nine weeks from the date of the interview. The developer should raise early anything likely to slip; the year-end carry-over flag is the obvious candidate, since it isn't needed until December 2027.
- **Fallback** if the system isn't ready for set-up in early December — **[UNCONFIRMED]**, see `12`.

## Not needed, on purpose

- Importing staff, rotas, booked leave, balances or history.
- Parallel running.
- Training sessions or guides.
