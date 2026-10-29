# Departments

**Where:** sidebar › Departments (`/departments/`). Managers only: team managers
and all-teams managers. Staff do not see the item and are refused the page.

## The mental model

**A department is one entry in the practice's single list of the teams, roles and
tasks a shift can be tagged with** (Reception AG, Prescriptions, Workflow, Nursing
and so on). It is not the same thing as a **team**. Teams come from Practice HR
and decide *who manages whom*; departments are typed here and decide *what a
shift is for*. A nurse is in the Nursing team and may work a Nursing shift, or a
Workflow one.

**Nothing uses departments yet.** The rota grid release tags shifts with them.
Until then the list is set up in advance, so that managers can agree the names and
colours before the grid needs them. Nothing breaks if a setting here is
wrong today; it is cheaper to get it right now than once shifts reference it.

**A department is archived, never deleted.** Shifts will refer to it, and deleting
it would orphan every one. There is no delete button.

## The list

The page is a white table with **Name** (in the department's colour), **Colour**
(the hex value), **Order**, **Date added**, and an **Edit** link. Archived
departments are listed in a second table below, headed *Archived*, which is shown
only when there is at least one. **Add department +**, in the top bar, opens the
pop-up.

The practice's seventeen departments are there from the first migration, each with
a distinct starting colour: Reception AG, Reception PMC, Cleaning PMC,
Prescriptions, Private Income, Workflow, VAS/Enhanced, Scanning, Pharmacy,
Secretarial, Management, Salaried GP, Nursing, HCA, Phlebotomist, Pharmacist and
Pharmacy Technician. They are numbered 10 to 26 in that order.

## The pop-up

| Field | What it does, and what goes wrong |
|---|---|
| **Name** | Up to 60 characters, required. Must be unique **ignoring case**: "nursing" is refused as a clash with "Nursing", with the message "A department with this name already exists." Renaming keeps the department's identity, so existing shifts will follow the new name. |
| **Colour** | The tile colour on the rota and the name chip here. Pick a swatch or type `#rrggbb`. Anything else is refused with "Choose a colour." New departments start on blue (`#2F6FB3`); pick another, as two departments the same colour cannot be told apart on a grid. A pale colour makes white text unreadable. |
| **Display order** | A whole number, 0 or more, default 100. Lower comes first; ties fall back to alphabetical. A new department with the default sits after the seventeen seeded ones (10 to 26). To put one between two others, give it a number between theirs; there is no drag to reorder. |
| **Archived** | Shown only when editing. Tick it to retire a department: it moves to the *Archived* table, and the rota grid release will stop offering it for new shifts while leaving the ones already tagged with it intact. Untick it to bring it back. Archiving something in use is safe; deleting would not have been. |

The button reads **Add department** or **Update department**. A form error
(the clashing name, a bad colour) comes back in the same pop-up with the other
fields as you typed them.

## Who can do what

Any manager, of any team, can add, edit, recolour, reorder and archive any
department. They are the practice's list, not a team's. Every change is recorded
(who, when, which field, from what, to what) and appears in the
[Activity log](access.md#the-two-logs) for every manager, under the record name
*department*; the log is the place to look when a colour changes unexpectedly.
