import { Link } from "react-router-dom";
import MeridianMark from "../components/common/MeridianMark";

interface NavCard {
  to: string;
  label: string;
  description: string;
}

const SITE_MAP: NavCard[] = [
  {
    to: "/runs",
    label: "Pipeline Runs",
    description:
      "The control tower: every processing run across all sources, filterable by pipeline and sortable by status, duration, and more. Open any run to drill in.",
  },
  {
    to: "/oltp/transactions",
    label: "Transactions",
    description:
      "The live trading feed with real-time risk scores. Generate a normal or high-risk demo trade and watch the fraud pipeline react.",
  },
  {
    to: "/demo/upload",
    label: "Excel Upload",
    description:
      "The governed spreadsheet on-ramp. Generate a valid payroll workbook — or an intentionally invalid one — to see scanning, validation, and quarantine.",
  },
  {
    to: "/backfill",
    label: "Backfill & Replay",
    description:
      "Re-process historical data through the full pipeline without rewriting history. Each backfill is a traceable, distinctly tagged run.",
  },
  {
    to: "/alerts",
    label: "Alerts",
    description:
      "One prioritized feed of every failure and risk event — quarantines, fraud flags, pipeline errors — each linked to the run that raised it.",
  },
  {
    to: "/metrics",
    label: "Metrics",
    description:
      "Platform health: live consumer-group lag (are we keeping up with real time?) and 30-day pipeline throughput and failure analytics.",
  },
];

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-lg font-semibold tracking-tight text-navy-900">
      {children}
    </h2>
  );
}

