import React, { useState } from 'react';
import { Popover, Box, Select, MenuItem, Button, FormControl, InputLabel } from '@mui/material';

export const ManualRedactionPopover = ({ anchorEl, onClose, onRedact }) => {
    const [redactionType, setRedactionType] = useState('PII');

    const handleRedact = () => {
        onRedact(redactionType);
    };

    return (
        <Popover
            open={Boolean(anchorEl)}
            anchorEl={anchorEl}
            onClose={onClose}
            anchorOrigin={{
                vertical: 'bottom',
                horizontal: 'left',
            }}
            transformOrigin={{
                vertical: 'top',
                horizontal: 'left',
            }}
        >
            <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2, width: 400 }}>
                <FormControl fullWidth size="small">
                    <InputLabel>Redaction Type</InputLabel>
                    <Select value={redactionType} label="Redaction Type" onChange={(e) => setRedactionType(e.target.value)}>
                        <MenuItem value="PII">Third-Party PII</MenuItem>
                        <MenuItem value="OP_DATA">Operational Data</MenuItem>
                        <MenuItem value="DS_INFO">Data Subject Information</MenuItem>
                    </Select>
                </FormControl>
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
                    <Button onClick={onClose} size="small">Cancel</Button>
                    <Button onClick={handleRedact} variant="contained" size="small">Redact</Button>
                </Box>
            </Box>
        </Popover>
    );
}