package com.backendjava.api.dto;

import com.backendjava.task.ReviewTaskStatus;

public record CreateReviewResponse(String taskId, ReviewTaskStatus status, String message) {
}
