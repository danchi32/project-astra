# Embeddings

Three things in ASTRA are retrieved by vector similarity: the **knowledge base**, the
**semantic cache** of answers, and **learned actions** (fixes the AI auto-applies). All
three share one embedding provider.

## What runs by default

Nothing external. With no key set, ASTRA uses `HashingEmbeddingProvider` — deterministic
feature hashing over tokens, 256 dimensions, no network and no cost. It matches on **shared
words, not meaning**:

It stems (`printing` → `print`, so it meets `printer`) and drops stopwords — including
Hinglish filler like `hai` / `nahi` / `raha`, which appears in nearly every complaint and
therefore separates nothing.

| Query | Article | Matches? |
|---|---|---|
| "printer not printing" | "printer is offline" | yes |
| "printers keep failing" | "printer troubleshooting" | yes — stemming |
| "printer not printing" | "spooler service has stopped" | **no** — no shared word |
| "my laptop is slow" | "high memory utilization" | **no** |

Those last two rows are what aliases (below) exist to fix, and what a real embedding model
would fix more generally.

> ⚠️ The tokenizer is part of the vector space. `HashingEmbeddingProvider.VERSION` is in
> the provider name (`hash-v2-256`) for exactly that reason — change the stemming or the
> stopword list and you must bump it, or search will compare old vectors against new ones
> and score every existing article at zero without raising anything.

## Configuring a real provider

Anthropic does not offer an embeddings endpoint; it recommends
[Voyage AI](https://docs.voyageai.com/reference/embeddings-api), which is what ASTRA
implements.

```bash
ASTRA_VOYAGE_API_KEY=pa-...          # that alone switches it on
ASTRA_VOYAGE_MODEL=voyage-4-lite     # default; voyage-4 / voyage-4-large also available
ASTRA_EMBEDDING_PROVIDER=auto        # auto | voyage | hash
```

- `auto` (default) — Voyage when a key is present, hashing otherwise.
- `voyage` — **refuses to start** without a key rather than silently falling back. Falling
  back would write hash vectors into a base the operator believes is running a real model,
  and the two are not comparable.
- `hash` — force the offline provider even if a key exists.

## The one thing that will bite you: vector spaces

**Vectors from two different models are not comparable.** Not "less accurate" —
meaningless. Cosine similarity between a 256-dim hash vector and a 1024-dim Voyage vector
returns `0.0`, and `0.0` is indistinguishable from "no match".

Left alone, that means the day you set a Voyage key, every existing article scores zero
against every query and **the knowledge base looks empty rather than broken**. No error, no
log, nothing to search for.

So every stored vector records the provider that produced it, in `embedding_model`
(`hash-256`, `voyage:voyage-4-lite`, …), and search filters to the current provider's rows.
The consequence per store:

| Store | Rows on an old model | Impact until re-embedded |
|---|---|---|
| Knowledge base | skipped, and **logged as a warning** naming the fix | articles aren't found |
| Semantic cache | skipped silently | one extra LLM call — self-correcting |
| Learned actions | skipped silently | the AI stops auto-applying fixes it knows |

## Making articles findable: aliases

The provider is only half the answer. Even a perfect embedding can't match words that
aren't there — and technicians and employees don't use the same words.

So when an article is created, ASTRA asks Claude once for the phrasings a non-technical
user would actually type (including Hinglish, because they do), and stores them on the
article. They're matched against but never displayed.

```
Article : "High memory utilization troubleshooting"
Aliases : "mera laptop bahut slow hai" · "system hang ho raha hai" · "laptop is slow"
```

One call per article write — not per search — so the cost sits on the rare side. Inert
without an Anthropic key, and a failed call never blocks the save: an article with no
aliases is findable by fewer words, an article that wouldn't save is a technician's work
thrown away.

Learned articles get this for free from the other direction: `symptom_samples` already
holds the real user phrasings that preceded a confirmed fix. Both sources fill the same
column, so vocabulary grows from prediction *and* from evidence.

## Re-embedding after a change

Any provider, model, **or tokenizer** change needs a backfill. In production, run the
**Re-embed stored vectors** workflow (manual, `dry_run` on by default) — it executes as a
Cloud Run job against the image the service is currently running, so prod database
credentials never touch a laptop.

Locally:

```bash
python scripts/reembed.py --dry-run   # how many rows, before you spend anything
python scripts/reembed.py
```

Safe to re-run and safe to interrupt — it commits per batch and skips rows already on the
current model, so a second run resumes. If the API starts failing it stops rather than
grinding through; failed rows keep their previous vectors and stay excluded from search,
which is the state they were already in.

## Indexing vs searching

Retrieval models are asymmetric: a document is embedded to be *found*, a query to *find*.
Voyage prepends a different instruction for each. `embed()` therefore takes `purpose` as a
**required** argument — no default, because getting it wrong costs accuracy with no visible
symptom.

## Cost

Voyage bills per token. The volume here is small — one embedding per article write, one per
learned-fix confirmation, one per chat message that reaches the cache or KB lookup. The
backfill is the only bulk operation, which is why `--dry-run` reports the row count first.
