"use client";
import React from "react";
import { IconButton, Tooltip } from "@mui/material";
import DownloadIcon from "@mui/icons-material/Download";
import toast from "react-hot-toast";
import { downloadFile } from "@/utils/downloadFile";

export const DownloadTrainingDocButton = ({ fileUrl, filename }) => {
    const handleDownload = async () => {
        try {
            await downloadFile(fileUrl, filename);
        } catch (error) {
            toast.error("Failed to download the document.");
        }
    };

    return (
        <Tooltip title="Download">
            <IconButton onClick={handleDownload} size="small">
                <DownloadIcon />
            </IconButton>
        </Tooltip>
    );
};
