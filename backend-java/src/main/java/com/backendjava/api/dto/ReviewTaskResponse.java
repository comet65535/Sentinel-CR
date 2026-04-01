package com.backendjava.api.dto;

import com.backendjava.task.ReviewTaskStatus;
import java.time.Instant;
import java.util.Map;

public record ReviewTaskResponse(
        String taskId,
        ReviewTaskStatus status,
        Instant createdAt,
        Instant updatedAt,
        Map<String, Object> result,
        String errorMessage) {
}
