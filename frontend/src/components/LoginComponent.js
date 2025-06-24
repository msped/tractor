"use client";
import * as React from "react";
import { signIn } from "next-auth/react"
import { Box, Button, TextField, Typography, Paper } from "@mui/material";

export default function LoginComponent() {
    const [username, setUsername] = React.useState("");
    const [password, setPassword] = React.useState("");
    const [error, setError] = React.useState("");

    const handleLogin = async (e) => {
        e.preventDefault();
        setError("");
        const result = await signIn("credentials", {
            username,
            password,
            redirect: true,
            callbackUrl: "/cases"
        });
        if (result && result.error) {
            setError("Login failed. Please check your credentials.");
        }
    };

    return (
        <Box
            sx={{
                minHeight: "100vh",
                bgcolor: "background.default",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
            }}
        >
            <Paper elevation={3} sx={{ p: 4, minWidth: 320 }}>
                <Box sx={{ textAlign: "center", mb: 3 }}>
                    <Typography variant="h4" component="h1" gutterBottom>
                        Welcome to Redactor
                    </Typography>
                    <Typography variant="body1" gutterBottom>
                        Please log in to continue.
                    </Typography>
                </Box>
                <form onSubmit={handleLogin}>
                    <TextField
                        label="Username"
                        value={username}
                        onChange={e => setUsername(e.target.value)}
                        fullWidth
                        margin="normal"
                        required
                    />
                    <TextField
                        label="Password"
                        type="password"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        fullWidth
                        margin="normal"
                        required
                    />
                    {error && (
                        <Typography color="error" variant="body2" sx={{ mt: 1 }}>
                            {error}
                        </Typography>
                    )}
                    <Button
                        type="submit"
                        variant="contained"
                        color="primary"
                        fullWidth
                        sx={{ mt: 2 }}
                    >
                        Login
                    </Button>
                </form>
            </Paper>
        </Box>
    );
}