# Engagement: open shifts, messages, notices, uploads, the Outbox, reports and the phone app

**Where:** Rota › Open shifts (`/rota/open/`); Messages (`/messages/`), with Send a message and
Sent messages for managers; Notice board (`/notices/`); Uploads (`/uploads/`), and Uploads on a
person's profile; Outbox (`/outbox/`, managers); Reports › Dashboard, Shifts and Staff by hour
(managers); Notifications (`/notifications/`, everyone). Open shifts, Messages, the Notice
board, Uploads and Notifications are for everyone to read or use; posting, sending, deciding,
adding documents and the reports are for managers.

## The mental model

**Staff are offered things and told things; managers decide.** A manager posts an open shift
and a member of staff asks for it. A manager sends a message or posts a notice and staff read
it. Nobody replies in the app: messages are one-way.

**Email always arrives, and a phone notification is a copy of it.** Every message the app
emails a person can also be a notification on their phone, if they have turned that on for that
phone. The email carries the full text; the notification carries only the subject. Turning
notifications off never stops the email.

**Everything sent is written down in the Outbox**, whether or not the mail relay took it, so a
manager can see what went to whom, and when.

**Documents are kept outside the website's own files** and can only be downloaded through the app,
by someone allowed to see them. A person's documents are seen by their managers and not by
the person.

