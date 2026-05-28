import { useQuery } from "@tanstack/react-query";

// The base URL for the launcher API to get the timer information from.
const LAUNCHER_API_URL = (
	import.meta.env.VITE_LAUNCHER_API_URL as string | undefined
)?.replace( /\/$/, "" );

// A data-object interface representing the expected response structure from the launcher status API.
interface LauncherStatus {
	instance_state: string;
	stop_scheduled_at: string | null;
}

/**
 * Fetches the current status of the launcher, including whether a session stop is scheduled and when.
 * 
 * @param {string} baseUrl The base URL of the launcher API to fetch the status from.
 * 
 * @returns {Promise<LauncherStatus>} A promise that resolves to the launcher status data.
 */
async function fetchLauncherStatus(baseUrl: string): Promise<LauncherStatus> {
	const res = await fetch( `${ baseUrl }/status`, {
		method: "GET",
		headers: { Accept: "application/json" },
	} );

	if ( ! res.ok ) {
		throw new Error( `launcher status failed (${ res.status })` );
	}

	return res.json();
}

// An interface representing the state of the session timer, specifically the scheduled stop time if applicable.
export interface SessionTimerState {
	stopAt: Date | null;
}

/**
 * A custom React hook that retrieves the session timer information from the
 * launcher API and returns the scheduled stop time if a session is active.
 * 
 * @returns {SessionTimerState} An object containing the stopAt Date if a session is active, or null otherwise.
 */
export function useSessionTimer(): SessionTimerState {
	const enabled = Boolean( LAUNCHER_API_URL );

	// Use React Query to fetch the launcher status, polling every 60 seconds with a stale time of 30 seconds.
	const { data } = useQuery( {
		queryKey: [ "launcher", "status" ],
		queryFn: () => fetchLauncherStatus( LAUNCHER_API_URL as string ),
		enabled,
		refetchInterval: 60_000,
		staleTime: 30_000,
	} );

	if ( ! data || ! data.stop_scheduled_at ) {
		return { stopAt: null };
	}

	const isRunning = data.instance_state === "running";
	const isPending = data.instance_state === "pending";

	if ( ! isRunning && ! isPending ) {
		return { stopAt: null };
	}

	const parsed = new Date( data.stop_scheduled_at );

	if ( Number.isNaN( parsed.getTime() ) ) {
		return { stopAt: null };
	}

	return { stopAt: parsed };
}
