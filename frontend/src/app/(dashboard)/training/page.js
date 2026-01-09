import Link from "next/link";
import { Typography, Grid, Card, CardContent, Button, Box, Container } from "@mui/material";
import { ScheduledTrainingCard } from '@/components/ScheduleTrainingCard';
import { TrainingRunList } from '@/components/TrainingRunList';
import { getTrainingSchedules, getTrainingRuns } from '@/services/trainingService';
import { auth } from "@/auth";
import ModelTrainingIcon from '@mui/icons-material/ModelTraining';

export default async function TrainingPage() {
    const session = await auth();
    let schedule = null, runs = [], error = null;
    try {
        [schedule, runs] = await Promise.all([
            getTrainingSchedules(session?.access_token),
            getTrainingRuns(session?.access_token)
        ]);
    } catch (e) {
        error = e.message;
    }


    return (
        <Container>
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
                        <Button component={Link} href="/training/manual" variant="text" sx={{ mt: 2 }}>
                            Go to Manual Training
                        </Button>
                    </CardContent>
                </Grid>
                <Grid component={Card} size={{ xs: 12, md: 6  }}>
                    <ScheduledTrainingCard schedule={schedule} />
                </Grid>
                <Grid component={Card} size={{ xs: 12}}>
                    <CardContent>
                        <Typography variant="h5" component="h3">
                            How to provide manual training data
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                            To provide manual training data, navigate to the Manual Training section 
                            where you can upload documents labelled documents.
                            This helps improve the models accuracy in detecting and redacting 
                            data.
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                            The only supported files for training are docx files. The document must
                            be highlighted using turquoise for operation data and bright green 
                            for Third Party information.
                        </Typography>
                    </CardContent>
                </Grid>
            </Grid>
            <TrainingRunList runs={runs} />
        </Container>
    );
}
