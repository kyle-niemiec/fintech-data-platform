import { useSessionTimer } from "../../hooks/useSessionTimer";
import { useNow } from "../../lib/useNow";

/**
 * Formats remaining seconds into "M:SS" format.
 * 
 * @param {number} seconds The number of seconds remaining in the session
 * 
 * @returns {string} Formatted time string
 */
function formatRemaining(seconds: number): string {
	const minutes = Math.floor(seconds / 60);
	const secs = seconds % 60;

	return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

/**
 * A component that displays the remaining time for the current session.
 * 
 * @returns {JSX.Element} The session timer element, or null if no active session
 */
export default function SessionTimer() {
	const { stopAt } = useSessionTimer();
	const now = useNow();

	if (! stopAt) {
		return null;
	}

	// Calculate remaining seconds, ensuring it doesn't go negative
	const remainingSec = Math.max(0, Math.floor((stopAt.getTime() - now) / 1000));

	if (remainingSec === 0) {
		return null;
	}

	// Return a badge showing the remaining session time in "M:SS" format
	return (
		<span className="rounded-full border border-navy-200 bg-slate-100 px-3 py-1 text-[11px] font-medium uppercase tracking-wider text-navy-700">
			Session · {formatRemaining(remainingSec)}
		</span>
	);
}
