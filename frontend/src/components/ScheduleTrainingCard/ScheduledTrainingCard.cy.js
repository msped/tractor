import React from 'react';
import { ScheduledTrainingCard } from './ScheduledTrainingCard';
import * as trainingService from '@/services/trainingService';
import { Card } from '@mui/material';

const mountOpts = { mockSession: { access_token: 'fake-token', status: 'authenticated' } };

describe('<ScheduledTrainingCard />', () => {
    context('When no schedule exists', () => {
        beforeEach(() => {
            const createTrainingScheduleStub = cy.stub(
                trainingService, 'createTrainingSchedule'
            ).as('createTrainingScheduleStub').resolves();
            const deleteTrainingScheduleStub = cy.stub(
                trainingService, 'deleteTrainingSchedule'
            ).as('deleteTrainingScheduleStub').resolves();
            cy.fullMount(
                <Card>
                    <ScheduledTrainingCard
                        schedule={null}
                        createTrainingSchedule={createTrainingScheduleStub}
                        deleteTrainingSchedule={deleteTrainingScheduleStub}
                    />
                </Card>,
                mountOpts
            );
        });

        it('renders the "no schedule" state correctly', () => {
            cy.contains('Automated Training Schedule').should('be.visible');
            cy.contains('No automated training schedule is currently active.').should('be.visible');
            cy.get('button').contains('Schedule Training').should('be.visible');
        });

        it('opens the dialog to create a new schedule', () => {
            cy.get('button').contains('Schedule Training').click();
            cy.get('[role="dialog"]').should('be.visible');
            cy.contains('Create New Training Schedule').should('be.visible');
        });

        it('allows creating a new schedule and calls the service function', () => {
            cy.get('button').contains('Schedule Training').click();

            cy.get('[role="dialog"]').within(() => {
                cy.get('#frequency-select-label').parent().click();
            });

            cy.get('[role="listbox"]').contains('Monthly').click();

            cy.get('[role="dialog"]').within(() => {
                const newDateTime = '2025-01-01T10:30';
                cy.get('input[type="datetime-local"]').type(newDateTime);

                cy.get('button').contains('Create').click();
            });

            cy.get('@createTrainingScheduleStub').should('have.been.called')
            cy.get('@createTrainingScheduleStub').should('be.calledWithMatch', {
                func: 'training.tasks.train_model',
                kwargs: { source: 'redactions' },
                repeats: -1,
                schedule_type: 'M',
                next_run: new Date('2025-01-01T10:30').toISOString(),
            });

            // The dialog should close after the async operation completes.
            cy.get('[role="dialog"]').should('not.exist');
        });

        it('closes the dialog when Cancel is clicked', () => {
            cy.get('button').contains('Schedule Training').click();
            cy.get('[role="dialog"]').should('be.visible');
            cy.get('[role="dialog"]').find('button').contains('Cancel').click();
            cy.get('[role="dialog"]').should('not.exist');
        });
    });

    context('When a schedule exists', () => {
        const mockSchedule = {
            id: 123,
            next_run: '2024-12-25T09:00:00Z',
        };

        beforeEach(() => {
            const createTrainingScheduleStub = cy.stub(
                trainingService, 'createTrainingSchedule'
            ).as('createTrainingScheduleStub').resolves();
            const deleteTrainingScheduleStub = cy.stub(
                trainingService, 'deleteTrainingSchedule'
            ).as('deleteTrainingScheduleStub').resolves();
            cy.fullMount(
                <Card>
                    <ScheduledTrainingCard
                        schedule={mockSchedule}
                        createTrainingSchedule={createTrainingScheduleStub}
                        deleteTrainingSchedule={deleteTrainingScheduleStub}
                    />
                </Card>,
                mountOpts
            );
        });

        it('renders the schedule details correctly', () => {
            cy.contains('The model is scheduled to retrain automatically').should('be.visible');
            cy.contains('Next scheduled run:').should('be.visible');

            const expectedDateString = new Date(mockSchedule.next_run).toLocaleString();
            cy.get('.MuiChip-label').should('contain.text', expectedDateString);

            cy.get('button').contains('Schedule Training').should('not.exist');
        });

        it('calls the delete service when the delete button is clicked', () => {
            cy.get('[data-testid="DeleteIcon"]').click();

            cy.get('@deleteTrainingScheduleStub').should('have.been.calledOnceWith', mockSchedule.id);
        });
    });
});
