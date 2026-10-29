# AMG Shift Central — developer pack

Requirements for **AMG Shift Central**, the practice's new staff rota and leave management system. Written from an interview with the practice manager (29 October 2026) and approved by them.

The specification says **what** the practice needs and **why**. Design and technology choices are yours, apart from the stated preferences in the documents.

## What's in this pack

| Folder | Contents |
|---|---|
| this folder | 13 Markdown documents, `00-overview.md` to `12-decisions-and-open-questions.md` |
| `../brand/` | Logo files: SVG (text converted to outlines, no font needed) and PNG (2× resolution) |

## Read these first

1. **`00-overview.md`** — the practice, goal, scope, key dates and glossary.
2. **`05-leave-policy.md`** and **`06-leave-worked-examples.md`** — the leave rules and 31 worked examples (LV-, SICK-, KIT-). **Getting hours-based leave right is the reason this project exists.** Turn every worked example into an automated test. Each must give exactly the expected answer.
3. **`03-findmyshift-feature-review.md`** — the visuals and functionality must be **very close to FindMyShift**, screen by screen (FMS-00). Use the AMG Shift Central name and logo, not FindMyShift's branding.
4. **`11-priorities.md`** — build order, must/could/won't, and the success and failure measures.

## Key dates

| When | What |
|---|---|
| As soon as possible, **early December 2026 at the latest** | Ready for managers to start setting up staff, allowances and the 2027 rota |
| Before Christmas 2026 | Staff can request 2027 leave |
| **1 January 2027** | Full launch, all features in place |

The timeline is tight. Please raise early anything likely to slip (see the risks in `10-migration-and-go-live.md`).

## Open questions

These are listed in `12-decisions-and-open-questions.md`. The ones for you are:

- **Q-04** Fallback if the system isn't ready for set-up in early December (agree it with the practice manager)
- **Q-08** How to display half-minutes (e.g. 2 h 37½ min)
- **Q-09** Confirm Practice HR's built-in leave design stays switched off
- **Q-10** The GP rota app must read GP time off from AMG Shift Central instead of FindMyShift

The practice is checking Q-01 to Q-03 (legal points on rounding, carry-over and sickness) with its HR/legal adviser.

## Logo files

| File | Use |
|---|---|
| `amg-shift-central-logo-dark.svg / .png` | **Main logo.** Top of the navy side panel, login screen |
| `amg-shift-central-logo-light.svg / .png` | On white backgrounds, e.g. printed reports and PDF one-pagers |
| `amg-shift-central-logo-light-transparent.svg / .png` | Light version with no background |
| `amg-shift-central-logo-stacked-dark / -light` | Square spaces, e.g. splash screen |
| `amg-shift-central-icon.svg` and `-icon-512/192/180/32.png` | Phone app icon (512, 192), Apple touch icon (180), browser favicon (32) |

- **Colours:** navy `#143D5C`, amber `#F2A33A`, white `#FFFFFF`, pale grey-blue `#DDE7EE` (secondary text on navy).
- **Typeface:** Manrope (free, SIL Open Font License, on Google Fonts). Fallbacks: Segoe UI, Arial.
- The practice manager can also share the logo design canvas, which has adjustable colours.

## Not included, on purpose

The practice's FindMyShift screenshots document is **not** in this pack because it contains staff personal data. The practice manager will send a redacted copy separately. `03-findmyshift-feature-review.md` describes every screen in the meantime.
