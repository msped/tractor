import Link from "next/link";
import { Container, Typography, Grid, Card, CardContent, Button, Box } from "@mui/material";
import ScheduledTrainingCard from '@/components/ScheduledTrainingCard';
import TrainingRunList from '@/components/TrainingRunList';
import { getTrainingSchedules, getTrainingRuns } from '@/services/trainingService';
import ModelTrainingIcon from '@mui/icons-material/ModelTraining';

export default async function TrainingPage() {
    let schedule = null, runs = [], error = null;
    try {
        [schedule, runs] = await Promise.all([
            getTrainingSchedules(),
            getTrainingRuns()
        ]);
    } catch (e) {
        error = e.message;
    }


    return (
        <>
            <Typography variant="h4" fontWeight={600} align="center" component="h1" gutterBottom>
                Model Training
            </Typography>

            <Grid container spacing={4}>
                <Grid component={Card} size={{ xs: 12, md: 6 }}>
                    <CardContent>
                        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                            <ModelTrainingIcon color="action" sx={{ mr: 1 }} />
                            <Typography variant="h6" component="h2">Manual Training</Typography>
                        </Box>
                        <Typography variant="body2" color="text.secondary">
                            Train your model to improve its ability to detect and redact sensitive information. You can run training manually or set up an automated schedule.
                        </Typography>
                        <Button component={Link} href="/settings/training/manual" variant="text" sx={{ mt: 2 }}>
                            Go to Manual Training
                        </Button>
                    </CardContent>
                </Grid>
                <Grid component={Card} size={{ xs: 12, md: 6  }}>
                    <ScheduledTrainingCard schedule={schedule} />
                </Grid>
            </Grid>
            <TrainingRunList runs={runs} />
        </>
    );
}