export default function HomePage() {
  return (
    <div className="space-y-10">
      {/* Hero */}
      <section className="card card-pad border-l-4 border-navy-700 bg-navy-50/40">
        <div className="flex items-start gap-4">
          <MeridianMark size={44} className="mt-1 shrink-0 rounded-md shadow-sm" />
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-navy-500">
              Meridian Data Platform &middot; Demo Console
            </p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-navy-900">
              A compliance-grade fintech data platform, end to end.
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-relaxed text-navy-700">
              This console is a working portfolio demonstration of how a regulated
              financial firm turns messy, disconnected source data into trustworthy,
              auditable analytics. It is built on the patterns a senior data engineer
              would reach for in production &mdash; event-driven ingestion, a
              bronze/silver/gold lakehouse, immutable lineage, and least-privilege
              security &mdash; and wired so you can watch a single record travel the
              whole way and prove what happened to it.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Link to="/runs" className="btn-primary">
                Browse pipeline runs
              </Link>
              <Link to="/oltp/transactions" className="btn-ghost">
                Generate a transaction
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* The project & its goals */}
      <section className="space-y-3">
        <SectionHeading>What this platform is built to prove</SectionHeading>
        <p className="max-w-3xl text-sm leading-relaxed text-navy-700">
          Financial data is hard not because it is large, but because it is{" "}
          <strong>accountable</strong>. Meridian ingests three very different
          sources and reconciles them into one governed lakehouse while satisfying
          the controls a regulator expects. The goal of the project is to demonstrate
          industry-standard data engineering under real compliance constraints
          &mdash; specifically alignment with <strong>FINRA</strong> and{" "}
          <strong>SOC&nbsp;2</strong>, with GDPR-style data handling as a stretch
          objective.
        </p>
        <p className="max-w-3xl text-sm leading-relaxed text-navy-700">
          Everything is <strong>event-driven</strong>: sources emit events, workers
          react, and every step writes an immutable record to an event store. Data
          settles into three tiers &mdash; <strong>bronze</strong> (raw,
          append-only, the legal record), <strong>silver</strong> (cleaned,
          normalized, de-duplicated, with PII masked), and <strong>gold</strong>{" "}
          (aggregated KPIs for the business). History is never edited: corrections
          arrive as new events and data is replayed forward, so any run can be
          reconstructed and audited long after the fact. Objects are encrypted at
          rest with managed keys, and every service runs under a least-privilege
          identity.
        </p>
      </section>

      {/* Meet Meridian */}
      <section className="space-y-3">
        <SectionHeading>Meet Meridian</SectionHeading>
        <p className="max-w-3xl text-sm leading-relaxed text-navy-700">
          Meridian is a (fictional) wealth-management firm. Day to day, its{" "}
          <strong>Trading Desk</strong> and client <strong>advisors</strong> execute
          trades against client accounts; <strong>People Operations</strong> runs
          payroll; <strong>Revenue Operations</strong> reconciles advisor
          commissions; and <strong>Sales</strong> maintains a CRM of client
          relationships. Each of those activities throws off data in a different
          shape, from a different system, on a different schedule.
        </p>
        <p className="max-w-3xl text-sm leading-relaxed text-navy-700">
          Behind them, <strong>Risk &amp; Compliance</strong> watches for fraud and
          regulatory breaches, the <strong>Data Platform / SRE</strong> team keeps
          the pipelines healthy, and <strong>BI</strong> and leadership rely on the
          gold-tier numbers to run the business. This platform is the connective
          tissue that lets all of those teams trust the same data.
        </p>
      </section>

      {/* How data moves */}
      <section className="space-y-3">
        <SectionHeading>How data moves through the platform</SectionHeading>
        <p className="max-w-3xl text-sm leading-relaxed text-navy-700">
          Three independent pipelines feed one shared lakehouse:
        </p>
        <ul className="max-w-3xl space-y-2 text-sm leading-relaxed text-navy-700">
          <li>
            <strong>Transactions (CDC).</strong> The Trading Desk's database streams
            every trade the moment it lands via change-data-capture, and a fraud
            model scores it in real time.
          </li>
          <li>
            <strong>Finance spreadsheets (Excel).</strong> People Ops and RevOps
            upload payroll and commission workbooks through a virus-scanned,
            schema-validated on-ramp.
          </li>
          <li>
            <strong>Salesforce (CRM).</strong> The Sales CRM is pulled in safe,
            scheduled incremental batches.
          </li>
        </ul>
        <p className="max-w-3xl text-sm leading-relaxed text-navy-700">
          All three converge through <strong>bronze &rarr; silver &rarr; gold</strong>,
          so the whole firm sees one normalized, auditable picture instead of three
          conflicting ones.
        </p>
      </section>

      {/* Site map */}
      <section className="space-y-3">
        <SectionHeading>Find your way around</SectionHeading>
        <p className="max-w-3xl text-sm leading-relaxed text-navy-700">
          Every page carries a "From the Meridian playbook" note that explains its
          business purpose in depth. Here is where each capability lives:
        </p>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {SITE_MAP.map((card) => (
            <Link
              key={card.to}
              to={card.to}
              className="card card-pad transition-colors hover:border-navy-400 hover:bg-slate-50"
            >
              <div className="text-sm font-semibold text-navy-900">{card.label}</div>
              <p className="mt-1 text-xs leading-relaxed text-navy-600">
                {card.description}
              </p>
            </Link>
          ))}
        </div>
        <p className="max-w-3xl text-sm leading-relaxed text-navy-700">
          Opening any run takes you to <strong>Run Detail</strong> &mdash; the audit
          microscope, with the full event timeline, lineage from inputs to outputs,
          the artifacts produced, any alerts raised, and a preview of the data that
          was processed.
        </p>
      </section>

      {/* Try it */}
      <section className="space-y-3">
        <SectionHeading>Try it yourself</SectionHeading>
        <p className="max-w-3xl text-sm leading-relaxed text-navy-700">
          The fastest way to understand the platform is to feed it something.
          Generate a high-risk transaction or upload a workbook, then follow it: it
          appears in <Link to="/runs" className="text-navy-700 underline">Pipeline Runs</Link>,
          its <strong>Run Detail</strong> traces every transformation, any problem
          surfaces in <Link to="/alerts" className="text-navy-700 underline">Alerts</Link>,
          and <Link to="/metrics" className="text-navy-700 underline">Metrics</Link>{" "}
          shows whether the system kept up. Intentionally break a file on the{" "}
          <Link to="/demo/upload" className="text-navy-700 underline">Excel Upload</Link>{" "}
          page to watch the quarantine guardrail catch it.
        </p>
      </section>
    </div>
  );
}
