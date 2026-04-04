package com.backendjava.api.dto;

import com.backendjava.task.ReviewTaskStatus;

public record CreateReviewResponse(
        String taskId,
        String conversationId,
        String messageId,
        ReviewTaskStatus status,
        String message) {
}
