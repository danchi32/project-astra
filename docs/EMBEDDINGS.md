# Embeddings

Three things in ASTRA are retrieved by vector similarity: the **knowledge base**, the
**semantic cache** of answers, and **learned actions** (fixes the AI auto-applies). All
three share one embedding provider.

## What runs by default

Nothing external. With no key set, ASTRA uses `HashingEmbeddingProvider` — deterministic
feature hashing over tokens, 256 dimensions, no network and no cost. It matches on **shared
words, not meaning**:

| Query | Article | Matches? |
|---|---|---|
| "printer not printing" | "printer is offline" | yes — shared word |
| "printer not printing" | "spooler service has stopped" | **no** — no shared word |
| "my laptop is slow" | "high memory utilization" | **no** |

That last row is the reason to configure a real provider: users type symptoms, runbooks are
written in technical language, and hashing never bridges the two.

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

## Re-embedding after a change

Any provider **or model** change needs a backfill:

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
