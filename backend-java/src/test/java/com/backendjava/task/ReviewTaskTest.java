package com.backendjava.task;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;

import java.util.HashMap;
import java.util.Map;
import org.junit.jupiter.api.Test;

class ReviewTaskTest {

    @Test
    void markCompletedShouldAcceptNullValuesInResultPayload() {
        ReviewTask task = new ReviewTask("rev_test_nulls", "public class Demo {}", "java", "snippet");
        Map<String, Object> result = new HashMap<>();
        result.put("summary", Map.of("final_outcome", "patch_generated"));
        result.put("verification", null);
        result.put("patch", Map.of("status", "generated"));

        assertThatCode(() -> task.markCompleted(result)).doesNotThrowAnyException();

        assertThat(task.getStatus()).isEqualTo(ReviewTaskStatus.COMPLETED);
        assertThat(task.getResult()).containsEntry("verification", null);
        assertThat(task.getErrorMessage()).isNull();
    }
}
