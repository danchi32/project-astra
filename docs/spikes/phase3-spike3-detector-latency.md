# Phase 3 · Spike 3 — Can the D4 detectors run on a 4 GB RAM PC, fast enough to check a paste before it goes?

Status: **measured (16 Nov 2026)** on this laptop: i7-1355U, 16 GB RAM, Windows 11, .NET 8.
The 4 GB / low-end figures below are **extrapolated**. Confirming them takes one run of the
same benchmark on a real low-end PC.

## What was measured
`docs/spikes/spike3-detector-bench/` is a throwaway .NET 8 console app in the agent's
language. It is not part of the agent build. It runs the D4 detectors on synthetic text:
- Aadhaar (12 digits + Verhoeff check)
- PAN
- GSTIN (+ check character)
- card (13–19 digits + Luhn)
- +91 mobile
- email
- IFSC
- a "contact list" heuristic: 20+ lines, 60%+ of them carrying a phone or e-mail.

It ran twice: on all cores, and on **one core at below-normal priority**, which roughly
mimics a weak PC that is also busy. To repeat it: `dotnet run -c Release -- --one-core`.

## Results (one core, below-normal priority)
| Input | Time | Note |
|---|---|---|
| First scan in a process (regex build + JIT) | 33–54 ms | Paid once, when the scanner process starts |
| 1,000-character paste | 0.6 ms | |
| 10,000-character paste | 5 ms | |
| 100,000-character paste | 8 ms | |
| 1,000,000-character paste | 55 ms | Bigger than almost any real paste |
| A .docx of ~200 KB of text (unzip, strip tags, scan) | 8 ms | about 130 files/s |
| Memory | 48 MB working set, 2.4 MB managed heap | Peak 53 MB |

**Accuracy on the synthetic set:** every planted Aadhaar, PAN, card, mobile and e-mail was
found. A 500-row customer list was flagged as a contact list, and 50 KB of ordinary prose
was not. This is synthetic data and says nothing about false positives on real documents;
see "What it doesn't tell us".

## What it means for a 4 GB PC
- Typical 4 GB office PCs in India run Celeron, Pentium Silver or old Core i3 CPUs. Their
  single-thread speed is roughly **4–5× slower** than this i7-1355U.
- Scaled by 5×, a 10 KB paste takes about 25 ms and a 1 MB paste about 275 ms. **Checking a
  paste before it is released is affordable.** The D7 coaching dialog appears only when
  something is found. A clean paste waits tens of milliseconds, which nobody notices.
- **Memory:** about 50 MB for the scanner process is acceptable on 4 GB. Keep it one
  long-lived process (E4 isolation): the start-up cost is paid once, and rules compiled
  once stay compiled.
- **D5 background file scan:** at about 25 files/s after scaling, 50,000 documents take
  roughly 35 minutes of one core. Run it at low priority, throttled, outside working hours
  or when idle, and incrementally (only changed files) after the first pass. Text
  extraction from PDFs and old .doc/.xls files will be slower than .docx; that is the next
  thing to measure.

## Decision
**No ML classifier for v1.** Regular expressions plus checksums meet the latency and memory
budget with a wide margin, and they explain themselves: "Aadhaar number, checksum valid" is
a reason a person can check. Revisit only if false positives on real documents call for it.
That would be a small model (ONNX, under 20 MB) applied only to what the rules already
flagged, never to every keystroke.

## What it doesn't tell us
- **False positives on real Indian business documents.** Invoice numbers or 12-digit order
  IDs could pass Verhoeff by chance, about 1 in 10. Guard it with context words ("Aadhaar",
  "UID") or with several hits together. This needs a pilot customer's real (consented)
  samples, or a public-document corpus.
- **PDF and legacy Office extraction cost.** A library still has to be picked.
- **The browser extension side.** If detection runs *in the extension* (JavaScript), the
  numbers differ. The roadmap's E4 design sends content to the isolated local scanner over
  native messaging instead, so these .NET numbers apply. The native-messaging round trip
  (a few ms) adds on top.
- **A real low-end PC.** The 4–5× factor is an estimate. One run of the benchmark on a
  Celeron or Pentium PC confirms it.
