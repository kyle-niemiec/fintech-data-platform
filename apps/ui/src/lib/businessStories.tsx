import type { ReactNode } from "react";

// Onboarding-voice business narratives, one per page. Each explains the problem
// the business faces, how the platform solves it, and which on-page elements to
// look at, referencing the Meridian departments that own each surface. Rendered
// through components/common/BusinessStory.
export interface Story {
  title: string;
  body: ReactNode;
}

export const businessStories: Record<string, Story> = {
  runs: {
    title: "Every record has to be accountable.",
    body: (
      <>
        <p>
          Meridian is a wealth-management firm: we execute trades for client
          accounts, run payroll and advisor commissions, and keep a CRM of client
          relationships &mdash; all data that regulators (FINRA, SOC&nbsp;2) expect
          us to account for byte by byte. A <strong>pipeline</strong> is one
          automated assembly line that takes raw data from a source system and
          moves it through tiers &mdash; bronze (raw, immutable record), silver
          (cleaned and normalized), gold (aggregated KPIs) &mdash; validating it
          along the way. The Runs view is the control tower: each row is a single
          execution of one of those pipelines, stamped with its source, current
          stage, status, and duration.
        </p>
        <p>
          We run a pipeline per source, and each serves a different part of the
          business. The <strong>CDC pipeline</strong> processes the{" "}
          <strong>Trading Desk's</strong> transaction database; the{" "}
          <strong>Excel pipeline</strong> processes finance workbooks from{" "}
          <strong>People Operations</strong> (payroll) and{" "}
          <strong>Revenue Operations</strong> (advisor commissions); the{" "}
          <strong>Salesforce pipeline</strong> pulls the CRM that{" "}
          <strong>Sales</strong> maintains. They run independently but converge:
          every source lands in append-only bronze, is cleaned into silver for{" "}
          <strong>Data Science</strong> and analysts, then aggregated into the gold
          KPIs <strong>BI</strong> and leadership read &mdash; so the whole firm
          sees one normalized picture.
        </p>
        <p>
          This is where the <strong>Data Platform / SRE</strong> team lives. When
          the desk reports something looks off, start here: filter to a single
          pipeline to isolate a source during an incident, sort by{" "}
          <strong>Status</strong> to push failures and quarantines to the top, or
          sort by <strong>Duration</strong> to find the run that's dragging &mdash;
          then open it for the full evidence trail.
        </p>
      </>
    ),
  },
  transactions: {
    title: "Catch the bad trade before it settles.",
    body: (
      <>
        <p>
          These are trades, and the customer isn't booking them directly &mdash;
          the <strong>Trading Desk</strong> and client-facing{" "}
          <strong>advisors</strong> execute orders against client{" "}
          <strong>accounts</strong> (the account on each row), with some flowing in
          from the client app. Every order is written to our transactions database,
          the front office's system of record. A single fraudulent or mis-booked
          trade can cost real money and trigger regulatory scrutiny, so it has to be
          checked the moment it happens.
        </p>
        <p>
          The <strong>Instrument</strong> is the security being traded &mdash; a
          stock ticker like AAPL or NVDA &mdash; and the <strong>Amount</strong> is
          the dollar value of the order. The instant a trade lands,
          change-data-capture streams it off the database and our fraud model scores
          it, so risk is assessed in real time rather than in an overnight batch.
        </p>
        <p>
          The <strong>Risk Score</strong> is a continuous value between 0 and 1 from
          a smooth curve, <em>r(x) = 1 &minus; r_f / (x + r_f)</em>: the larger the
          trade amount <em>x</em>, the closer the score creeps to 1. Each instrument
          is calibrated with its own alert amount &mdash; the dollar size at which
          the score hits our 0.9 line (roughly $10k for AAPL but $1k for NVDA)
          &mdash; because a $9k order is routine for one security and alarming for
          another. Anything scoring 0.9 or above is flagged.
        </p>
        <p>
          A flag raises a high-severity alert for <strong>Risk &amp; Compliance</strong>,
          and a genuinely suspicious pattern is handed to the{" "}
          <strong>Financial Crime Unit</strong>, which can open a formal
          investigation and escalate to a regulatory filing. On this page, red flags
          mark trades the model judged high-risk and a <strong>Manual</strong> flag
          marks one an analyst injected to rehearse that path; sort by{" "}
          <strong>Risk Score</strong> to bring the riskiest to the top, and click a
          scored row to open the run that assessed it.
        </p>
      </>
    ),
  },
  excelUpload: {
    title: "Spreadsheets, without the spreadsheet risk.",
    body: (
      <>
        <p>
          Two teams still run core processes in Excel.{" "}
          <strong>People Operations</strong> uploads <strong>payroll</strong>{" "}
          workbooks &mdash; one row per employee with an employee ID, the pay-period
          end date, gross and net pay, and currency.{" "}
          <strong>Revenue Operations</strong> uploads{" "}
          <strong>commission adjustments</strong> for advisors &mdash; an advisor ID,
          the adjustment date and amount, a reason (retro credit, chargeback, or
          manual override), and currency. Ungoverned spreadsheets &mdash; no
          validation, no audit trail, no idea what got loaded &mdash; are one of the
          biggest compliance liabilities a firm carries.
        </p>
        <p>
          This is the governed on-ramp, open only to finance uploaders. A file is
          virus-scanned, size- and type-checked, then validated against a registered
          schema contract for its kind. Clean files are stored in append-only raw
          storage under their run ID and promoted into the lakehouse; anything that
          fails is <strong>quarantined</strong>.
        </p>
        <p>
          A <strong>quarantined</strong> file passed the virus scan but failed schema
          validation &mdash; a missing or malformed column, for instance (use the
          invalid option to drop the required <em>net_amount</em> column and watch it
          happen). It is set aside in a quarantine area, never loaded into the
          lakehouse, and an alert fires so the uploading team &mdash;{" "}
          <strong>Payroll</strong> or <strong>RevOps</strong> &mdash; can fix and
          resubmit. <strong>Risk &amp; Compliance</strong> sees the same alert,
          because a rejected financial load is itself an auditable event.
        </p>
      </>
    ),
  },
  backfill: {
    title: "Fix the past without rewriting history.",
    body: (
      <>
        <p>
          A <strong>backfill</strong> is a deliberate re-processing of historical
          data for a chosen source and date. You'd run one when data arrived late,
          an upstream system had an outage, or a bug was found and fixed and the
          corrected records still need to flow through. It is not an everyday action
          &mdash; it's the controlled exception, normally run by{" "}
          <strong>Data Platform / SRE</strong> at the request of{" "}
          <strong>Finance</strong> or <strong>Risk &amp; Compliance</strong>.
        </p>
        <p>
          The golden rule is that we never edit history. Our lakehouse is
          append-only, so a backfill <em>replays</em> through the same validated
          pipelines as live data rather than overwriting the past, and each backfill
          run is tagged distinctly so it never masquerades as real-time activity.
        </p>
        <p>
          BI receives it <strong>idempotently</strong> &mdash; replaying the same
          period does not double-count. The silver layer MERGEs each record on its
          business key, so a second run of the same data updates the same rows
          instead of appending new ones, and checkpoints record what has already been
          promoted. You can confirm it from the UI: the run carries the{" "}
          <strong>Backfill</strong> tag in the Runs view, and opening its{" "}
          <strong>Lineage</strong> shows the same inputs mapping to the same outputs.
          Gold KPIs recompute from the de-duplicated silver tables, so the executive
          dashboards stay correct no matter how many times a period is replayed.
        </p>
      </>
    ),
  },
  alerts: {
    title: "One queue for everything that needs attention.",
    body: (
      <>
        <p>
          This page is one feed of every failure and risk event across all pipelines:
          quarantined uploads, high-risk trades flagged by the fraud model, and
          outright pipeline errors. Each alert carries a severity, a category, a short
          summary, the underlying details, and a link to the run that raised it. (In
          production these would also page an on-call Slack channel; in this console
          they all land here so any observer can see them.)
        </p>
        <p>
          <strong>Risk &amp; Compliance</strong> monitors the feed as the first line
          of defense; <strong>Data Platform / SRE</strong> owns the operational
          failures &mdash; a crashed job or a stuck pipeline &mdash; and the{" "}
          <strong>Financial Crime Unit</strong> picks up genuine fraud signals. Yes,
          Meridian does launch formal financial investigations: a confirmed high-risk
          pattern becomes a documented case and, where required, a regulatory filing.
        </p>
        <p>
          Severity routes the response. <strong>High</strong> &mdash; a fraud flag or
          a hard pipeline failure &mdash; demands an immediate owner;{" "}
          <strong>medium</strong> is worked in normal operations; <strong>low</strong>{" "}
          is informational. Sort by <strong>Severity</strong> to work top-down or by{" "}
          <strong>Category</strong> to batch similar issues, and click any alert to
          land on the offending run with full context.
        </p>
      </>
    ),
  },
  metrics: {
    title: "Proof the platform is keeping up.",
    body: (
      <>
        <p>
          Leadership and <strong>Risk &amp; Compliance</strong> care about three
          things here: is the data <strong>timely</strong>, is the platform{" "}
          <strong>healthy</strong>, and are we <strong>failing</strong> anywhere?
          Falling behind real time means stale risk scores and late regulatory
          reporting &mdash; exactly what you don't want a regulator to discover first.
        </p>
        <p>
          <strong>Consumer-group lag</strong> is a streaming measure. Each pipeline is
          a <em>consumer</em> reading a stream of events; lag is how many events it
          hasn't processed yet &mdash; the backlog between what has been produced and
          what has been consumed, broken out per partition. Zero (green) means it's
          caught up to real time; a growing number (amber, then red) means it's
          falling behind.
        </p>
        <p>
          A worker that is down or undersized lets lag climb, so{" "}
          <strong>Data Platform / SRE</strong> fixes it by restarting or scaling out
          the consumer to drain the backlog &mdash; or, if one poisoned message is
          blocking progress, by correcting the cause and replaying from the last good
          offset (events are append-only, so we always replay forward, never edit).
          The same playbook covers a failing pipeline: read its alert, fix the root
          cause, replay from the last checkpoint. Expand a group and sort by{" "}
          <strong>Lag</strong> to find the worst offender, and use the 30-day
          analytics to spot a degrading source before it becomes an incident.
        </p>
      </>
    ),
  },
  runDetail: {
    title: "The audit microscope for a single run.",
    body: (
      <>
        <p>
          When you're investigating one specific run &mdash; for an audit, a bug, or
          a customer question &mdash; you need the whole story in one place, not
          scattered across logs. This page reconstructs it from the event store.
        </p>
        <p>
          The <strong>Events</strong> timeline shows every state transition in order;{" "}
          <strong>Lineage</strong> traces inputs to outputs so you can prove what fed
          what; <strong>Artifacts</strong> lists the exact objects produced;{" "}
          <strong>Alerts</strong> surfaces anything it raised; and{" "}
          <strong>Preview</strong> shows the data that was processed.
        </p>
        <p>
          To see how one run affects the big picture, follow its connections. Every
          run records its source, its parent run, and the input and output objects it
          touched, so <strong>Lineage</strong> links this run's outputs to the
          bronze, silver, and gold objects they became, and a curated run points back
          to the source run that triggered it. That lets you trace a single payroll
          upload or trade all the way to the gold KPIs <strong>BI</strong> reports on
          &mdash; and prove, run by run, that the aggregate picture is built only from
          accountable units of work.
        </p>
      </>
    ),
  },
};
