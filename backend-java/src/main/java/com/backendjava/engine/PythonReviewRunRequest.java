package com.backendjava.engine;

import java.util.Map;

public record PythonReviewRunRequest(
        String taskId,
        String conversationId,
        String messageId,
        String parentMessageId,
        String messageText,
        String codeText,
        String language,
        String sourceType,
        Map<String, Object> options,
        Map<String, Object> metadata) {
}
