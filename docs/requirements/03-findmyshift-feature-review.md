# 03 — FindMyShift feature review

Based on the practice manager's walkthrough and screenshots. "Keep" means the new system must have the same capability, look and way of working (FMS-00), using the **AMG Shift Central** name and logo rather than FindMyShift's branding.

**FMS-00 (overall)** — The new system's **visuals and functionality must be very close to FindMyShift**: the same screen layouts, navigation, menus, pop-up windows, colour-coded tiles and ways of working described screen by screen below. A FindMyShift user should feel at home immediately. The **AMG Shift Central** name and logo are used; FindMyShift's name, logo and branding are not.
*Why:* the practice manager likes FindMyShift's interface and staff already know it; not matching it is a stated failure measure (`11`), and staff will not be trained (MIG-07).

**FMS-00a** — The developer should check each screen against the descriptions below (and against the redacted screenshots, once available) before release.

## Screen by screen — how it must look and behave

**Overall layout**
- A **dark navy side panel** on the left, which can be shrunk or unpinned, with icon + label items: Rota, Staff, Departments, Time off, Messages, Notice board, Outbox (with a count badge), Uploads, Reports, Activity logs, Settings, and Log out at the bottom.
- Hovering or clicking an item opens a **flyout submenu** in the same navy:
  - Time off: Add time off, Planner, Download, Report, Restrictions (blackout periods), Settings
  - Messages: Send a message, Sent messages
  - Reports: Dashboard, Budget, Hours, Time off, Shifts, Staff by hour, Log in logs, Sent messages
  - Settings: General, Display, Requests, Privacy, Time off, Notifications, Colours & fonts, Budgets, Pay rates, Break rules
- A light **top bar** on each page: the page title, then actions as small text links with icons, e.g. on the rota: back/forward arrows, jump to today, "Show [1–20 weeks] from [date]", Options, Filters, Download, Templates. The main "add" action on a page (e.g. "Add time off +", "Add staff +") is highlighted in orange.

**Rota grid**
- White page; a header row of days with dates (e.g. "Mon. Oct. 26"); **today's column lightly shaded**; dates and names **stay visible when scrolling**.
- **All grid colours are set by managers while building the rota** — none are fixed by the system. The colours named here are only examples from the practice's current rota.
- **Name column** on the left, each name cell filled with the person's chosen colour (e.g. red, blue) with white bold text.
- **Shift tiles**: centred small text — times on the first line ("08:00–16:15"), break on the second ("1 hour break"), department or comment on the third ("PMC", "WFH"). Tile background = the department's colour, or a colour the manager sets on that tile (e.g. pale yellow, orange, peach for WFH, bright green). Days off show as full red tiles reading "OFF". Thin grey gridlines.
- **Right-click menu**: dark navy panel with white text and icons, with submenus opening to the right:
  - Add ▸ Shift, Comment, Separator, Department ▸ (list with colour swatches, "More departments…"), Break ▸ (15 / 30 / 45 minutes, 1 hour), Common ▸, Recent ▸, Time off ▸ (leave types), **Overtime ▸ (paid / TOIL)** (new)
  - Appearance ▸ Background, Text colour, Bold, Underline, Italic, Strikethrough, Wrap text, Font size ▸, Reset appearance
  - Find & Replace; Cut; Copy; Delete; Select ▸; Print; Send a message to *[name]*
- Tiles can be free-typed, dragged, copied and pasted singly or in blocks.

**Options panel** (from the top bar): a drop-down list of labelled tick boxes and link-style settings (show staff colours, show job titles, use department colours for shifts, float dates/names when scrolling, sort staff, font, font size, spacing, days to display, paste behaviour, etc.).

**Staff profile pop-up**: a window over the grid with a dark header bar ("[Name]'s profile" / "Your profile") and small icons (message, notifications, history, close); an avatar circle; tabs **General / Display / Pay & time off / Notes**; outlined fields with floating labels and small icons; a full-width dark button "Update profile"; links underneath: Uploads, Permissions, Delete this staff member. Pay & time off tab includes **Holiday allowance (hours)** and the new **Bank holiday allowance (hours)**, plus weekly hours and days per week.

