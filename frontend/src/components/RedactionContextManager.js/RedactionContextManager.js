import React, { useState } from 'react';
import {
  Box,
  Button,
  TextField,
  CircularProgress,
  Alert,
  IconButton,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import { useSession } from 'next-auth/react';
import { toast } from 'react-hot-toast';
import { updateRedactionContext, deleteRedactionContext } from '@/services/redactionService';


export const RedactionContextManager = ({ redactionId, context, isEditing, onCancel, onContextSave }) => {
  const { data: session } = useSession();
  const [contextText, setContextText] = useState(context?.text || '');
  const [initialText, setInitialText] = useState(context?.text || '');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSave = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const updatedContext = await updateRedactionContext(
        redactionId,
        { text: contextText },
        session?.access_token
      );
      setInitialText(contextText);
      toast.success('Context saved successfully.');
      onContextSave(redactionId, updatedContext.text);
      onCancel();
    } catch (err) {
      setError('Failed to save context.');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteContext = () => {
    setIsLoading(true);
    setError(null);
    deleteRedactionContext(redactionId, session?.access_token)
      .then(() => {
        setContextText('');
        setInitialText('');
        toast.success('Context deleted successfully.');
        onContextSave(redactionId, null);
        onCancel();
      })
      .catch((err) => {
        setError('Failed to delete context.');
        console.error(err);
      })
      .finally(() => {
        setIsLoading(false);
      });
  };


  const handleCancel = () => {
    setContextText(initialText);
    onCancel();
  };

  if (isLoading) {
    return <CircularProgress size={24} />;
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  if (!isEditing) {
    return null;
  }

  return (
    <Box sx={{ p: 2, borderTop: '1px solid', borderColor: 'divider' }}>
      <TextField
        fullWidth
        multiline
        rows={3}
        label="Context for Disclosure"
        name="Context for Disclosure"
        value={contextText}
        onChange={(e) => setContextText(e.target.value)}
        helperText="This text will replace the redaction in the final export."
        variant="outlined"
      />
      <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
        <Button variant="contained" color="success" size='small' onClick={handleSave} disabled={isLoading}>
          Save
        </Button>
        <Button onClick={handleCancel} variant="contained" color="error" size='small' disabled={isLoading}>Cancel</Button>
        <IconButton onClick={handleDeleteContext} sx={{ ml: 'auto' }} variant="contained" color="error" size='small' disabled={isLoading || !contextText}>
          <DeleteIcon />
        </IconButton>
      </Box>
    </Box>
  );
}
