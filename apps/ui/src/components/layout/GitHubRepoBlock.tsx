import { useEffect, useState } from "react";

const REPO_SLUG = "kyle-niemiec/fintech-data-platform";
const REPO_URL = `https://github.com/${REPO_SLUG}`;
const REPO_API = `https://api.github.com/repos/${REPO_SLUG}`;

interface RepoStats {
  stars: number;
  forks: number;
}

export default function GitHubRepoBlock() {
  const [stats, setStats] = useState<RepoStats | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(REPO_API)
      .then((res) => {
        if (! res.ok) {
          throw new Error(`GitHub API ${res.status}`);
        }
        return res.json() as Promise<{
          stargazers_count: number;
          forks_count: number;
        }>;
      })
      .then((data) => {
        if (cancelled) return;
        setStats({ stars: data.stargazers_count, forks: data.forks_count });
      })
      .catch(() => {
        if (cancelled) return;
        setFailed(true);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const stars = failed ? null : stats?.stars ?? null;
  const forks = failed ? null : stats?.forks ?? null;

  return (
    <a
      href={REPO_URL}
      target="_blank"
      rel="noreferrer"
      title="Go to repository"
      className="inline-flex items-center gap-2 rounded-full border border-navy-400/40 bg-navy-800 px-3 py-1 text-navy-100 transition-colors hover:bg-navy-700 hover:text-white"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="currentColor"
        className="h-4 w-4 shrink-0"
        aria-hidden="true"
      >
        <path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.56v-1.95c-3.2.7-3.87-1.54-3.87-1.54-.52-1.33-1.27-1.68-1.27-1.68-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.18 1.76 1.18 1.02 1.75 2.68 1.25 3.34.95.1-.74.4-1.25.72-1.54-2.55-.29-5.23-1.28-5.23-5.7 0-1.26.45-2.29 1.18-3.1-.12-.29-.51-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11.07 11.07 0 0 1 2.9-.39c.98 0 1.97.13 2.9.39 2.21-1.49 3.18-1.18 3.18-1.18.63 1.59.23 2.76.11 3.05.73.81 1.18 1.84 1.18 3.1 0 4.43-2.69 5.41-5.25 5.69.41.36.78 1.07.78 2.15v3.19c0 .31.21.68.8.56C20.21 21.39 23.5 17.08 23.5 12 23.5 5.65 18.35.5 12 .5z" />
      </svg>
      <span className="flex flex-col leading-tight">
        <span className="text-[11px] font-medium">{REPO_SLUG}</span>
        <span className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-navy-300">
          <span className="inline-flex items-center gap-1">
            <span aria-hidden="true">★</span>
            <span>{stars ?? "—"}</span>
          </span>
          <span className="inline-flex items-center gap-1">
            <span aria-hidden="true">⑂</span>
            <span>{forks ?? "—"}</span>
          </span>
        </span>
      </span>
    </a>
  );
}
