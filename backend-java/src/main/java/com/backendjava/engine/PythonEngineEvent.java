package com.backendjava.engine;

import java.util.Map;

public record PythonEngineEvent(
        String taskId,
        String eventType,
        String message,
        String status,
        Map<String, Object> payload) {
}
