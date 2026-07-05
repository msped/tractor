import apiClient from "@/api/apiClient";

function triggerAnchorDownload(href, filename) {
    const link = document.createElement("a");
    link.href = href;
    link.download = filename || "";
    document.body.appendChild(link);
    link.click();
    link.remove();
}

/**
 * Download a media file and save it via a temporary anchor element.
 *
 * Root-relative URLs (`/media/...`, local storage) are served by an
 * auth-protected backend view, so they are fetched as a blob through the
 * authenticated API client — a plain <a href> navigation carries no
 * Authorization header.
 *
 * Absolute URLs (S3/Azure presigned URLs when MEDIA_STORAGE is a cloud
 * backend) carry their own auth in the query string; routing them through
 * apiClient would attach the Django JWT, which cloud storage rejects (and
 * would leak the token to the storage host). Those download natively.
 */
export async function downloadFile(url, filename) {
    if (/^https?:\/\//i.test(url)) {
        triggerAnchorDownload(url, filename);
        return;
    }

    const response = await apiClient.get(url, {
        baseURL: process.env.NEXT_PUBLIC_API_HOST || "",
        responseType: "blob",
    });
    const blobUrl = window.URL.createObjectURL(response.data);
    triggerAnchorDownload(blobUrl, filename || url.split("/").pop() || "download");
    // Defer revocation: Safari/older Firefox can start reading the blob URL
    // after the click task, and a same-tick revoke silently cancels the
    // download.
    setTimeout(() => window.URL.revokeObjectURL(blobUrl), 1000);
}
