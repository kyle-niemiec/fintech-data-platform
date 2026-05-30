const CONTROL_API_BASE = "__CONTROL_API_BASE__".replace(/\/$/, "");
const DEMO_HOST = "__DEMO_HOST__";

const startButton = document.getElementById("start-btn");
const statusNode = document.getElementById("status");
const statusLabel = statusNode.querySelector(".status-label");
const windowNode = document.getElementById("window");
const menuToggle = document.getElementById("menu-toggle");
const menuPanel = document.getElementById("menu-panel");
const yearNode = document.getElementById("year");

let pollHandle = null;

/**
 * Sets the status pill state and label. The pill's data-state drives its colour
 * and the animated dot via CSS; the label is plain text.
 *
 * @param {string} variant One of: stopped, pending, running, stopping, error, unknown.
 * @param {string} label
 */
function setStatus( variant, label ) {
	statusNode.dataset.state = variant;
	statusLabel.textContent = label;
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
 * Renders the current status of the demo instance into the status pill.
 *
 * @param {*} data
 */
function renderState( data ) {
	const state = data.instance_state ?? "unknown";
	let variant = "unknown";
	let label = `Instance state: ${ state }`;

	switch ( state ) {
		case "running":
			variant = "running";
			label = data.app_ready
				? "Ready - opening demo..."
				: "Running - waiting for app...";
			break;
		case "pending":
			variant = "pending";
			label = "Starting - this can take a minute...";
			break;
		case "stopping":
			variant = "stopping";
			label = "Stopping - refresh in a moment.";
			break;
		case "stopped":
			variant = "stopped";
			label = "Offline - click Start Demo.";
			break;
		default:
			break;
	}

	setStatus( variant, label );
	setWindow( data.stop_scheduled_at );
	// Only allow starting from a fully stopped state; any other state means a start is in flight or unnecessary.
	startButton.disabled = state !== "stopped";
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
		setStatus( "error", "Status check failed. Try again." );
		windowNode.textContent = "";
		console.error( error );
	}
}

/**
 * Starts the demo instance.
 */
async function startDemo() {
	startButton.disabled = true;
	setStatus( "pending", "Submitting start request..." );

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
		setStatus( "error", "Start request failed. Try again." );
		windowNode.textContent = "";
		// Re-enable so the user can retry; on success, renderState owns the disabled state.
		startButton.disabled = false;
		console.error( error );
	}
}

/**
 * Opens or closes the header menu and keeps the toggle's aria-expanded in sync.
 *
 * @param {boolean} open
 */
function setMenuOpen( open ) {
	menuToggle.setAttribute( "aria-expanded", String( open ) );
	menuPanel.hidden = ! open;
}

// Toggle the menu on click; close it on outside-click or Escape.
menuToggle.addEventListener( "click", () => {
	setMenuOpen( menuPanel.hidden );
} );

// Close the menu if the user clicks outside the menu panel or the toggle button.
document.addEventListener( "click", ( event ) => {
	if ( menuPanel.hidden ) {
		return;
	}

	if ( ! menuPanel.contains( event.target ) && ! menuToggle.contains( event.target ) ) {
		setMenuOpen( false );
	}
} );

// Close the menu if the user presses Escape while it's open.
document.addEventListener( "keydown", ( event ) => {
	if ( event.key === "Escape" && ! menuPanel.hidden ) {
		setMenuOpen( false );
		menuToggle.focus();
	}
} );

// Show the current year in the footer.
yearNode.textContent = String( new Date().getFullYear() );

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
