"use client";
import toast from 'react-hot-toast';
import { resolveErrorMessage } from './apiError';

/**
 * Show a caught service error as a toast.
 *
 * Use this instead of `toast.error('Failed to X. Please try again.')`. The
 * hardcoded form discarded whatever the backend said, so a 400 explaining that
 * a case was already exported rendered as an invitation to retry something
 * that could never succeed.
 *
 * `options` is forwarded to react-hot-toast, so callers keep their `{ id }`
 * de-duplication for replacing a loading toast.
 */
export function toastError(error, fallback, options) {
    return toast.error(resolveErrorMessage(error, fallback), options);
}
