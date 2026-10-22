"use client";
import { useEffect, useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Info, Plus, Trash2, Save } from "lucide-react";
import { getMe } from "@/lib/api/auth";
import {
  getCategories,
  putCategories,
  type Bucket,
  type CategoryOverrides,
} from "@/lib/api/tracker";
import {
  UpgradeRequired,
  isUpgradeRequired,
  requiredFeature,
} from "@/components/upgrade-required";

const BUCKET_META: Record<Bucket, { label: string; color: string }> = {
  productive: { label: "Productive", color: "#10b981" },
  neutral: { label: "Neutral", color: "#64748b" },
  unproductive: { label: "Unproductive", color: "#ef4444" },
};

/** One editable override row. The key is a website host or an app keyword; order is just
 *  insertion order so the list is stable while editing. */
interface Rule {
  key: string;
  bucket: Bucket;
}

function toRules(map: Record<string, Bucket>): Rule[] {
  return Object.entries(map).map(([key, bucket]) => ({ key, bucket }));
}

/** Rules → the wire map, dropping blank keys and keeping the last value when a key repeats. */
function toMap(rules: Rule[]): Record<string, Bucket> {
  const out: Record<string, Bucket> = {};
  for (const r of rules) {
    const k = r.key.trim().toLowerCase();
    if (k) out[k] = r.bucket;
  }
  return out;
}

function BucketSelect({
  value, onChange, disabled, buckets,
}: { value: Bucket; onChange: (b: Bucket) => void; disabled: boolean; buckets: Bucket[] }) {
  return (
    <select
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value as Bucket)}
      className="px-2 py-1.5 rounded-lg text-sm outline-none disabled:opacity-60"
      style={{
        background: "var(--bg)", border: "1px solid var(--border)",
        color: BUCKET_META[value].color, fontWeight: 600,
      }}
    >
      {buckets.map((b) => (
        <option key={b} value={b} style={{ color: "var(--text-primary)" }}>
          {BUCKET_META[b].label}
        </option>
      ))}
    </select>
  );
}

/** The editor for one kind of rule (websites or apps): a list of key → bucket rows, plus an
 *  add row. It owns no server state, just reports changes up. */
