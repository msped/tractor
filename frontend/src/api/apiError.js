/**
 * Extracts a human-readable message from an Axios error response.
 * Checks Django REST framework field names in priority order:
 *   detail → non_field_errors[0] → name[0] → error → fallback
 */
export function extractApiError(error, fallback) {
    return (
        error.response?.data?.detail
        || error.response?.data?.non_field_errors?.[0]
        || error.response?.data?.name?.[0]
        || error.response?.data?.error
        || fallback
    );
}

export function throwApiError(error, fallback) {
    const err = new Error(extractApiError(error, fallback));
    err.status = error.response?.status;
    throw err;
}
