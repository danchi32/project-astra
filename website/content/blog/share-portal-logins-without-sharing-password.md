---
title: "How to Share Portal Logins With Your Team Without Sharing the Password"
description: "Shared vendor and client portal logins end up in spreadsheets and chat threads. Here is how to give a team access to a portal without any of them knowing the password."
date: "2026-09-27"
author: "Technomate IT-Solution"
keywords:
  - share passwords with team securely
  - shared login security
  - team password sharing best practices
  - vendor portal access management
  - stop sharing passwords in spreadsheets
---

Somewhere in your company there is a spreadsheet with a column called `Password`.

It exists because a portal you depend on — a client system, a vendor platform, a supplier's ordering site — issues exactly one login, and eight people need it. Nobody decided to do it this way. It happened because the portal gave you no other option, and work had to get done.

The spreadsheet is the visible half of the problem. The invisible half is that the password is now in eight people's heads, three chat threads, and at least one screenshot.

## What a shared login actually costs you

**You cannot take it back.** Access granted by telling someone a password can only be withdrawn by changing that password — which means finding every portal, changing each one by hand, and then redistributing the new one to everyone who still needs it. In practice most teams skip it, which is why leavers keep working access for months.

**You cannot say who did anything.** When a portal asks who approved a change or downloaded a report, a shared login answers "all of you". There is no record on your side that can narrow it down, and the portal's own log only shows the one account.

**It spreads faster than you track it.** Every forward, paste and screenshot is another copy. None of them are logged, and none of them expire.

If your industry has an audit obligation, this is usually the finding that comes back first — not because anything went wrong, but because you cannot demonstrate that it didn't.

## Why the usual fixes don't hold

**"We rotate it every quarter."** Rotation is a good instinct and a poor control. It shrinks the window rather than closing it, it costs a person a day each time, and it fails the moment someone is missed off the redistribution list — which is also the moment someone quietly keeps the old one written down.

**"We use a password manager."** Better, but most consumer and team password managers are built to *show* people a credential. The vault holds it, the person reveals it, copies it, pastes it into the portal. The moment it is revealed, it is shared again — and now it is in a clipboard too.

**"Each person should have their own portal account."** The right answer, where it is available. It very often is not. Plenty of vendor and client portals issue one account per company, charge per seat, or take weeks to provision — which is precisely why the spreadsheet exists.

## The idea that actually works: share the access, not the secret

The important shift is separating two things that usually travel together:

- **Access** — being able to get into the portal and do your job
- **Knowledge** — being able to repeat the password to somebody else

Almost every team treats these as the same thing. They are not. It is entirely possible to give someone the first without the second: the credential lives encrypted, and software puts it into the portal's login form on their behalf, without ever displaying it.

The person signs in. They never learn the password. They could not pass it on if they wanted to — and on the day they leave, you remove them, and nothing has to be rotated at all.

## A practical checklist

If you are fixing this, work through these in order:

### 1. Find every shared login
Start with the spreadsheet, then ask each team which portals they use that IT has never heard of. The second list is usually longer than the first.

### 2. Put them somewhere encrypted
One place, encrypted at rest, that nobody browses casually. Not a document, not a chat pin, not a shared note.

### 3. Assign access by group, not by person
People change teams. Groups do not. Assign a portal to "operations" rather than to nine individuals, and joiners and leavers become a one-line change.

### 4. Stop showing the credential
This is the step most teams skip, and it is the one that makes the rest work. If the password can be revealed, it will eventually be revealed — usually in a hurry, to somebody helping out for an afternoon.

### 5. Make sure somebody is keeping the record
Who opened which portal, from where, and when. Not for surveillance — for the day a client asks and "we think it was someone in operations" is not an acceptable answer.

### 6. Handle the second factor too
Portals increasingly send a one-time code or expect an authenticator app. If your answer is "the code goes to one person's phone", you have recreated the original problem with extra steps. The code needs to reach whoever is signing in, without a shared handset.

### 7. Close the loop on leaving
Removing someone should end their access everywhere at once — every browser, every device — and it should take seconds. Tie it to your offboarding process; our [IT offboarding checklist](/blog/secure-employee-offboarding-checklist/) covers the rest of that first hour.

## What to look for in a tool

Whatever you choose, check these specifically. They are the ones that separate a real answer from a tidier spreadsheet:

- **Is there a reveal button?** If yes, assume every credential will be revealed eventually.
- **Can it fill a portal that uses single sign-on?** Many portals hand you off to an identity provider for the actual login. A tool that loses track at the redirect will not work on your hardest portals.
- **Does it handle one-time codes?** Both kinds — authenticator apps and codes sent by email.
- **What does removal actually do?** Ending future logins is not the same as ending the session somebody has open right now.
- **Can you restrict where people sign in from?** Network rules should apply to every route in, including the API and any browser extension — not just the website.
- **What does the log contain?** "User signed in" is not evidence. The person, the portal, the address, the browser and the time is.

## Where Secure Vault fits

We built [Secure Vault](/vault/) for exactly this problem, and the non-revealing part is the point rather than a feature.

Credentials are encrypted and assigned by group. When somebody opens a portal, a browser extension fills the login form and submits it behind a cover screen — the fields stay masked as they are filled, there is no reveal control anywhere, and copying out of them is blocked. One-time codes are generated or read from a mailbox and entered automatically. Every launch is written to an audit log with the address and browser it came from, and removing a person ends every session and paired browser they had.

They get in. They never see the password. On the day they leave, you remove them, and there is nothing to rotate.

If that is the shape of your problem, [have a look at how it works](/vault/) — or [talk to us](/contact/) and we will set it up against your own portals so you can see the audit trail on real data.
