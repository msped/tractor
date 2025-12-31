import React from 'react';
import { PathnameContext } from 'next/dist/shared/lib/hooks-client-context.shared-runtime';
import { NavSidebar } from './NavSidebar';
import { SidebarProvider, SIDEBAR_WIDTH_EXPANDED, SIDEBAR_WIDTH_COLLAPSED } from '@/contexts/SidebarContext';

const mountOpts = { mockSession: { access_token: 'fake-token', status: 'authenticated' } };

const mountNavSidebar = (pathname = '/cases') => {
    return cy.fullMount(
        <PathnameContext.Provider value={pathname}>
            <SidebarProvider>
                <NavSidebar />
            </SidebarProvider>
        </PathnameContext.Provider>,
        mountOpts
    );
};

describe('<NavSidebar />', () => {
    context('Initial Render', () => {
        beforeEach(() => {
            mountNavSidebar('/cases');
        });

        it('renders the sidebar with correct width when expanded', () => {
            cy.get('nav').should('have.css', 'width', `${SIDEBAR_WIDTH_EXPANDED}px`);
        });

        it('renders the logo/brand name with link to cases', () => {
            cy.contains('a', 'Tractor')
                .should('be.visible')
                .and('have.attr', 'href', '/cases');
        });

        it('renders the collapse toggle button', () => {
            cy.get('[data-testid="ChevronLeftIcon"]').should('be.visible');
        });

        it('renders the "New Case" button with correct link', () => {
            cy.contains('New Case')
                .closest('a')
                .should('have.attr', 'href', '/cases/new');
        });

        it('renders all navigation items', () => {
            cy.contains('Cases').should('be.visible');
            cy.contains('Training').should('be.visible');
        });

        it('renders the Settings link', () => {
            cy.contains('Settings')
                .closest('a')
                .should('have.attr', 'href', '/settings');
        });
    });

    context('Navigation Links', () => {
        it('highlights Cases nav item when on /cases path', () => {
            mountNavSidebar('/cases');
            cy.contains('Cases')
                .closest('.MuiListItemButton-root')
                .should('have.class', 'Mui-selected');
        });

        it('highlights Cases nav item when on nested /cases/* path', () => {
            mountNavSidebar('/cases/123');
            cy.contains('Cases')
                .closest('.MuiListItemButton-root')
                .should('have.class', 'Mui-selected');
        });

        it('highlights Training nav item when on /training path', () => {
            mountNavSidebar('/training');
            cy.contains('Training')
                .closest('.MuiListItemButton-root')
                .should('have.class', 'Mui-selected');
        });

        it('highlights Settings when on /settings path', () => {
            mountNavSidebar('/settings');
            cy.contains('Settings')
                .closest('.MuiListItemButton-root')
                .should('have.class', 'Mui-selected');
        });

        it('nav items have correct href attributes', () => {
            mountNavSidebar('/cases');
            cy.contains('Cases').closest('a').should('have.attr', 'href', '/cases');
            cy.contains('Training').closest('a').should('have.attr', 'href', '/training');
        });
    });

    context('Collapse/Expand Functionality', () => {
        beforeEach(() => {
            mountNavSidebar('/cases');
        });

        it('collapses the sidebar when toggle button is clicked', () => {
            cy.get('[data-testid="ChevronLeftIcon"]').parent('button').click();

            cy.get('nav').should('have.css', 'width', `${SIDEBAR_WIDTH_COLLAPSED}px`);
        });

        it('hides the logo text when collapsed', () => {
            cy.get('[data-testid="ChevronLeftIcon"]').parent('button').click();

            cy.contains('Tractor').should('not.exist');
        });

        it('hides nav item text labels when collapsed', () => {
            cy.get('[data-testid="ChevronLeftIcon"]').parent('button').click();

            cy.get('nav').within(() => {
                cy.contains('Cases').should('not.exist');
                cy.contains('Training').should('not.exist');
                cy.contains('New Case').should('not.exist');
                cy.contains('Settings').should('not.exist');
            });
        });

        it('shows ChevronRightIcon when collapsed', () => {
            cy.get('[data-testid="ChevronLeftIcon"]').parent('button').click();

            cy.get('[data-testid="ChevronRightIcon"]').should('be.visible');
            cy.get('[data-testid="ChevronLeftIcon"]').should('not.exist');
        });

        it('expands the sidebar when toggle is clicked again', () => {
            // Collapse
            cy.get('[data-testid="ChevronLeftIcon"]').parent('button').click();
            cy.get('nav').should('have.css', 'width', `${SIDEBAR_WIDTH_COLLAPSED}px`);

            // Expand
            cy.get('[data-testid="ChevronRightIcon"]').parent('button').click();
            cy.get('nav').should('have.css', 'width', `${SIDEBAR_WIDTH_EXPANDED}px`);
        });

        it('shows logo text again after expanding', () => {
            // Collapse
            cy.get('[data-testid="ChevronLeftIcon"]').parent('button').click();
            cy.contains('Tractor').should('not.exist');

            // Expand
            cy.get('[data-testid="ChevronRightIcon"]').parent('button').click();
            cy.contains('Tractor').should('be.visible');
        });
    });

    context('Icons', () => {
        beforeEach(() => {
            mountNavSidebar('/cases');
        });

        it('displays correct icons for each nav item', () => {
            cy.get('[data-testid="FolderIcon"]').should('be.visible');
            cy.get('[data-testid="PsychologyIcon"]').should('be.visible');
            cy.get('[data-testid="AddIcon"]').should('be.visible');
            cy.get('[data-testid="SettingsIcon"]').should('be.visible');
        });

        it('icons remain visible when sidebar is collapsed', () => {
            cy.get('[data-testid="ChevronLeftIcon"]').parent('button').click();

            cy.get('[data-testid="FolderIcon"]').should('be.visible');
            cy.get('[data-testid="PsychologyIcon"]').should('be.visible');
            cy.get('[data-testid="AddIcon"]').should('be.visible');
            cy.get('[data-testid="SettingsIcon"]').should('be.visible');
        });
    });

    context('Styling and Layout', () => {
        beforeEach(() => {
            mountNavSidebar('/cases');
        });

        it('sidebar is fixed positioned on the left', () => {
            cy.get('nav')
                .should('have.css', 'position', 'fixed')
                .and('have.css', 'left', '0px')
                .and('have.css', 'top', '0px');
        });

        it('sidebar takes full viewport height', () => {
            cy.window().then((win) => {
                cy.get('nav').should('have.css', 'height', `${win.innerHeight}px`);
            });
        });

        it('New Case button has secondary color styling', () => {
            cy.contains('New Case')
                .closest('.MuiListItemButton-root')
                .should('have.css', 'background-color')
                .and('not.equal', 'rgba(0, 0, 0, 0)');
        });
    });
});
