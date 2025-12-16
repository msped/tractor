"use client";
import React, { useState, useEffect } from "react";
import { signIn as RealSignIn, getProviders } from "next-auth/react"
import { Box, Button, TextField, Typography, Paper, Divider } from "@mui/material";

export const LoginComponent = ({ signIn = RealSignIn }) => {
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [providers, setProviders] = useState(null);

    useEffect(() => {
        const fetchProviders = async () => {
            const res = await getProviders();
            console.log(res);
            setProviders(res);
        };
        fetchProviders();
    }, []);

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

    const otherProviders = providers
        ? Object.values(providers).filter((provider) => provider.id !== "credentials")
        : [];

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
                    {otherProviders.length > 0 && (
                        <>
                            <Divider sx={{ my: 2 }}>OR</Divider>
                            {otherProviders.map((provider) => (
                                <Button
                                    key={provider.id}
                                    variant="outlined"
                                    fullWidth
                                    onClick={() => signIn(provider.id, { callbackUrl: "/cases" })}
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