function RuleEditor({
  title, placeholder, rules, buckets, editable, onChange,
}: {
  title: string;
  placeholder: string;
  rules: Rule[];
  buckets: Bucket[];
  editable: boolean;
  onChange: (rules: Rule[]) => void;
}) {
  const [newKey, setNewKey] = useState("");
  const [newBucket, setNewBucket] = useState<Bucket>("productive");

  const add = () => {
    const k = newKey.trim().toLowerCase();
    if (!k) return;
    const rest = rules.filter((r) => r.key.trim().toLowerCase() !== k);
    onChange([...rest, { key: k, bucket: newBucket }]);
    setNewKey("");
  };

  return (
    <div className="rounded-2xl overflow-hidden" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <div className="px-5 py-3 border-b" style={{ borderColor: "var(--border)" }}>
        <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{title}</h3>
      </div>
      <div className="p-5 space-y-2">
        {rules.length === 0 && (
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            No custom rules — the built-in defaults apply.
          </p>
        )}
        {rules.map((r, i) => (
          <div key={`${r.key}-${i}`} className="flex items-center gap-2">
            <input
              value={r.key}
              disabled={!editable}
              onChange={(e) =>
                onChange(rules.map((x, j) => (j === i ? { ...x, key: e.target.value } : x)))}
              className="flex-1 px-3 py-1.5 rounded-lg text-sm outline-none disabled:opacity-60"
              style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
            />
            <BucketSelect
              value={r.bucket} disabled={!editable} buckets={buckets}
              onChange={(b) => onChange(rules.map((x, j) => (j === i ? { ...x, bucket: b } : x)))} />
            {editable && (
              <button
                onClick={() => onChange(rules.filter((_, j) => j !== i))}
                className="p-1.5 rounded-lg" title="Remove rule"
                style={{ color: "var(--text-secondary)", border: "1px solid var(--border)" }}
              >
                <Trash2 size={14} />
              </button>
            )}
          </div>
        ))}
        {editable && (
          <div className="flex items-center gap-2 pt-2">
            <input
              value={newKey}
              placeholder={placeholder}
              onChange={(e) => setNewKey(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") add(); }}
              className="flex-1 px-3 py-1.5 rounded-lg text-sm outline-none"
              style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
            />
            <BucketSelect value={newBucket} disabled={false} buckets={buckets} onChange={setNewBucket} />
            <button
              onClick={add}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium"
              style={{ border: "1px solid var(--border)", color: "var(--text-primary)" }}
            >
              <Plus size={14} /> Add
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

/** Read-only reference: the built-in default bucket for every known app/site, so an admin can
 *  see what they'd be overriding. Collapsed by default — it's long. */
function BuiltinReference({ builtin }: { builtin: CategoryOverrides }) {
  const rows = useMemo(
    () => [
      ...Object.entries(builtin.domain).map(([k, b]) => ({ k, b, kind: "site" })),
      ...Object.entries(builtin.app).map(([k, b]) => ({ k, b, kind: "app" })),
    ],
    [builtin],
  );
  return (
    <details className="rounded-2xl" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <summary className="px-5 py-3 cursor-pointer text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
        Built-in defaults ({rows.length})
      </summary>
      <div className="px-5 pb-5 max-h-72 overflow-y-auto">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5">
          {rows.map(({ k, b, kind }) => (
            <div key={`${kind}-${k}`} className="flex items-center justify-between gap-2 text-sm">
              <span className="truncate" style={{ color: "var(--text-secondary)" }} title={k}>
                {k} <span style={{ opacity: 0.5 }}>· {kind}</span>
              </span>
              <span className="shrink-0 text-xs font-medium" style={{ color: BUCKET_META[b].color }}>
                {BUCKET_META[b].label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </details>
  );
}

/** The Configuration > Categories section: reclassify apps/sites into the three scoring buckets.
 *  Self-contained — its own query, its own Save — so it drops into the Configuration page beside
 *  other setup sections. */
export function CategoryConfig() {
  const qc = useQueryClient();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const isAdmin = me?.role === "admin";

  const { data, error } = useQuery({
    queryKey: ["tracker-categories"],
    queryFn: getCategories,
    retry: (count, err) => !isUpgradeRequired(err) && count < 2,
  });

  const [domainRules, setDomainRules] = useState<Rule[]>([]);
  const [appRules, setAppRules] = useState<Rule[]>([]);
  useEffect(() => {
    if (data) {
      setDomainRules(toRules(data.overrides.domain));
      setAppRules(toRules(data.overrides.app));
    }
  }, [data]);

  const save = useMutation({
    mutationFn: (body: CategoryOverrides) => putCategories(body),
    onSuccess: (fresh) => qc.setQueryData(["tracker-categories"], fresh),
  });

  if (isUpgradeRequired(error)) {
    return <UpgradeRequired feature={requiredFeature(error)} />;
  }

  const buckets = data?.buckets ?? ["productive", "neutral", "unproductive"];
  const dirty =
    !!data &&
    (JSON.stringify(toMap(domainRules)) !== JSON.stringify(data.overrides.domain) ||
      JSON.stringify(toMap(appRules)) !== JSON.stringify(data.overrides.app));

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="flex-1">
          <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
            Productivity categories
          </h2>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
            Decide which apps and websites count as productive, neutral or unproductive
          </p>
        </div>
        {isAdmin && (
          <button
            onClick={() => save.mutate({ domain: toMap(domainRules), app: toMap(appRules) })}
            disabled={!dirty || save.isPending}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
            style={{ background: "var(--accent)", color: "#fff" }}
          >
            <Save size={14} /> {save.isPending ? "Saving…" : "Save changes"}
          </button>
        )}
      </div>

      <div
        className="rounded-xl px-4 py-3 flex items-start gap-2 text-xs"
        style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}
      >
        <Info size={14} className="mt-0.5 shrink-0" style={{ color: "var(--accent)" }} />
        <span>
          A rule overrides the built-in default for one website host (e.g. <code>youtube.com</code>)
          or app keyword (e.g. <code>figma</code>). New rules apply to activity scored from now
          on — days already rolled up keep their buckets until the next time that device reports.
          {!isAdmin && " Only an admin can change these; you're viewing them read-only."}
        </span>
      </div>

      {save.isError && (
        <p className="text-sm" style={{ color: "#ef4444" }}>
          Could not save — please check the rules and try again.
        </p>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RuleEditor
          title="Website rules"
          placeholder="host, e.g. reddit.com"
          rules={domainRules}
          buckets={buckets}
          editable={!!isAdmin}
          onChange={setDomainRules}
        />
        <RuleEditor
          title="App rules"
          placeholder="app keyword, e.g. myinternaltool"
          rules={appRules}
          buckets={buckets}
          editable={!!isAdmin}
          onChange={setAppRules}
        />
      </div>

      {data && <BuiltinReference builtin={data.builtin} />}
    </section>
  );
}
