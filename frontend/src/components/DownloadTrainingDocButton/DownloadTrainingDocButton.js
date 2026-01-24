"use client";
import React from "react";
import { IconButton, Tooltip } from "@mui/material";
import DownloadIcon from "@mui/icons-material/Download";

export const DownloadTrainingDocButton = ({ fileUrl, filename }) => {
    return (
        <Tooltip title="Download">
            <IconButton
                component="a"
                href={fileUrl}
                download={filename}
                size="small"
            >
                <DownloadIcon />
            </IconButton>
        </Tooltip>
    );
};
