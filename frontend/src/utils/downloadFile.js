import apiClient from "@/api/apiClient";

/**
 * Download a media file through the authenticated API client and save it
 * via a temporary object URL. Media URLs are root-relative (`/media/...`)
 * and served by an auth-protected backend view, so a plain <a href>
 * navigation (which carries no Authorization header) cannot be used.
 */
export async function downloadFile(url, filename) {
    const response = await apiClient.get(url, {
        baseURL: process.env.NEXT_PUBLIC_API_HOST || "",
        responseType: "blob",
    });
    const blobUrl = window.URL.createObjectURL(response.data);
    const link = document.createElement("a");
    link.href = blobUrl;
    link.download = filename || url.split("/").pop() || "download";
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(blobUrl);
}
