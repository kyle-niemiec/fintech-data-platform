const CONTROL_API_BASE = "__CONTROL_API_BASE__".replace(/\/$/, "");
const DEMO_HOST = "__DEMO_HOST__";

const startButton = document.getElementById("start-btn");
const statusNode = document.getElementById("status");
const windowNode = document.getElementById("window");

let pollHandle = null;

/**
 * Sets the status message displayed to the user. HTML is allowed so state
 * messages can highlight the key state keyword via .kw-* spans; non-state
 * strings are plain text and render identically.
 *
 * @param {string} message
 */
function setStatus( message ) {
	statusNode.innerHTML = message;
}

/**
 * Sets the auto-stop window message based on the provided ISO timestamp.
 *
 * @param {Date} stopAtIso
 */
function setWindow( stopAtIso ) {
	if ( ! stopAtIso ) {
		windowNode.textContent = "";
		return;
	}

	const stopAt = new Date( stopAtIso );

	if ( Number.isNaN( stopAt.getTime() ) ) {
		windowNode.textContent = "";
		return;
	}

	windowNode.textContent = `Auto-stop scheduled at ${stopAt.toLocaleTimeString()}`;
}

/**
 * Redirects the user to the demo host if the app is ready.
 *
 * @param {*} data 
 */
function maybeRedirect( data ) {
	if ( data.app_ready ) {
		window.location.replace( DEMO_HOST );
	}
}

/**
 * Renders the current status of the demo instance.
 *
 * @param {*} data 
 */
function renderState( data ) {
	const state = data.instance_state ?? "unknown";
	let status = `Instance state: ${ state }`;

	switch ( state ) {
		case "running":
			status = ! data.app_ready
				? 'Demo is <span class="kw-running">running</span>. Waiting for app health...'
				: status;
			break;
		case "pending":
			status = '<span class="kw-starting">Starting</span> demo instance. This can take a minute...';
			break;
		case "stopping":
			status = 'Demo is <span class="kw-stopping">stopping</span>. Refresh in a moment.';
			break;
		case "stopped":
			status = 'Demo is <span class="kw-offline">offline</span>. Click Start Demo.';
			break;
		default:
			break;
	}

	setStatus( status );
	setWindow( data.stop_scheduled_at );
	maybeRedirect( data );
}

/**
 * Fetches the status of the demo instance via the control API.
 *
 * @returns {string} The JSON response containing the instance status and related information.
 */
async function fetchStatus() {
	const res = await fetch( `${ CONTROL_API_BASE }/status`, {
		method: "GET",
		headers: { Accept: "application/json" },
	} );

	if ( ! res.ok ) {
		throw new Error( `status request failed (${ res.status })` );
	}

	return res.json();
}

/**
 * Polls the status of the demo instance and updates the UI accordingly.
 */
async function pollStatus() {
	try {
		const status = await fetchStatus();
		renderState( status );
	} catch ( error ) {
		setStatus( "Status check failed. Try again." );
		windowNode.textContent = "";
		console.error( error );
	}
}

/**
 * Starts the demo instance.
 */
async function startDemo() {
	startButton.disabled = true;
	setStatus( "Submitting start request..." );

	// Attempt to start the instance via the control API and update the UI based on the response.
	try {
		const res = await fetch( `${CONTROL_API_BASE}/start`, {
			method: "POST",
			headers: { Accept: "application/json" },
		} );

		if ( ! res.ok ) {
			throw new Error( `start request failed (${res.status})` );
		}

		const payload = await res.json();
		renderState( payload );
	} catch ( error ) {
		setStatus( "Start request failed. Try again." );
		windowNode.textContent = "";
		console.error( error );
	} finally {
		startButton.disabled = false;
	}
}

// Attach event listener to the start button to initiate the demo start process when clicked.
startButton.addEventListener( "click", startDemo );

// Grab the initial status of the instance immediately and then start polling at regular intervals.
pollStatus();
pollHandle = window.setInterval( pollStatus, 5000 );

window.addEventListener( "beforeunload", () => {
	if ( pollHandle !== null ) {
		window.clearInterval( pollHandle );
	}
} );