**Staff and Departments pages**: simple white tables (Name, Job title, Department, Email… / Name, Date started) with Options, Filters, Download and the orange "Add" link in the top bar.

**Time off list**: table with Staff, First day off, Last day off, Days, Type, Display (coloured label), Repeat, Pay (paid/unpaid), Allowance used, and edit / view / delete icons.

**Add time off pop-up**: dark header "Time off", tabs **General / Advanced**. General: Staff member, Type of time off, Display (coloured bar, with the **overtypeable description**), First day off, Last day off, Days to include (plus half day / start and end times). Advanced: Repeat, Allowance used (shows the calculated cost, overridable), Paid/unpaid, Manager notes. Full-width dark button (e.g. "Add holiday").

**Time off planner**: a year calendar — months as rows, days across lined up by weekday, weekends shaded; leave shown as coloured cells with the person's initials under the date; filters by leave type and year.

**Time off report**: table with First name, Last name, **Instances of absence / trigger** (replacing Bradford Factor), Yearly allowance (hours), Allowance, Instances, Days, Deducted, Remaining, Paid hours; a date-range selector with arrows and a Refresh button.

**Time off settings**: a pop-up list — setting label on the left, tick box or value on the right.

**Hours report**: one block per person headed "[Name] — N shifts / X hours", with a table of Day, Date, Start, Finish, Break, Hours and a total.

**Phone**: the same functions in a phone-friendly layout, with push notifications.

> **Note:** the screenshots document supplied contains real staff names and one person's personal contact details and date of birth. It should not be passed to the developer unredacted.

## Rota grid

| # | Feature | Decision | Priority | Comments |
|---|---|---|---|---|
| 1 | People down the side, days across, view 1–20 weeks | Keep | Must | |
| 2 | Filter by name, department, role | Keep | Must | |
| 3 | Free-type text in any tile | Keep | Must | |
| 4 | Drag tiles to move shifts | Keep | Must | |
| 5 | Right-click: add shift, comment, separator, department, break, time off | Keep | Must | Plus **overtime – paid / overtime – TOIL** (ROTA-06) |
| 6 | "Common" and "recent" shifts | Keep | Must | |
| 7 | Appearance: background, text colour, bold, underline, italic, strikethrough, font size, wrap, reset | Keep | Must | |
| 8 | Find and replace | Keep | Must | |
| 9 | Cut, copy, paste, delete, select — including whole weeks/blocks | Keep | Must | Main way of laying out the year (ROTA-07) |
| 10 | Colours by staff group and by department | Keep | Must | |
| 11 | Print | Keep | Must | |
| 12 | Message a person from the grid | Keep | Must | |
| 13 | Download the rota | Keep | Must | |
| 14 | Options: float dates/names when scrolling, sort staff by drag and drop, my shifts on top, only my shifts, hide staff with no shifts, show job titles/departments, font, spacing, days to display, paste behaviour | Keep | Must | |

## Staff profiles and lists

| # | Feature | Decision | Priority | Comments |
|---|---|---|---|---|
| 15 | Click a name to open the profile (own; managers: anyone) | Keep | Must | |
| 16 | General: name, email, mobile, alternate phone, gender, date of birth, password | Keep | Must | Typed in by managers; not pulled from Practice HR. Password/sign-in is via Practice HR |
| 17 | Display: job title, department, start and finish dates, name colour | Keep | Must | |
| 18 | Display on rota / show to other staff / can see other staff | Keep | Must | |
| 19 | Pay: payroll ID, tax rate, hourly rate, day rate, salary | Keep for future | Could | Not needed for launch |
| 20 | Break rules | Keep | Must | |
| 21 | Holiday allowance (hours) | Keep | Must | Full-year hours typed by manager |
| 22 | **Bank holiday allowance (hours)** | **Add** | Must | Separate box; combined with holiday on the leave report |
| 23 | Sick allowance | Drop | Won't | |
| 24 | Notes tab | Change | Must | **Visible to managers only** |
| 25 | Uploads (per person) | Keep | Must | |
| 26 | Permissions (manager access) | Keep | Must | Per team (PEOPLE-04) |
| 27 | Staff list: add/remove, filter, download | Keep | Must | |
| 28 | Guests | Drop | Won't | |
| 29 | Departments page: add, set colours | Keep | Must | |
| — | **Weekly hours and days worked per week** | **Add** | Must | Needed for the leave placeholder (`04`) |

