# The rota

**Where:** sidebar › Rota (`/rota/`). Who's in today and Time off… are under it, Hours is under
Reports. Everyone sees the rota; the editing, Templates, Notify staff, Who's
in today and booking leave are for managers.

## The mental model

**The grid is a spreadsheet of days and people, and you type into it.** Click a
cell, type `8-4`, press Enter, and the shift is there. Nothing is saved by a
Save button: each change is written the moment you leave the cell, and the grid
shows what the server stored, so what you see is what is on record.

**You can edit the people you manage, and nobody else.** A team manager edits
their team's rows, an all-teams manager everyone's, and **nobody edits their own
row**: another manager enters a manager's shifts, as another manager approves
their leave. A row you cannot edit is drawn the same and simply does not respond
to clicks.

**Every change is remembered, and staff are told when you choose.** Each change
writes a line in the [Activity log](access.md#the-two-logs) and adds the day to
that person's *unnotified* changes. Nothing is emailed until you press
[Notify staff](#notify-staff).

## The grid

The window is one or more weeks, Monday to Sunday. The top bar has ‹ and › (one
window back or forward), **Today**, **Show [1 to 20] weeks from [date]** (either
control reloads the page; a date in the middle of a week shows from that week's
Monday), **Options**, **Filters**, **Download**, and, for managers, **Templates**
and **Notify staff**. Today's column is shaded and weekends are muted.

The **name column** is a coloured chip with the person's name; click the chip for their
profile pop-up, as on the Staff page (a click elsewhere in the name's cell selects the row). The name column and the dates stay on
screen as you scroll (switch that off in Options). Rows are in team order, then
each person's own display order, then name. Only people who are current on at
least one day of the window have a row; a leaver's row disappears after their
finish date, and their past shifts stay for the hours report.

What a cell shows, one tile per line you typed:

- A **shift**: the times, the break if there is one, the department name or the
  comment, then `WFH`, `OT paid` or `TOIL` if set. Overtime tiles have an amber
  left edge. The tile is coloured by its department if *Use department colours*
  is on.
- A **comment**: its text in italics with a dotted top edge, so it reads as not
  costed.
- A **separator**: a hairline across the cell, to keep two groups apart.
- A **GP session**: a pale grey-blue tile, for example `AM · Surgery · AG`. See
  [GPs](#gps).
- A **leave tile**: the leave type's colour and name (or the text overtyped in Display), above
  anything else in the cell, with `½ am`, `½ pm` or the hours for a part day. Approved leave is
  filled in the type's colour, with white or dark text, whichever reads better on it. A hatched,
  outlined tile reading "requested", with a thick edge on its left in the type's colour, is leave still
  waiting for approval. See [Time off on the grid](#time-off-on-the-grid).

If two shifts in one cell overlap, the cell carries a small warning marker.

Ctrl-Z undoes your last change; it remembers up to fifty and forgets them when
the page is reloaded. There is no redo. The Activity log is the record that
survives.

## Typing a shift

Select a cell and start typing, or double-click it, or press Enter. A box opens
over the cell holding its text, one item per line. **Enter** saves, **Shift-Enter**
adds a line, **Escape** abandons the edit, and clicking away saves. Delete or
Backspace on a selected cell (or block) clears it.

A line is a shift if it holds a **time range**, and a comment if it does not.
Anything typed is accepted; the worst that happens is a comment, which you will
see at once because it is in italics.

**The time range.** Each side is an hour (`8`), an hour and minutes (`8:30`,
`8.30` or `0830`), optionally followed by `am` or `pm` in either case. The two
sides are joined by `-`, `–`, `—`, `to` or `until`. So `8-4`, `08:00 to 16:15`,
`8.30am - 5pm` and `0830-1700` all work.

- `pm` after an hour under 12 adds twelve hours, and `12am` is midnight.
- If neither side has `am` or `pm` and the finish is not after the start, the
  finish is read as the afternoon: `8-4` is 08:00 to 16:00, and `12:30-1` is
  12:30 to 13:00. It is read this way only when the start is before 13:00, so
  `13:00-2` is a comment, not a shift.
- With `pm` on the finish only, the start is read as the afternoon too if that
  still leaves it before the finish: `1-5pm` is 13:00 to 17:00, while `8-4pm` is
  08:00 to 16:00.
- Minutes over 59 or hours over 23 make the line a comment. If the finish is still
  not after the start, so does that.

**What else can be on the line**, in any order after the times:

| Type | What it does |
|---|---|
| `1 hour break`, `30 min break`, `45 minutes break`, `break 30` | An unpaid break. The word *break* is needed. Lengths are 15, 30, 45 and 60 minutes (or `1 hour`); any other length stays in the comment. `30m` on its own is also read as a 30-minute break. |
| `WFH` | Working from home. Who's in today lists them apart. |
| `TOIL` | Marks the shift as time off in lieu. See [Overtime](#overtime). |
| `OT`, `OT paid`, `overtime paid`, `paid overtime` | Marks the shift as paid overtime. |
| A department's name | Sets the department: the longest name that matches as whole words wins, in any capitals, and archived departments are not matched. |
| Anything else | The comment on the shift, up to 200 characters. |

So `8-4 1 hour break Reception PMC` is a shift with a break and a department, and
`8-4 phones only` is a shift with the comment *phones only*. A separator is a line
of three or more hyphens, `---`.

**Text that is not a shift** is kept as a comment, exactly as typed. It is not an
error, and it does not count in anyone's hours. Beware one consequence: a comment
that happens to contain a department's name or `wfh` is read as that the next time
the cell is edited. For an exact result use the shift dialog (**Add › Shift…** on
the right-click menu), which has a field for everything.

A typed shift keeps its colours and bold or italic if you retype a cell, as long as
the line is still the same kind of line in the same position.

## The right-click menu

Right-click a cell (or press Shift-F10 or the Menu key on a selected one) for a
dark menu. It acts on the **whole selection**, not only the cell you clicked.

- **Add ›** Shift… opens the shift dialog; Comment starts a new comment line in the
  cell's box; Separator adds a separator; **Department ›** and **Break ›** set
  those on the selected shifts (*More departments…* opens the
  [Departments](departments.md) page); **Common ›** lists the
  ten shifts most often used in your teams over the last twelve weeks, and
  **Recent ›** your own last ten, and picking one adds that shift; **Overtime ›**
  None, Paid or TOIL; **WFH** switches working from home on or off.
- **Appearance ›** background and text colour from the swatches, bold, underline,
  italic, strikethrough, wrap, font size, and Reset appearance. This changes how
  the tile looks and nothing else, and it is not reported to staff.
- **Find & Replace…** opens a dialog: text to find, text to put in its place, match
  case or not, over the selected cells or the whole window. Each changed line is
  read again as if typed.
- **Time off…** (first on the list) opens the Add time off dialog with the person and the day
  already filled in, for a cell with no leave. On a cell that has leave it is replaced by **View time
  off** and, for the people you manage, **Cancel time off**; on approved leave there is also
  **Shift behind the leave…** (a whole or half day) or **Edit the day's shift…** (leave by the hour).
  See [Time off on the grid](#time-off-on-the-grid).
- **Cut**, **Copy**, **Paste**, **Delete**. See [Copying weeks](#copying-weeks).
- **Select ›** Row, Column, Week or All, from the cell you clicked.
- **Save selection as template…** See [Templates](#templates).
- **Print** prints the page.
- **Message [name]** is greyed out and marked *coming later*.

## Selecting

Click a cell to select it; Shift-click extends to a block; Ctrl-click adds a cell;
dragging across cells selects a block. Clicking a date selects that column, and
clicking in a name's cell, beside the chip, selects that person's row (the chip itself
opens the profile). The arrow keys move, Tab moves right, and Home and End go to the window's
first and last day. A cell on a row you cannot edit is never selected.

**Moving** a block: drag the selection to where it should go. **Ctrl-drag** copies
it instead. A drop on a row you cannot edit is refused at once.

## Copying weeks

Select a block (a Monday-to-Friday run for one person, or a whole week for the
team), press **Ctrl-C** (or **Ctrl-X** to cut), click the top-left cell of where it
should go, and press **Ctrl-V**. The block lands with its top-left corner there,
the same days apart and the same rows below. A copied week pasted onto next
Monday fills next week.

- Rows that fall below the last row, or on a person you cannot edit, are skipped,
  and the grid says how many. So is any day with **approved leave** on it, whether it is
  where you are copying from or to: the shifts hidden under the leave are never copied, moved or deleted.
  The grid counts the two apart: "1 row and 2 leave days couldn't be pasted onto." (rows you
  cannot edit, and approved-leave days). Waiting leave does not block a paste.
- A day the copy did not see, such as a weekday hidden in Options, is left alone
  on the target, and so is a cell inside the block that you did not select
  (Ctrl-click a few cells, and only those are pasted). A selected cell that was
  empty does clear the cell it lands on.
- A paste goes by calendar day from the cell you paste at: a Monday-to-Friday
  block pasted onto a Thursday fills Thursday, Friday, the weekend and Monday,
  whether or not the weekend is shown, and can run past the last day on screen.
- **Paste behaviour** in Options decides what happens to a cell that already has
  something: **Replace what is there** (the default), or **Add to what is there**.
- Pasting is for managers only.

**Into and out of Excel.** Copying also puts the block on the computer's clipboard
as tab-separated text, a cell per column and several items in one cell joined by
` / `, so it can be pasted into a spreadsheet. Pasting text from elsewhere does
the reverse: each cell is read exactly as if it had been typed into the grid,
and tabbed text fills cells to the right and lines downwards. The copy survives a
reload of the page, but not closing the browser, so nothing copied is left behind
on a shared computer.

## Templates

A template is a saved block, usually a week, to lay down again. Select the cells,
right-click, **Save selection as template…**, and name it. **Templates** in the top
bar lists them with **Apply** (to the cell selected on the grid; it behaves like a
paste, with your paste behaviour), **Rename** and **Delete**. Templates are shared
by all managers. Applying one onto a person you cannot edit skips that row, and onto a day of
approved leave skips that day, and it tells you how many of each were skipped ("1 row and 1 leave
day couldn't be pasted onto.").

## Overtime

Mark a shift **Paid** or **TOIL** from the right-click menu (Add › Overtime), by
typing `OT` or `TOIL` after the times, or in the shift dialog.

- **Paid** is overtime the practice will pay for.
- **TOIL** is overtime to be taken back as time off in lieu.

Either way the tile gets an amber edge and a fourth line, and **its hours are no
longer counted as scheduled hours**: the [hours report](#the-hours-report) shows
them in their own Overtime column. **TOIL** shifts, up to today, are the TOIL a person has
earned in [Leave](leave.md#the-statement-and-how-to-read-it), and a later release reads
the marks for payroll, so mark them as you go.

## Notify staff

Changes are not emailed as you make them. **Notify staff (N)** in the top bar,
shown in amber when N is more than none, is the number of people with changes
nobody has told them about yet. It opens a list of those people with a tick box
each (ticked), the days that changed, and a note where nothing can be sent:

- **no email**: the person has no email on record. They are greyed and cannot be
  ticked.
- **changes cancel out**: the days were changed and then changed back. They are
  greyed but stay ticked, so that pressing Send clears them; no email is sent.

**Send** emails each ticked person once, in plain text, from the address in
`DEFAULT_FROM_EMAIL`. The subject is *Your rota has changed*, and the body reads:

    Your rota has changed. Here is what is different:

    Tue 3 Mar 2027: 08:00–16:15 1 hour break Reception PMC (was 09:00–17:00 Reception PMC)
    Sat 7 Mar 2027: no shift (was 08:00–13:00 Reception AG)

    See your rota: https://<this site>/rota/?from=2027-03-01

Only days that really differ are listed, with what they are now and what they were
when the person was last told; the link opens the first changed week. The dialog then
says, by name, who was sent to and who failed. **A failed send keeps that person's
changes for next time**; a successful one clears them and writes an entry in the
Activity log.

If the site has no mail relay configured (the `EMAIL_*` settings in
[Setting up](setup.md)) nothing can be sent: the dialog lists everyone as failed and
keeps all their changes, so nothing is lost by trying. The same happens if the mail
relay cannot be reached part-way through: the people not yet sent to are not tried,
are listed as failed, and keep their changes. A change you make to someone's day
while their email is being sent is kept for the next Notify.

**The Health line.** The Health card on the Staff page counts *Unnotified rota
changes over a week old* and links to this dialog. A week-old change that staff were
never told about is the thing to look for there: it means a change was made and the
person may still be working the old rota.

## Time off on the grid

Leave is booked on the [Time off pages](leave.md); the grid shows it. What changes in the grid:

- **Approved leave owns the cell.** The leave tile is drawn above whatever else is there and the
  cell cannot be typed into, pasted over, dragged, cleared or changed by Find & Replace: it is
  skipped like a row you cannot edit. It can still be focused and right-clicked, and right-clicking it
  empties the selection, as clicking it does, so Delete or Cut afterwards acts on nothing. A shift
  on that day is not deleted: it is **covered**, hidden from the grid, the hours report, Who's in today,
  the phone list and Notify staff, and comes back when the leave is cancelled.
- **Leave by the hour** shortens the shift it falls inside instead of covering it: the shift stays on
  the grid with its new times, under the tile.
- **Waiting leave** is hatched with "requested" and covers nothing. The cell stays editable.
- **The right-click menu** has **Time off…** on any cell you may edit (the person and day filled
  in), and **View time off** and **Cancel time off** (for people you manage) on a leave tile. On a cell
  with approved leave, or on a row you cannot edit, that is all it shows. **Rota › Time off…**
  in the sidebar opens the same dialog without a person or day chosen. On approved leave of a row
  you may edit the menu also offers **Shift behind the leave…**, or for leave by the hour **Edit the
  day's shift…** (below). Waiting leave never gets either.
- **Booking leave moves the grid and leaves a trail.** Adding or cancelling approved leave
  changes what the person sees for the day, so it appears in **Notify staff** as a change ("Holiday" in
  place of the shifts), and in the Activity log.
- **The shift behind the leave.** Right-click a day of approved whole-day or half-day leave and choose
  **Shift behind the leave…**: the shift dialog opens with a note that the person is off, prefilled
  from the shift the leave covers if there is one. What you save is what they would have worked; it stays
  hidden on the grid. If the booking is a whole day costed on an average day (the week had no rota), the
  day is re-costed from this shift and the managers are emailed ("Leave cost to check"), even if the
  figure is the same. Writing the person's other days does not change it. A half-day, timed or
  typed-by-hand cost is left alone, so a half day's placeholder is settled by typing the figure in the
  **Allowance used** box in the booking's Edit dialog, which is also the other way to put any cost right.
- **The shift on a day of leave by the hour.** The leave has only shortened the shift, which is still on
  the grid, so the menu says **Edit the day's shift…** and the dialog edits that shift, opening on the
  times the person would have worked, leave included (09:00 to 17:00 where the grid shows 09:00 to 14:00),
  with a note giving the leave's times. It finds the shift the leave shortened, or the one it hides when
  the leave is the whole of it, or the day's only shift; with none it says **Add shift**. The shift you
  save must include the leave ("The shift must include the leave, 14:00–15:30"). Saving cuts it around
  the leave again and remembers the times you typed, so cancelling the leave gives them back. On a day
  with more than one shift, the others can only be changed once the leave is cancelled.

## Options and Filters

**Options** is saved for you alone and applies everywhere you open the rota:

| Option | What it does |
|---|---|
| Show staff colours | Name chips in each person's colour, or plain text. |
| Show job titles | The job title under the name. |
| Use department colours for shifts | Tiles take their department's colour. Off, tiles are white. |
| Float dates and names when scrolling | Keeps the date row and name column in view. |
| My shifts on top | Your own row first. |
| Only my shifts | Only your own row. |
| Hide staff with no shifts | Drops people with nothing in the window. |
| Font size, Spacing | Small, normal or large type; tight, normal or loose rows. |
| Days to display | Hides the unticked weekdays' columns. The shifts are still there, and a paste whose block spans a hidden day still writes to it (a paste goes by calendar day). |
| Paste behaviour | Replace or add. See [Copying weeks](#copying-weeks). |

**Sort staff by drag and drop** is a link at the bottom of Options, for managers.
The name column grows handles; drag a name to where it should go, and each drop is
saved. **Done sorting** in the top bar leaves the mode. The order is the person's
display order, so it changes for everyone and on the Staff page too. Only the
people you manage are renumbered (not yourself, nor other teams' people, whose
order stays as it was).

**Filters** narrows the window to people whose **name contains** some text, to
chosen **teams**, or to chosen **departments** (people with at least one shift in
that department in the window). It lives in the page's address, so a filtered rota
can be bookmarked. **Clear** removes it.

## Download and Print

**Download** gives the current window as a CSV file, `rota-<first date>.csv`: a row
per person, a column per day, several items in a cell joined by ` / `, any GP
session first. It follows your filters and shows what you can see. A day of leave reads as the type's name, for
example `Holiday`, `Holiday (morning)` or `Training 14:00–15:30`, and `(requested)` after it for leave
still waiting.

**Print** is on the right-click menu and prints the page as it is; use the browser's
print settings to choose landscape, and Filters or Options to narrow what is shown
first.

## The hours report

Sidebar › Reports › Hours (`/reports/hours/`). Choose **From** and **To** (up to a
year; this week to begin with) and press Refresh. Managers see the people they
manage and themselves; everyone else sees only themselves.

Each person has a block headed *Nina Patel — 5 shifts / 37 h 30 min* (and
*+ 4 h overtime* if any) with a row per shift: day, date, start, finish, break, the
hours worked after the break, overtime in its own column, and the department or
comment. When the range spans more than one week there is a **subtotal per week**,
and always a **total** per person. A comment is not a row. A GP session is a row
with its part and label, no times, and **4 h 10 min**. **Download** is the same
rows as CSV with the person's name added.

## Who's in today

Sidebar › Rota › Who's in today (managers). A board for one day, with ‹ and › to
move and Today to come back. People are grouped by **site** (AG, PMC, or Either),
then by team, each with their times. A shift is at AG or PMC when its department's
name contains *AG* or *PMC* as a word (*Reception AG*, *Cleaning PMC*), and Either
otherwise. People working from home are listed in their own section. **Off** lists
everyone with **approved leave** today, with the leave type's name (Holiday, Sick leave, Bank
holiday…) and nothing more, however much of the day it covers. Someone with no shift and no leave
is simply not listed. A waiting request does not count.

## On a phone

Under 768 pixels wide the rota is a read-only list instead of the grid: a card for
each day of the week with your own shift first (or *No shift*), and, behind
**Whole team**, everyone else's with their names. ‹, › and Today are in the top bar.
A day of leave is a coloured line with its label and "morning", "afternoon" or the hours, and
"requested" for leave still waiting. There is no editing. To edit on a phone, turn it sideways: most phones pass 768
pixels that way and the grid appears.

## GPs

GPs are rows in the grid like anyone else's, but **their sessions come from the GP
rota app and cannot be edited here**. They are read from it every fifteen minutes,
for the eight weeks before today and the year after, and drawn as pale tiles
before anything you have typed in the same cell. Sessions are never selected,
copied or deleted by anything you do in the grid.

A GP's cell can still take shifts and comments typed by a manager, for example an
extra shift, and the hours report adds both.

**A GP's leave is booked in Shift Central like anyone's**, and the leave tile sits above their
session, which stays: the session belongs to the GP rota app, which reads the leave back
(see [the GP leave feed](sync.md#the-gp-rota-app-reads-gp-leave-from-here)) and flags a session that clashes with it. A GP's day of leave
costs their sessions that day. On **Who's in today** a GP on a whole-day booking is listed under "off" only; on a morning or afternoon booking the other session still shows under its site.
The grid still shows the sessions.

**A GP's sessions are matched to the GP by work email.** If the address the GP rota
app holds differs from the one in Practice HR, even by a typo, the sessions do not
show, and the Staff page's [Health card](sync.md#gp-sessions-from-the-rota-app)
lists the address that did not match. The fix is to make the two agree, in
whichever of the two systems is wrong. If **no** GP has sessions, the card says
whether the feed is configured, failed or has never run.
