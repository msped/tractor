/**
 * Pulls the server's own explanation out of an Axios error, in DRF field
 * priority order: detail → non_field_errors[0] → name[0] → error.
 *
 * Returns null when the response carried no usable message — a network failure,
 * a timeout, or an HTML error page from nginx rather than a JSON body from
 * Django. That null is the signal callers need: it means nobody has actually
 * explained what went wrong, so the caller's own fallback is all there is.
 */
export function extractServerMessage(error) {
    const data = error.response?.data;
    const message =
        data?.detail
        || data?.non_field_errors?.[0]
        || data?.name?.[0]
        || data?.error;
    return typeof message === 'string' && message ? message : null;
}

/**
 * Extracts a human-readable message from an Axios error response, falling back
 * to `fallback` when the server said nothing usable.
 */
export function extractApiError(error, fallback) {
    return extractServerMessage(error) ?? fallback;
}

export function throwApiError(error, fallback) {
    const serverMessage = extractServerMessage(error);
    const err = new Error(serverMessage ?? fallback);
    err.status = error.response?.status;
    // Records whether `message` is the server's words or just our fallback.
    // Without this the two are indistinguishable downstream, and the UI cannot
    // tell "the backend explained why" from "we guessed".
    err.isServerMessage = serverMessage !== null;
    throw err;
}

/**
 * Decides what a caught service error should say to the user.
 *
 * The useful question is not which status class it was, but whether anyone
 * actually explained the failure:
 *
 *   - The server sent a message → show it. A 400 says the case is already
 *     exported; a 500 from our exception handler carries the reference the user
 *     should quote. Replacing either with "please try again" destroys the only
 *     actionable information available, and invites a retry that cannot work.
 *   - The server sent nothing (network down, timeout, nginx HTML) → show the
 *     caller's fallback, because there is nothing better to say.
 *
 * Anything that is not a clean 4xx is also written to the console, so a failure
 * a user reports can be recovered from their browser session.
 *
 * Returns the message rather than displaying it, so inline Alerts and form
 * error state get the same treatment as toasts.
 */
export function resolveErrorMessage(error, fallback) {
    const status = error?.status ?? error?.response?.status;
    const isHandledClientError = status >= 400 && status < 500;

    if (!isHandledClientError) {
        console.error(fallback, error);
    }

    if (error?.isServerMessage && error.message) {
        return error.message;
    }

    return fallback;
}
