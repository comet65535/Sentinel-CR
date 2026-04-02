package com.backendjava.engine;

import java.util.Map;

public record PythonReviewRunRequest(
        String taskId,
        String codeText,
        String language,
        String sourceType,
        Map<String, Object> options,
        Map<String, Object> metadata) {
}
