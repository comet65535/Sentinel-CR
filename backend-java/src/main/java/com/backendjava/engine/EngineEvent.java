package com.backendjava.engine;

import com.backendjava.task.ReviewTaskStatus;
import java.util.Map;

public record EngineEvent(
        String eventType,
        String message,
        ReviewTaskStatus status,
        Map<String, Object> payload) {
}
