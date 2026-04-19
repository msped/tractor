// ***********************************************
// This example commands.js shows you how to
// create various custom commands and overwrite
// existing commands.
//
// For more comprehensive examples of custom
// commands please read more here:
// https://on.cypress.io/custom-commands
// ***********************************************
//
//
// -- This is a parent command --
// Cypress.Commands.add('login', (email, password) => { ... })
//
//
// -- This is a child command --
// Cypress.Commands.add('drag', { prevSubject: 'element'}, (subject, options) => { ... })
//
//
// -- This is a dual command --
// Cypress.Commands.add('dismiss', { prevSubject: 'optional'}, (subject, options) => { ... })
//
//
// -- This will overwrite an existing command --
// Cypress.Commands.overwrite('visit', (originalFn, url, options) => { ... })
import React from 'react';
import { mount } from 'cypress/react'
import { AppRouterCacheProvider } from '@mui/material-nextjs/v15-appRouter';
import { AppRouterContext } from 'next/dist/shared/lib/app-router-context.shared-runtime'
import { ThemeProvider } from '@mui/material/styles';
import GlobalStyles from '@mui/material/GlobalStyles';
import { SWRConfig } from 'swr';
import { Toaster } from 'react-hot-toast';
import theme from '@/theme';
import { SessionProvider } from 'next-auth/react';

const noAnimations = (
    <GlobalStyles styles={{ '*, *::before, *::after': { transitionDuration: '1ms !important', animationDuration: '1ms !important' } }} />
);

Cypress.Commands.add('fullMount', (component, options = {}) => {
    const { mockSession } = options;
    const router = {
        route: '/',
        pathname: '/',
        query: {},
        asPath: '/',
        basePath: '',
        refresh: cy.stub().as('router:refresh'),
        back: cy.stub().as('router:back'),
        forward: cy.stub().as('router:forward'),
        push: cy.stub().as('router:push'),
        reload: cy.stub().as('router:reload'),
        replace: cy.stub().as('router:replace'),
        isReady: true,
        ...(options.router || {}),
    };

    return mount(
        <SWRConfig value={{ dedupingInterval: 0, provider: () => new Map() }}>
        <SessionProvider session={mockSession}>
        <AppRouterCacheProvider>
            <ThemeProvider theme={theme}>
                {noAnimations}
                <AppRouterContext.Provider value={router}>
                    {component}
                    <Toaster />
                </AppRouterContext.Provider>
            </ThemeProvider>
        </AppRouterCacheProvider>
        </SessionProvider>
        </SWRConfig>,
        options
    );
});

Cypress.Commands.add('mount', (component, options) => {
    return mount(
    <AppRouterCacheProvider>
        <ThemeProvider theme={theme}>
            {noAnimations}
            {component}
            <Toaster />
        </ThemeProvider>
    </AppRouterCacheProvider>, options);
})