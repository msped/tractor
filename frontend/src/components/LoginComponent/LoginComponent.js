"use client";
import React, { useState } from "react";
import { Box, Button, TextField, Typography, Paper, Divider } from "@mui/material";
import { authClient } from "@/lib/auth-client";
import { useRouter } from "next/navigation";

export const LoginComponent = ({ sessionError, socialProviders = [] }) => {
    const router = useRouter();
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState(
        sessionError === "SessionExpired" ? "Your session has expired, please log in again." : ""
    );
    const [loading, setLoading] = useState(false);

    const handleLogin = async (e) => {
        e.preventDefault();
        setError("");
        setLoading(true);
        const result = await authClient.signIn.username({ username, password });
        if (result.error) {
            setError("Login failed. Please check your credentials.");
            setLoading(false);
        } else {
            authClient.$store.notify("$sessionSignal");
            router.push("/cases");
        }
    };

    return (
        <Box
            sx={{
                minHeight: "100dvh",
                bgcolor: "background.default",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
            }}
        >
            <Paper elevation={3} sx={{ p: 4, minWidth: 320 }}>
                <Box sx={{ textAlign: "center", mb: 3 }}>
                    <Typography variant="h4" component="h1" gutterBottom>
                        Tractor
                    </Typography>
                    <Typography variant="body1" gutterBottom>
                        Please log in to continue.
                    </Typography>
                </Box>
                <form onSubmit={handleLogin}>
                    <TextField
                        label="Username"
                        name="username"
                        autoComplete="username"
                        value={username}
                        onChange={e => setUsername(e.target.value)}
                        fullWidth
                        margin="normal"
                        required
                    />
                    <TextField
                        label="Password"
                        name="password"
                        type="password"
                        autoComplete="current-password"
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
                        loading={loading}
                        sx={{ mt: 2 }}
                    >
                        Sign in
                    </Button>
                    {socialProviders.length > 0 && (
                        <>
                            <Divider sx={{ my: 2 }}>OR</Divider>
                            {socialProviders.map((provider) => (
                                <Button
                                    key={provider.id}
                                    variant="outlined"
                                    fullWidth
                                    onClick={() => authClient.signIn.oauth2({
                                        providerId: provider.id,
                                        callbackURL: "/cases",
                                    })}
                                    sx={{ mt: 1 }}
                                >
                                    Sign in with {provider.name}
                                </Button>
                            ))}
                        </>
                    )}
                </form>
            </Paper>
        </Box>
    );
};