## Time off

| # | Feature | Decision | Priority | Comments |
|---|---|---|---|---|
| 30 | Add time off for anyone: type, colour, dates, days to include | Keep | Must | Plus **overtyped description** for that occasion (e.g. "Training – SDL") |
| 31 | Repeating time off | Keep | Must | |
| 32 | Override "allowance used" | Keep | Must | Every override is logged (LEAVE-30) |
| 33 | Pay calculation on a booking | Keep | Must | Becomes **paid / unpaid** marker (LEAVE-27) |
| 34 | Manager notes on a booking | Keep | Must | |
| 35 | Editable leave types | Keep | Must | See `05` for the list |
| 36 | Year planner, filtered by type and year | Keep | Must | |
| 37 | Leave report: allowance, instances, days, deducted, remaining | Keep | Must | Calculations must follow `05` |
| 38 | Bradford Factor | **Replace** | Must | With **instances of absence** and triggers (LEAVE-40 to 44) |
| 39 | Restrictions | Change | Must | **Blackout periods only** (REQ-08). No maximum-off rules |
| 40 | Download time off lists | Keep | Must | |

## Settings, messaging and reports

| # | Feature | Decision | Priority | Comments |
|---|---|---|---|---|
| 41 | Leave year start (1 January) | Keep | Must | Overridable per person |
| 42 | Staff see each other's approved time off | Keep (on) | Must | Leave **type** only (ACC-05) |
| 43 | Staff see each other's pending time off | Keep (on) | Must | |
| 44 | Staff can request time off | Keep (on) | Must | |
| 45 | Staff can cancel approved time off | Change | Must | Cancellation **needs manager approval** (REQ-10) |
| 46 | Managers approve each other's requests | Keep (on) | Must | |
| 47 | Managers approve their own time off | Keep (off) | Must | Except practice manager's own leave: recorded without approval |
| 48 | Automatic approval after X minutes | Drop | Won't | |
| 49 | Administrators bypass restrictions | Keep | Must | Managers can book in blackout periods |
| 50 | Minimum/maximum notice periods | Drop | Won't | Replaced by blackout periods only |
| 51 | Shifts can overlap time off | **Change** | Must | Adding time off **removes** the shift (ROTA-10) |
| 52 | Internal messages: send, sent | Keep | Must | |
| 53 | Notice board | Keep | Must | |
| 54 | Hours report (rota hours minus breaks) | Keep | Must | Replaces manual hours calculation |
| 55 | Log-in logs (date and time stamped) | Keep | Must | |
| 56 | Dashboard, shifts, staff-by-hour reports | Keep | Must | Budget report: **Could** (future, with item 19) |

## Other features

| # | Feature | Decision | Priority | Comments |
|---|---|---|---|---|
| 57 | Staff use it on their own phone (installable app) | Keep | Must | With push notifications |
| 58 | Open shifts, claimed by staff | Keep | Must | Manager approves claims (ROTA-11) |
| 59 | Shift swap requests | Drop | Won't | Staff agree; manager edits rota (ROTA-13) |
| 60 | Availability | Drop | Won't | |
| 61 | Clock in/out | Drop | Won't | |
| 62 | Templates | Keep | Must | |
| 63 | Uploads area (shared documents) | Keep | Must | |
| 64 | Outbox (sent emails/notifications) | Keep | Must | |
| 65 | Activity logs (who changed what) | Keep | Must | |

## What FindMyShift gets wrong

- **Pro-rata leave for starters and leavers.** FindMyShift pro-rates by calendar days (e.g. 285 h × 136/365 = 106.19 h). The practice's rule is by weeks — see LEAVE-10 and LV-20 (109 h 30 min).
- **Mixed units.** The leave report showed "2 days deducted, −2 days remaining" for someone with an hours allowance.

## What is missing from FindMyShift

Nothing beyond **correct leave calculations** and having **everything, GPs included, in one place**.

## Not needed, on purpose

Items 23, 28, 48, 50, 59, 60, 61; Bradford Factor; maximum-off restrictions.
