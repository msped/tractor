import React from 'react';
import { Footer } from '@/components/Footer';

describe('<Footer />', () => {
  it('renders the copyright notice with the current year', () => {
    cy.mount(<Footer />);

    const currentYear = new Date().getFullYear();
    cy.get('footer').contains(`© ${currentYear} Subject Access Manager (SAM). All rights reserved.`);
  });
});