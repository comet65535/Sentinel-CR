package com.backendjava.engine;

import com.backendjava.task.ReviewTask;
import com.backendjava.task.ReviewTaskStatus;
import java.time.Duration;
import java.util.Map;
import reactor.core.publisher.Flux;

public class MockAiEngineAdapter implements AiEngineAdapter {
    @Override
    public Flux<EngineEvent> startReview(ReviewTask task) {
        return Flux.just(
                        new EngineEvent(
                                "analysis_started",
                                "analysis started",
                                ReviewTaskStatus.RUNNING,
                                Map.of("source", "mock-engine")),
                        new EngineEvent(
                                "analysis_completed",
                                "analysis completed",
                                ReviewTaskStatus.RUNNING,
                                Map.of("source", "mock-engine", "issuesCount", 0)),
                        new EngineEvent(
                                "review_completed",
                                "review completed",
                                ReviewTaskStatus.COMPLETED,
                                Map.of(
                                        "source",
                                        "mock-engine",
                                        "result",
                                        Map.of("summary", "mock pipeline completed", "engine", "mock"))))
                .delayElements(Duration.ofMillis(800));
    }
}
