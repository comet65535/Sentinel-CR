package com.backendjava.task;

import java.time.Instant;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;

public class ReviewTask {
    private final String taskId;
    private final String conversationId;
    private final String messageId;
    private final String parentMessageId;
    private final String messageText;
    private final String codeText;
    private final String language;
    private final String sourceType;
    private final Map<String, Object> options;
    private final Map<String, Object> metadata;
    private final AtomicLong sequenceCounter = new AtomicLong(0);

    private volatile ReviewTaskStatus status;
    private volatile Instant createdAt;
    private volatile Instant updatedAt;
    private volatile Map<String, Object> result;
    private volatile String errorMessage;

    public ReviewTask(String taskId, String codeText, String language, String sourceType) {
        this(taskId, null, null, null, null, codeText, language, sourceType, Map.of(), Map.of());
    }

    public ReviewTask(String taskId, String codeText, String language, String sourceType, Map<String, Object> options) {
        this(taskId, null, null, null, null, codeText, language, sourceType, options, Map.of());
    }

    public ReviewTask(
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
        Instant now = Instant.now();
        this.taskId = taskId;
        this.conversationId = conversationId;
        this.messageId = messageId;
        this.parentMessageId = parentMessageId;
        this.messageText = messageText;
        this.codeText = codeText;
        this.language = language;
        this.sourceType = sourceType;
        this.options = Collections.unmodifiableMap(new LinkedHashMap<>(options == null ? Map.of() : options));
        this.metadata = Collections.unmodifiableMap(new LinkedHashMap<>(metadata == null ? Map.of() : metadata));
        this.status = ReviewTaskStatus.CREATED;
        this.createdAt = now;
        this.updatedAt = now;
        this.result = Map.of();
    }

    public long nextSequence() {
        return sequenceCounter.incrementAndGet();
    }

    public synchronized void updateStatus(ReviewTaskStatus nextStatus) {
        this.status = nextStatus;
        this.updatedAt = Instant.now();
    }

    public synchronized void markCompleted(Map<String, Object> result) {
        this.status = ReviewTaskStatus.COMPLETED;
        this.updatedAt = Instant.now();
        this.result = result == null ? Map.of() : Collections.unmodifiableMap(new LinkedHashMap<>(result));
        this.errorMessage = null;
    }

    public synchronized void markFailed(String errorMessage) {
        this.status = ReviewTaskStatus.FAILED;
        this.updatedAt = Instant.now();
        this.errorMessage = errorMessage;
    }

    public String getTaskId() {
        return taskId;
    }

    public String getConversationId() {
        return conversationId;
    }

    public String getMessageId() {
        return messageId;
    }

    public String getParentMessageId() {
        return parentMessageId;
    }

    public String getMessageText() {
        return messageText;
    }

    public String getCodeText() {
        return codeText;
    }

    public String getLanguage() {
        return language;
    }

    public String getSourceType() {
        return sourceType;
    }

    public Map<String, Object> getOptions() {
        return options;
    }

    public Map<String, Object> getMetadata() {
        return metadata;
    }

    public ReviewTaskStatus getStatus() {
        return status;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }

    public Map<String, Object> getResult() {
        return result;
    }

    public String getErrorMessage() {
        return errorMessage;
    }
}
