package com.backendjava.engine;

import com.backendjava.task.ReviewTask;
import com.backendjava.task.ReviewTaskStatus;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import reactor.core.publisher.Flux;

public class MockAiEngineAdapter implements AiEngineAdapter {
    @Override
    public Flux<EngineEvent> startReview(ReviewTask task) {
        List<Map<String, Object>> stages = List.of(
                Map.of(
                        "stage", "patch_apply",
                        "status", "passed",
                        "summary", "Patch applied cleanly."),
                Map.of(
                        "stage", "compile",
                        "status", "passed",
                        "summary", "javac compile passed."),
                Map.of(
                        "stage", "lint",
                        "status", "skipped",
                        "summary", "No lint command configured.",
                        "skip_reason", "missing_lint_runner"),
                Map.of(
                        "stage", "test",
                        "status", "blocked",
                        "summary", "No executable regression test target found.",
                        "skip_reason", "missing_test_target"),
                Map.of(
                        "stage", "security_rescan",
                        "status", "pending",
                        "summary", "Not executed."));

        Map<String, Object> taxonomy = new LinkedHashMap<>();
        taxonomy.put("bucket", "none");
        taxonomy.put("legacy_bucket", "none");
        taxonomy.put("code", null);
        taxonomy.put("explanation", null);

        Map<String, Object> delivery = new LinkedHashMap<>();
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
        delivery.put("verification_stages", stages);
        delivery.put("final_outcome", "verified_patch");
        delivery.put("failed_stage", null);
        delivery.put("failure_code", null);
        delivery.put("failure_reason", null);
        delivery.put("retryable", false);

        Map<String, Object> executionTruth = new LinkedHashMap<>();
        executionTruth.put("patch_apply_status", "passed");
        executionTruth.put("compile_status", "passed");
        executionTruth.put("lint_status", "skipped");
        executionTruth.put("test_status", "blocked");
        executionTruth.put("security_rescan_status", "pending");
        executionTruth.put("regression_risk", "untested");
        executionTruth.put("failure_taxonomy", taxonomy);
        executionTruth.put("next_context_hint", "Provide test command for regression validation.");
        executionTruth.put("next_constraint_hint", "Clarify whether behavior changes are allowed.");
        executionTruth.put("next_retry_strategy", "Configure tests then rerun verifier.");

        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("verified_level", "L1");
        summary.put("final_outcome", "verified_patch");
        summary.put("failure_taxonomy", taxonomy);
        summary.put(
                "user_message",
                "Patch applied and compile passed. Lint skipped, test blocked, security pending; regression risk remains untested.");

        Map<String, Object> verification = new LinkedHashMap<>();
        verification.put("status", "passed");
        verification.put("overall_status", "partial_pass");
        verification.put("verified_level", "L1");
        verification.put("regression_risk", "untested");
        verification.put("stages", stages);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("engine", "mock");
        result.put("delivery", delivery);
        result.put("execution_truth", executionTruth);
        result.put("summary", summary);
        result.put("patch", Map.of("status", "generated", "unified_diff", delivery.get("unified_diff")));
        result.put("verification", verification);

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
                                        delivery,
                                        "execution_truth",
                                        executionTruth)))
                .delayElements(Duration.ofMillis(600));
    }
}
