package com.backendjava.event;

import com.backendjava.task.ReviewTaskStatus;
import java.time.Instant;
import java.util.Map;

public record ReviewEvent(
        String taskId,
        String eventType,
        String message,
        Instant timestamp,
        long sequence,
        ReviewTaskStatus status,
        Map<String, Object> payload) {
}
