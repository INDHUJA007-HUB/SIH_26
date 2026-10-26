import type { UseQueryResult } from "@tanstack/react-query";
import { useMemo } from "react";
import { workspacePath } from "../../shell/nav";
import type { RuleImpact } from "../../types";
import { Code, DataTable, Digest, EmptyState, ErrorState, MetaList, Panel, RuleOutcomeBadge, Skeleton, type Column } from "../../ui2";

interface Row {
  key: string;
  application_id: string;
  institution: string;
  rule_id: string;
  before: string | null;
  after: string | null;
}

function Outcome({ o }: { o: string | null }) {
  return o ? <RuleOutcomeBadge outcome={o} /> : <span className="text-ink-3">Not evaluated</span>;
}

const columns: Column<Row>[] = [
  {
    id: "application",
    header: "Application",
    sortValue: (r) => r.institution,
    cell: (r) => (
      <span className="block min-w-0">
        <span className="block">{r.institution}</span>
        <code className="block font-mono text-xs font-normal text-ink-3">{r.application_id}</code>
      </span>
    ),
  },
  { id: "rule", header: "Rule", sortValue: (r) => r.rule_id, cell: (r) => <code className="font-mono text-xs text-ink-2">{r.rule_id}</code> },
  { id: "before", header: "Before", cell: (r) => <Outcome o={r.before} /> },
  { id: "after", header: "After", cell: (r) => <Outcome o={r.after} /> },
];

/** Which applications would change outcome if their last run were evaluated under the active ruleset. */
export function Impact({ q }: { q: UseQueryResult<RuleImpact> }) {
  const rows = useMemo<Row[]>(
    () =>
      (q.data?.affected ?? []).flatMap((a) =>
        a.changes.map((c) => ({
          key: `${a.application_id}-${c.rule_id}`,
          application_id: a.application_id,
          institution: a.institution,
          rule_id: c.rule_id,
          before: c.before,
          after: c.after,
        })),
      ),
    [q.data],
  );

  if (q.isPending)
    return (
      <div role="status">
        <span className="sr-only">Computing the change impact</span>
        <Skeleton className="h-64 w-full" rounded="lg" />
      </div>
    );
  if (q.error)
    return <ErrorState error={q.error} title="Could not compute the change impact" onRetry={() => void q.refetch()} retrying={q.isFetching} />;

  return (
    <Panel
      title="Change impact"
      description="Each application's latest run is evaluated again under the active ruleset with the same inputs. Runs that already used it are skipped. Nothing is changed or re-run."
      padding="none"
    >
      <div className="px-5 pb-3 text-sm text-ink-3">
        <MetaList
          items={[
            <span key="a">
              Active ruleset <Code>{q.data.active_ruleset}</Code>
            </span>,
            <Digest key="h" value={q.data.active_hash} label="Active ruleset hash" />,
          ]}
        />
      </div>
      <div className="border-t border-line">
        {rows.length === 0 ? (
          <EmptyState
            size="sm"
            title="No application changes outcome under this ruleset."
            description="Every latest run either already used this ruleset or gives the same outcome for every rule under it."
          />
        ) : (
          <DataTable
            label="Rule outcomes that change under the active ruleset"
            rows={rows}
            columns={columns}
            rowKey={(r) => r.key}
            rowHref={(r) => workspacePath(r.application_id)}
            rowState={(r) => ({ institution: r.institution, from: "/rules?tab=impact" })}
          />
        )}
      </div>
    </Panel>
  );
}

