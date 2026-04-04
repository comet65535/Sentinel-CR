package com.backendjava.engine;

import com.backendjava.task.ReviewTask;
import com.backendjava.task.ReviewTaskStatus;
import java.time.Duration;
import java.util.Map;
import reactor.core.publisher.Flux;

public class MockAiEngineAdapter implements AiEngineAdapter {
    @Override
    public Flux<EngineEvent> startReview(ReviewTask task) {
        Map<String, Object> delivery = new java.util.LinkedHashMap<>();
        delivery.put(
                "unified_diff",
                String.join(
                        "\n",
                        "diff --git a/snippet.java b/snippet.java",
                        "--- a/snippet.java",
                        "+++ b/snippet.java",
                        "@@ -1,1 +1,1 @@",
                        "-class snippet { void run(){ int x = 1 } }",
                        "+class snippet { void run(){ int x = 1; } }"));
        delivery.put("verified_level", "L1");
        delivery.put(
                "verification_stages",
                java.util.List.of(
                        Map.of("stage", "patch_apply", "status", "passed"),
                        Map.of("stage", "compile", "status", "passed")));
        delivery.put("final_outcome", "verified_patch");
        delivery.put("failed_stage", null);
        delivery.put("failure_code", null);
        delivery.put("failure_reason", null);
        delivery.put("retryable", false);
        Map<String, Object> result = Map.of(
                "engine",
                "mock",
                "delivery",
                delivery,
                "summary",
                Map.of(
                        "verified_level",
                        "L1",
                        "final_outcome",
                        "verified_patch",
                        "user_message",
                        "Verified patch generated."),
                "patch",
                Map.of(
                        "status",
                        "generated",
                        "unified_diff",
                        delivery.get("unified_diff")),
                "verification",
                Map.of(
                        "status",
                        "passed",
                        "verified_level",
                        "L1",
                        "stages",
                        delivery.get("verification_stages")));
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
                                        result,
                                        "delivery",
                                        delivery)))
                .delayElements(Duration.ofMillis(800));
    }
}
