package com.backendjava.engine;

import com.backendjava.task.ReviewTask;
import com.backendjava.task.ReviewTaskStatus;
import java.time.Duration;
import java.util.Map;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;

@Component
public class MockAiEngineAdapter implements AiEngineAdapter {
    @Override
    public Flux<EngineEvent> startReview(ReviewTask task) {
        return Flux.just(
                        new EngineEvent(
                                "analysis_started",
                                "analysis started",
                                ReviewTaskStatus.RUNNING,
                                Map.of()),
                        new EngineEvent(
                                "analysis_completed",
                                "analysis completed",
                                ReviewTaskStatus.RUNNING,
                                Map.of("issuesCount", 0)),
                        new EngineEvent(
                                "review_completed",
                                "review completed",
                                ReviewTaskStatus.COMPLETED,
                                Map.of("summary", "mock pipeline completed")))
                .delayElements(Duration.ofMillis(800));
    }
}
