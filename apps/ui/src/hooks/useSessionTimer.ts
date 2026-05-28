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

// An interface representing the state of the session timer: the scheduled stop time and the latest EC2 instance state.
export interface SessionTimerState {
	stopAt: Date | null;
	instanceState: string | null;
}

/**
 * A custom React hook that retrieves the session timer information from the
 * launcher API. Polls slowly during a normal session and ramps up to a 3s
 * cadence once the scheduled stop time has passed or shutdown begins, so the
 * UI can react quickly to the running -> stopping -> stopped transition.
 *
 * @returns {SessionTimerState} The scheduled stop Date (if any) and the latest instance_state from the launcher.
 */
export function useSessionTimer(): SessionTimerState {
	const enabled = Boolean( LAUNCHER_API_URL );

	const { data } = useQuery( {
		queryKey: [ "launcher", "status" ],
		queryFn: () => fetchLauncherStatus( LAUNCHER_API_URL as string ),
		enabled,
		refetchInterval: ( query ) => {
			const current = query.state.data;

			if ( ! current ) {
				return 60_000;
			}

			// Once the instance is fully stopped, there is nothing more to poll for.
			if ( current.instance_state === "stopped" ) {
				return false;
			}

			// Shutdown in progress — poll fast so the modal/redirect fires promptly.
			if ( current.instance_state === "stopping" ) {
				return 3_000;
			}

			// Past the scheduled stop but state hasn't transitioned yet — fast-poll to catch the change.
			if ( current.stop_scheduled_at ) {
				const ts = new Date( current.stop_scheduled_at ).getTime();

				if ( ! Number.isNaN( ts ) && Date.now() >= ts ) {
					return 3_000;
				}
			}

			return 60_000;
		},
		staleTime: 30_000,
	} );

	if ( ! data ) {
		return { stopAt: null, instanceState: null };
	}

	const instanceState = data.instance_state ?? null;

	if ( ! data.stop_scheduled_at ) {
		return { stopAt: null, instanceState };
	}

	const parsed = new Date( data.stop_scheduled_at );

	if ( Number.isNaN( parsed.getTime() ) ) {
		return { stopAt: null, instanceState };
	}

	return { stopAt: parsed, instanceState };
}