**Changes are in the Activity log** (sidebar › Activity logs): posting, filling and withdrawing an open
shift, sending a message, posting, editing and removing a notice, and adding, removing and
(for a person's documents) downloading a document, each with who and when. See
[the two logs](access.md#the-two-logs).

## Open shifts

**Where:** Rota › Open shifts. Managers see **Post an open shift +** at the top.

An open shift is a gap a manager wants filled: a day, a start and finish, an optional break,
department and comment. Staff the shift is offered to can claim it; a manager approves one claim,
and the shift appears on that person's rota like any shift the manager had typed.

### Posting

A manager of a team posts for that team (an all-teams manager can post for any team). In the
dialog:

- **Owning team.** The team whose managers will decide the claims. They, and the all-teams
  managers, are the people told of a claim and the only ones who can approve it.
- **Day, Start, Finish and Break.** The day cannot be in the past, and the finish must be later than
  the start. The break is none, 15, 30, 45 or 60 minutes.
- **Department** and **Comment** (200 characters) are optional. The comment is shown on the
  open shift and carried onto the rota, and is never put in an email or notification.
- **Offer it to everyone**, or **Or to these teams**. One of the two is needed. This is who
  may claim, and it is separate from the owning team: a Reception manager can offer a shift to
  Reception and Admin. Only people who are currently employed and can sign in are offered it.

**Overtime is not set when posting.** The person who claims chooses how they will work it (below), and the approving
manager can change that.

On posting, everyone it is offered to (except the person who posted it) is emailed, and gets a
notification if they have them on.

### Claiming

A member of staff opens Rota › Open shifts, which lists the shifts offered to their team or to
everyone. **Claim** opens a short dialog:

- **How will you work it?** Normal hours, Overtime – paid or Overtime – TOIL. This is the same
  overtime marking the rota uses, so it carries onto the rota and the Hours and Shifts reports.
- **Note for the manager** (200 characters), optional. It is shown to the managers only on the open shift
  itself, never in an email.

After claiming the card says "You've claimed this" and offers **Withdraw my claim**. More than
one person can claim the same shift. Nobody is told when a claim is withdrawn. A shift whose
day has passed can no longer be claimed; it shows under *Filled and past* with the word
"expired". Past and filled shifts stay listed there for 30 days.

### Deciding

Managers of the owning team (and all-teams managers) see each waiting claim on the card, with **Decide**.
The dialog shows the claimant, their note, any warnings, the way they will work it (which the
manager can change) and two buttons, **Approve** and **Decline**. **Details** on a card shows the
claims waiting, the history of those decided, and **Withdraw this open shift**. The manager's
Dashboard lists claims waiting under *Waiting for you*.

- **Clashes only warn.** If the claimant is already working at an overlapping time that day,
  or has leave booked that day (the type is named), a yellow line says so on the card and in
  the dialog. It does not stop the approval: a manager may want exactly that.
- **Leave that would hide the shift refuses approval.** Approved leave covers the day's shifts
  on the grid, so a shift added on top of it would vanish at once. If any approved leave of the
  person covers the shift's hours, whether a whole day or part of one, Approve answers "(name) is on leave that day" and nothing
  is changed. The claim stays waiting; decline it, or sort out the leave first.
- **Nobody decides their own claim.** A manager who claims a shift cannot approve or decline it; another
  manager of the team (or an all-teams manager) does.
- **Approving** puts the shift on the claimant's rota with the post's times, break, department and comment and the
  overtime marking chosen, and closes the post as filled. Every other waiting claim is closed. Approving
  is still allowed after the day has passed, so a shift worked and claimed afterwards can be put on the rota.
  The claimant is told by the approval email, so the shift is not left waiting for the next
  [Notify staff](rota.md).
- **Declining** tells the claimant and leaves the post open for others.
- **Withdrawing a post** (Details › Withdraw this open shift) closes it, and everyone whose claim was
  waiting is told it was withdrawn. Only an open shift can be withdrawn; a filled one is
  changed on the rota.

### What staff see, who is told, and when

The page lists only the shifts offered to the person's team or to everyone. Managers also see every
post of the teams they manage. Staff never see anyone else's claim.

| When | Who is emailed (and notified) |
|---|---|
| A shift is posted | Everyone it is offered to, except the manager who posted it |
| Someone claims | The managers of the owning team and all-teams managers who can sign in, except the claimant |
| A claim is approved | The claimant |
| A claim is declined | The claimant |
| A shift is filled, or withdrawn | Everyone else whose claim was waiting |

Emails go as the action happens. A notification is sent by the push timer within about a minute. The subject of each
names the day and times; the body has the day, times, break and department and a link, and
never the comment or a note.

## Messages

**Where:** Messages › Inbox for everyone. Managers also have **Send a message…** and **Sent messages**.

**Only managers send.** Any manager can write to chosen people, to whole teams, or to everyone. Staff
read their messages and cannot send or reply; if staff should be able to answer, say so in
the message (a phone number, a person to see). This is a choice made with the practice manager; the amendments
page records it.

To send, open **Send a message…** (or **Sent messages** and **Send a message +**). A message needs a subject (150
characters) and some text (5,000), and a choice of **People**, **Teams** and **Everyone**: one at
least. A person in more than one choice is sent it once, and the sender is never sent their own message. The
dialog says how many people it went to. Everyone currently employed is included, whether or not they have
signed in; those without an email address show as failed in the Outbox.

On the rota grid, the right-click menu has **Message** followed by the person's name, which opens the same
dialog with that person already chosen.

Each person gets the message by email (the full text, with the sender's name and a link), and a notification if they
have turned them on (the subject only). It appears in their **Inbox**; a message not yet opened is in bold,
and the number of unread messages is the badge on Messages in the sidebar. Opening it marks it read.

**Sent messages** lists what a manager sent, who it went to and **Read**, the first names of those who have
opened it. An all-teams manager sees every manager's messages; other managers see their own.

## The notice board

**Where:** Notice board. Managers have **Post a notice +**.

A notice is plain text for everyone or for chosen teams: a title (120 characters) and text (5,000). Line breaks are kept; there is no
bold, formatting or pictures, and a web address is shown but is not a link. Staff read the board; a staff member sees
the notices for everyone and for their own team.

- **Pin to the top** keeps a notice above the others, which are in the order newest first.
- **Show until** is the last day the notice is shown. After it the notice disappears from the board (it stays in
  the list the manager can edit, until removed). Leave it empty to keep a notice up.
- **Also tell staff by email and notification** is off unless ticked, and is offered only when posting. Posting
  alone tells nobody. Ticked, it sends everyone the notice is for (except the poster) the title as the subject, with a link to the board;
  the text is read on the board.

A manager edits or removes the notices they posted under **Notices you can edit**; an all-teams manager can change any. Editing
never tells anyone again.

## Uploads

**Where:** Uploads, for the shared area; a person's profile › **Uploads**, for what is kept on them.

**The shared area** is the practice's noticeboard of files: the fire plan, a form, a policy. Managers add documents,
everyone signed in reads and downloads them. The manager who added a document, and any all-teams manager, can delete it.

**A person's documents** are the papers kept on a person: a certificate, a signed contract copy. They are reached from the
person's profile pop-up (the **Uploads** link, shown to those who manage that person) and are seen only by that person's
managers. **The person cannot see them**, and the page is not found for anyone else.

What can be uploaded, in both places:

- PDF, Word (`.doc`, `.docx`), Excel (`.xls`, `.xlsx`), OpenDocument (`.odt`, `.ods`), text, CSV, PNG and JPEG.
  The start of the file must match its name (a PDF that is not a PDF is refused).
- Up to **10 MB** a file, unless the server has been set to a different limit. An empty file is refused.
- A title can be given; without one the file's own name is shown.

Files are **downloads only**: the browser is told to save the file, never to open it in the page. There is **no virus scanning**: do not
open a file you do not know the source of, and only managers can add documents. There are no quotas and no versions;
to replace a file, add the new one and delete the old.

Adding and removing a document is written to the Activity log, and so is every **download** of a person's document, by whoever it was. Downloads
from the shared area are not logged. The files are kept in the server's `media` folder, which is in the
nightly backup (see the README, "Backups"). A file missing from that folder is a "not found", and the journal
records which row it was.

## The Outbox

**Where:** sidebar › Outbox (also Reports › Outbox). Managers only: an all-teams manager sees everything, and
a team manager what went to people in their teams, except what went to other managers (a notice to the practice manager can
name a colleague), though always what went to themself.

Every email the app sends, and every notification it queues, is a row: when it was queued, who to, the channel (Email or
Push), the subject, the status and the text. Filter by **Status**, **Person** and the **From** and **To**
dates, then **Refresh**. Fifty rows a page, newest first.

| Status | Meaning |
|---|---|
| **Sent** | The relay took the email, or the phone's push service took the notification. |
| **Queued** | A notification waiting for the next push timer run. An email is never left queued. |
| **Failed** | It did not go. The reason is beside it: the relay refused or could not be reached, "no email address", or for a notification "no device" (the person has none now), "push failed" (five tries) or "expired" (not sent within 24 hours). |
| **Not configured** | The server has no mail relay (`EMAIL_HOST` is not set), so nothing was tried. This is not a failure and is not counted. Set the mail up (README, "The settings") and later messages will go. Earlier ones are not resent. |

**The badge on Outbox** counts, for the last seven days, the rows that **failed**, and the notifications still **queued** after five minutes (the push timer is
not running or is failing). It is never counted for Not configured. The Dashboard's System card shows the same figure.
A message to a person with no email address fails each time until their address is in Practice HR.

**The text is removed after 12 months.** Emails contain personal details, so the daily job blanks the Outbox's copy of the text of rows older than
that and keeps who, when, the channel, the subject and the status. The messages and notices themselves, in Messages and on the notice board, are kept. The server's `OUTBOX_BODY_MONTHS` changes the
period; 0 keeps the text for ever. Ask whoever runs the server.

## Dashboard, Shifts and Staff by hour

**Where:** Reports › Dashboard, Shifts and Staff by hour. Managers only. A team manager sees the people in their
own teams; an all-teams manager sees everyone.

### Dashboard

A page of cards; it changes nothing.

- **Today**: how many people are in at each site (AG, PMC, or "no site" where the department names neither), how many
  are working from home and how many are off. It is the [Who's in today](rota.md) board, so the two always agree.
  It counts GPs, and not people hidden from the rota.
- **Waiting for you**: leave requests waiting, with the age in days of the oldest, and open shift claims waiting, each
  with a link to decide.
- **Next 14 days**: leave starting, and open shifts still unfilled.
- **Flags**: sickness triggers, people leaving in the next 30 days and people returning from absence.
- **System** (all-teams managers only): when Practice HR and the GP rota were last read, phone notifications (how many phones
  are registered and how many notifications are queued, or "not configured"), and the failed or stuck
  messages this week, with a link to the Outbox.

### Shifts

Every shift in a date range for the people you manage, grouped by person, with the date, times, break, net hours,
overtime, department and comment. **From**, **To**, **Team**, **Department** and **Person** narrow it. Net hours are finish less start less
break, as in the Hours report; overtime is shown apart; shifts covered by approved leave are left out. A range is at most
a year. **Download** gives an Excel file with the rows and one grand total; the per-person totals are on screen.

### Staff by hour

How many people are working in each hour of each day, for planning cover. Choose **From**, **To** (at most 31 days),
**Site** (AG, PMC or both) and **Team**. Each day has a row of counts for the hours worked that day, a **Peak**, and a
second row, "of which WFH".

How it counts:

- **Any part of an hour counts.** A shift from 08:00 to 16:15 counts in every hour column from 08:00 to 16:00
  inclusive; one finishing exactly on the hour does not count in that hour. A person with two shifts in an hour is counted
  once.
- **Breaks are not taken off.** Where a break falls is not recorded, so a person on a lunch break still counts.
- **GPs are not included.** Their sessions have no clock times here.
- **The site comes from the shift's department name.** A department with AG or PMC in its name belongs to that site; a shift in
  any other department is counted under **Both** only, never under AG or PMC alone.
- Shifts covered by approved leave are left out.

**Download** gives the same table as an Excel file. If the figures differ from what the practice is used to in
FindMyShift, say so: this definition is a first reading and can change.

## Putting the app on a phone

Shift Central is a web page that can be put on the phone's home screen like an app. It then opens without the browser's address bar,
and it is how notifications reach the phone. Nothing is downloaded from an app store, and the app shows no rota while the
phone is offline: only a page saying so.

**Android (Chrome).** Open the site in Chrome. In the Chrome menu (the three dots) choose **Install app** or **Add to Home
screen**. On Android, notifications work from Chrome even without installing, but the icon is easier to find.

**Finding your way on a phone.** The bar along the bottom has **Rota**, **Time off**, **Messages** and **Menu**. Menu lists
every section with the pages under it (Open shifts, My leave, Year planner, the reports and the rest) and **Log out**; a
number on Menu is what a section inside it is waiting on, such as failed Outbox mail.

**iPhone and iPad (Safari).** This needs a reasonably recent iPhone (iOS 16.4 or later). Open the site in Safari, tap **Share**,
then **Add to Home Screen**. **Open the app from the Home Screen icon**, not from Safari: notifications can only be
turned on there.

**Turning notifications on.** In the app, open **Notifications** (in the menu) and choose **Turn on notifications on this phone**, then
**Allow** when the phone asks. The page then says "Notifications are on for this device" and the phone is listed under
**Your devices**. Do this on each phone that should be told; each is separate. If the page says phone notifications are not switched on
for the practice, the server has not been set up for them yet (below).

**What a notification shows.** The title "AMG Shift Central" and the subject of the message, such as
"Open shift: Mon 9 Nov, 09:00–13:00". Sickness-trigger and return-from-absence notices show only a general line ("A sickness trigger needs your attention", "Someone is back from a long absence"), so no name shows on a lock screen. The message text is never shown.
Tapping it opens the right page: the open shift, the message, the notice board or the rota. A notification goes with each
email the app sends about open shifts, messages, notices (if "also tell staff" was ticked), Notify staff and leave.

**Turning them off.** On the Notifications page choose **Turn off notifications on this phone**. Email carries on
as before. **Remove** beside a device in *Your devices* stops the server sending to that phone; to switch it off from the phone itself, use
the Turn off button there.

**Log out turns them off on that phone**, so a phone handed to someone else shows nothing more of the last person's. Being
signed out after ten idle minutes does not: that is what lets notifications reach the phone while the app is closed. After
logging out, turn them on again from the Notifications page.

**Notifications follow whoever is signed in.** Each time the Notifications page opens it re-registers the phone for the person signed in
now, so a phone last used by someone else moves to them. An account with no staff record (the superuser) cannot receive
notifications, and the page says so. When the server refuses a phone, the page shows the reason.

**If a phone stops getting notifications:**

- The phone's permission was blocked or turned off. The Notifications page says "Notifications are blocked for this site in your
  browser's settings"; the person allows them again in the phone's settings for the app (or browser) and returns to the page.
- The device was removed, either by the person (Remove) or because the phone's push service said it no longer exists
  (app uninstalled, data cleared, or a long time offline). The person turns notifications on again.
- A new key was made on the server (below). Every phone has to turn them on again.
- The push timer is not running: a notification the server has not handed over within 24 hours is dropped, and the
  Outbox shows it as Failed with "expired". "Expired" means only that the timer did not run for 24 hours. Check the
  System card on the Dashboard and the timer.
- The Outbox shows "push failed": the push service refused the notification on all five tries, for instance because the
  key is wrong or the phone's subscription has been removed. Check the key settings (below); if only one person's
  phone is affected, they turn notifications off and on again on the Notifications page.
- The phone was switched off or out of signal. The push service accepted the notification, so the Outbox says Sent;
  it keeps it for 24 hours and, if the phone is still off after that, drops it and the phone never shows it.
  The email is the record.
- On an iPhone, the app was opened from Safari rather than the Home Screen icon.

## Setting up phone notifications (for whoever runs the server)

Nothing is needed to use open shifts, messages, notices, uploads, the Outbox or the reports. Only phone notifications need the server set up, and
the person who looks after the server does it once. The commands are in the README, "Phone notifications (optional)"; in short:

1. **Make the key** with `vapid_keys`. It writes a private key file, `/etc/shift-central/vapid.pem`, readable only by root and
   the app's group, and prints three lines. Give `--subject` a real address (`mailto:` and an address push services can contact).
   Keep a copy of the key file: replacing it cuts off every registered phone until each person turns notifications on again.
2. **Add the three settings** it printed to `/etc/shift-central.env` and restart the app: `VAPID_PRIVATE_KEY_FILE`,
   `VAPID_PUBLIC_KEY` and `VAPID_SUBJECT`. All three, with the file present, or notifications stay off and the Notifications page
   says so. Phones of staff using Google, Mozilla, Apple or Windows push services are accepted without more; `PUSH_ENDPOINT_HOSTS` is for
   an extra service and is rarely needed.
3. **Enable the timer**, `shift-central-push.timer`. It runs every minute and sends what is queued; with nothing queued it
   does nothing. A notification can therefore arrive up to a minute after the email.

The Dashboard's System card shows whether notifications are configured, how many phones are registered and how many
notifications are waiting. Failures show in the Outbox. The upload folder, the size limit and how long the Outbox keeps
text are also settings (`MEDIA_ROOT`, `UPLOAD_MAX_BYTES`, `OUTBOX_BODY_MONTHS`) with defaults that suit the practice;
the README's settings table has them.
