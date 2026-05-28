import { useEffect } from "react";
import { useSessionTimer } from "../../hooks/useSessionTimer";
import { useNow } from "../../lib/useNow";

/**
 * Full-screen overlay shown when the demo session timer has expired and the
 * launcher reports that the EC2 instance is no longer running. Once the
 * instance reports "stopped", the user is redirected back to "/" with a
 * cache-busting query so CloudFront origin failover lands them on the
 * launcher landing page.
 *
 * @returns {JSX.Element|null} The shutdown modal, or null when the session is still active.
 */
export default function ShutdownOverlay() {
	const { stopAt, instanceState } = useSessionTimer();
	const now = useNow();

	const hasExpired = stopAt !== null && now >= stopAt.getTime();
	const isStopping = instanceState === "stopping";
	const isStopped = instanceState === "stopped";

	useEffect( () => {
		// "stopped" is unambiguous: redirect regardless of whether we ever observed the
		// original stop time (covers late page-load + the API's null window after EventBridge fires).
		if ( isStopped ) {
			window.location.replace( `/` );
		}
	}, [ isStopped ] );

	// Show the modal once shutdown is observable: either the timer expired and we have
	// confirmation the instance is no longer running, or the launcher is directly reporting
	// stopping/stopped (which is the authoritative signal once stop_scheduled_at has cleared).
	// Treat a null instanceState (no data yet) as still-running to avoid spurious modals from
	// a transient fetch failure.
	const shouldShow =
		isStopping ||
		isStopped ||
		( hasExpired && instanceState !== null && instanceState !== "running" );

	if ( ! shouldShow ) {
		return null;
	}

	// Return the shutdown modal overlay
	return (
		<div
			role="dialog"
			aria-modal="true"
			aria-labelledby="shutdown-title"
			className="fixed inset-0 z-50 flex items-center justify-center bg-navy-900/60 backdrop-blur-sm"
		>
			<div className="mx-4 flex max-w-sm flex-col items-center gap-4 rounded-lg bg-white px-8 py-7 text-center shadow-xl">
				<div
					aria-hidden
					className="h-10 w-10 animate-spin rounded-full border-2 border-slate-200 border-t-navy-700"
				/>
				<div>
					<h2
						id="shutdown-title"
						className="text-base font-semibold text-navy-900"
					>
						The server is shutting down
					</h2>

					<p className="mt-1 text-sm text-navy-600">
						The 30-minute demo session has ended. You will be returned to the
						launcher shortly.
					</p>
				</div>
			</div>
		</div>
	);
}
