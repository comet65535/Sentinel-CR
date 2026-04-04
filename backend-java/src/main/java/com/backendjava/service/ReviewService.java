package com.backendjava.service;

import com.backendjava.api.dto.CreateReviewRequest;
import com.backendjava.api.dto.CreateReviewResponse;
import com.backendjava.api.dto.ReviewHistoryItemResponse;
import com.backendjava.api.dto.ReviewTaskResponse;
import com.backendjava.conversation.ConversationStore;
import com.backendjava.engine.AiEngineAdapter;
import com.backendjava.engine.EngineEvent;
import com.backendjava.engine.PythonEngineProperties;
import com.backendjava.event.ReviewEvent;
import com.backendjava.event.ReviewEventBus;
import com.backendjava.task.InMemoryTaskRepository;
import com.backendjava.task.ReviewTask;
import com.backendjava.task.ReviewTaskStatus;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicBoolean;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
import reactor.core.publisher.Flux;

@Service
public class ReviewService {
    private static final DateTimeFormatter TASK_ID_DATE_FORMATTER =
            DateTimeFormatter.ofPattern("yyyyMMddHHmmss").withZone(ZoneOffset.UTC);

    private final InMemoryTaskRepository taskRepository;
    private final ReviewEventBus reviewEventBus;
    private final AiEngineAdapter aiEngineAdapter;
    private final PythonEngineProperties aiProperties;
    private final ConversationStore conversationStore;

    public ReviewService(
            InMemoryTaskRepository taskRepository,
            ReviewEventBus reviewEventBus,
            AiEngineAdapter aiEngineAdapter,
            PythonEngineProperties aiProperties,
            ConversationStore conversationStore) {
        this.taskRepository = taskRepository;
        this.reviewEventBus = reviewEventBus;
        this.aiEngineAdapter = aiEngineAdapter;
        this.aiProperties = aiProperties;
        this.conversationStore = conversationStore;
    }

    public CreateReviewResponse createReviewTask(CreateReviewRequest request) {
        validateReviewRequest(request);

        String conversationId = normalize(request.getConversationId());
        String messageText = normalize(request.getMessageText());
        String codeText = normalize(request.getCodeText());
        String parentMessageId = normalize(request.getParentMessageId());
        String sourceType = normalize(request.getSourceType());

        if (conversationId == null) {
            conversationId = conversationStore.createConversation(deriveConversationTitle(messageText, codeText));
        } else {
            conversationStore.ensureConversation(conversationId, deriveConversationTitle(messageText, codeText));
        }

        Map<String, Object> threadState = conversationStore.getThreadState(conversationId);
        String latestCode = normalize(asText(threadState.get("latest_code"), null));
        if (codeText == null && latestCode != null) {
            codeText = latestCode;
        }

        if (codeText == null || codeText.isBlank()) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "codeText is required for new conversation or when thread_state has no latest_code");
        }

        String taskId = generateTaskId();
        String userMessageId = conversationStore.addMessage(
                conversationId,
                parentMessageId,
                "user",
                messageText,
                codeText,
                taskId,
                normalize(request.getMessageId()));

        Map<String, Object> metadata = mergedMetadata(request, conversationId, userMessageId, parentMessageId, threadState);
        Map<String, Object> options = mergedOptions(request, metadata);

        ReviewTask task =
                new ReviewTask(
                        taskId,
                        conversationId,
                        userMessageId,
                        parentMessageId,
                        messageText,
                        codeText,
                        request.getLanguage(),
                        sourceType == null ? "snippet" : sourceType,
                        options,
                        metadata);
        taskRepository.save(task);
        reviewEventBus.initializeTaskStream(taskId);

        conversationStore.upsertThreadState(
                conversationId,
                codeText,
                asMap(threadState.get("latest_patch")),
                asMap(threadState.get("latest_verifier_failure")),
                asMap(threadState.get("short_term_memory")),
                asText(metadata.get("repo_profile_id"), null),
                asText(metadata.get("repo_id"), null));

        publishTaskEvent(
                task,
                "task_created",
                "task created",
                ReviewTaskStatus.CREATED,
                Map.of(
                        "source", "backend",
                        "engine", aiProperties.getMode(),
                        "conversationId", conversationId,
                        "messageId", userMessageId));
        startReviewPipeline(task);

        return new CreateReviewResponse(taskId, conversationId, userMessageId, task.getStatus(), "review task created");
    }

    public ReviewTaskResponse getTaskDetail(String taskId) {
        ReviewTask task =
                taskRepository
                        .findByTaskId(taskId)
                        .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "task not found"));

        return new ReviewTaskResponse(
                task.getTaskId(),
                task.getConversationId(),
                task.getMessageId(),
                task.getParentMessageId(),
                task.getStatus(),
                task.getCreatedAt(),
                task.getUpdatedAt(),
                task.getResult(),
                task.getErrorMessage());
    }

    public List<ReviewHistoryItemResponse> listReviewTasks(int limit) {
        int cappedLimit = Math.max(1, Math.min(limit, 500));
        return taskRepository.findAll().stream()
                .sorted(Comparator.comparing(ReviewTask::getUpdatedAt).reversed())
                .limit(cappedLimit)
                .map(this::toHistoryItem)
                .toList();
    }

    public List<Map<String, Object>> listConversations(int limit) {
        return conversationStore.listConversations(limit);
    }

    public List<Map<String, Object>> listConversationMessages(String conversationId, int limit) {
        return conversationStore.listMessages(conversationId, limit);
    }

    public Flux<ReviewEvent> streamTaskEvents(String taskId) {
        if (!taskRepository.existsByTaskId(taskId)) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "task not found");
        }
        return reviewEventBus.streamForTask(taskId);
    }

    private void startReviewPipeline(ReviewTask task) {
        AtomicBoolean terminalEventObserved = new AtomicBoolean(false);

        aiEngineAdapter.startReview(task)
                .doOnNext(event -> {
                    handleEngineEvent(task, event);
                    if (event.status() == ReviewTaskStatus.COMPLETED || event.status() == ReviewTaskStatus.FAILED) {
                        terminalEventObserved.set(true);
                    }
                })
                .doOnError(throwable -> {
                    if (terminalEventObserved.get()) {
                        reviewEventBus.completeTaskStream(task.getTaskId());
                        return;
                    }
                    handleEngineFailure(task, throwable);
                })
                .doOnComplete(() -> {
                    if (terminalEventObserved.get()) {
                        reviewEventBus.completeTaskStream(task.getTaskId());
                        return;
                    }
                    handleEngineFailure(task, new IllegalStateException("engine stream completed without terminal event"));
                })
                .subscribe(
                        ignored -> { },
                        ignored -> { });
    }

    private void handleEngineEvent(ReviewTask task, EngineEvent engineEvent) {
        ReviewTaskStatus status = engineEvent.status();
        if (status == ReviewTaskStatus.RUNNING) {
            task.updateStatus(ReviewTaskStatus.RUNNING);
        } else if (status == ReviewTaskStatus.COMPLETED) {
            task.markCompleted(extractPersistedResult(engineEvent.payload()));
        } else if (status == ReviewTaskStatus.FAILED) {
            task.markFailed(engineEvent.message());
        }

        publishTaskEvent(task, engineEvent.eventType(), engineEvent.message(), status, engineEvent.payload());

        if (status == ReviewTaskStatus.COMPLETED || status == ReviewTaskStatus.FAILED) {
            persistTerminalState(task, engineEvent.payload(), status);
            reviewEventBus.completeTaskStream(task.getTaskId());
        }
    }

    private void handleEngineFailure(ReviewTask task, Throwable throwable) {
        String errorMessage = throwable.getMessage() == null ? "unknown engine failure" : throwable.getMessage();
        task.markFailed(errorMessage);

        Map<String, Object> payload = new HashMap<>();
        payload.put("source", "backend");
        payload.put("stage", "engine_error");
        payload.put("engine", aiProperties.getMode());
        payload.put("errorType", classifyEngineError(errorMessage));
        payload.put("error", errorMessage);
        if (task.getConversationId() != null) {
            payload.put("conversationId", task.getConversationId());
        }
        if (task.getMessageId() != null) {
            payload.put("messageId", task.getMessageId());
        }

        publishTaskEvent(
                task,
                "review_failed",
                "review failed",
                ReviewTaskStatus.FAILED,
                payload);

        persistTerminalState(task, payload, ReviewTaskStatus.FAILED);
        reviewEventBus.completeTaskStream(task.getTaskId());
    }

    private void publishTaskEvent(
            ReviewTask task,
            String eventType,
            String message,
            ReviewTaskStatus status,
            Map<String, Object> payload) {
        Map<String, Object> safePayload = payload == null ? Map.of() : payload;
        ReviewEvent event =
                new ReviewEvent(
                        task.getTaskId(),
                        eventType,
                        message,
                        Instant.now(),
                        task.nextSequence(),
                        status,
                        safePayload);
        reviewEventBus.publish(event);
        conversationStore.appendEventLog(task.getTaskId(), task.getConversationId(), event.sequence(), eventType, safePayload);
    }

    private void validateReviewRequest(CreateReviewRequest request) {
        if (!"java".equalsIgnoreCase(request.getLanguage())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "only supports language=java");
        }
        if (!"snippet".equalsIgnoreCase(request.getSourceType())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "only supports sourceType=snippet");
        }
    }

    private String classifyEngineError(String errorMessage) {
        String lowerMessage = errorMessage.toLowerCase();
        if (lowerMessage.contains("connection") || lowerMessage.contains("timeout") || lowerMessage.contains("refused")) {
            return "python_unreachable";
        }
        return "engine_error";
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> extractPersistedResult(Map<String, Object> payload) {
        if (payload == null || payload.isEmpty()) {
            return Map.of();
        }
        Object resultCandidate = payload.get("result");
        if (resultCandidate instanceof Map<?, ?> resultMap) {
            return (Map<String, Object>) resultMap;
        }
        return payload;
    }

    private void persistTerminalState(ReviewTask task, Map<String, Object> payload, ReviewTaskStatus status) {
        Map<String, Object> result = status == ReviewTaskStatus.COMPLETED ? extractPersistedResult(payload) : Map.of();
        Map<String, Object> patch = asMap(result.get("patch"));
        Map<String, Object> verification = asMap(result.get("verification"));
        Map<String, Object> memory = asMap(result.get("memory"));
        Map<String, Object> shortTermMemory = asMap(memory.get("short_term"));
        Map<String, Object> latestVerifierFailure = asMap(shortTermMemory.get("latest_verifier_failure"));

        conversationStore.upsertThreadState(
                task.getConversationId(),
                task.getCodeText(),
                patch,
                latestVerifierFailure,
                shortTermMemory,
                asText(task.getMetadata().get("repo_profile_id"), null),
                asText(task.getMetadata().get("repo_id"), null));

        if (!patch.isEmpty()) {
            conversationStore.appendPatchHistory(task.getTaskId(), task.getConversationId(), patch, verification);
        }

        String assistantText;
        if (status == ReviewTaskStatus.COMPLETED) {
            Map<String, Object> summary = asMap(result.get("summary"));
            assistantText = asText(summary.get("user_message"), "Review completed.");
        } else {
            assistantText = asText(payload.get("error"), "Review failed.");
        }
        conversationStore.addMessage(
                task.getConversationId(),
                task.getMessageId(),
                "assistant",
                assistantText,
                null,
                task.getTaskId(),
                null);
    }

    private String generateTaskId() {
        String timestamp = TASK_ID_DATE_FORMATTER.format(Instant.now());
        String suffix = UUID.randomUUID().toString().replace("-", "").substring(0, 6);
        return "rev_" + timestamp + "_" + suffix;
    }

    @SuppressWarnings("unchecked")
    private ReviewHistoryItemResponse toHistoryItem(ReviewTask task) {
        Map<String, Object> result = task.getResult() == null ? Map.of() : task.getResult();
        Map<String, Object> summary = asMap(result.get("summary"));
        Map<String, Object> failureTaxonomy = asMap(summary.get("failure_taxonomy"));
        Map<String, Object> patch = asMap(result.get("patch"));

        String finalStatus = asText(summary.get("final_outcome"), task.getStatus().name().toLowerCase());
        String verifiedLevel = asText(summary.get("verified_level"), "L0");
        String bucket = asText(failureTaxonomy.get("bucket"), "none");

        String title = deriveTitle(task.getCodeText(), task.getMessageText());
        boolean hasPatch = !asText(patch.get("unified_diff"), "").isBlank() || !asText(patch.get("content"), "").isBlank();

        return new ReviewHistoryItemResponse(
                task.getTaskId(),
                task.getConversationId(),
                task.getMessageId(),
                task.getStatus().name(),
                task.getCreatedAt(),
                task.getUpdatedAt(),
                title,
                asText(task.getSourceType(), "snippet"),
                new ReviewHistoryItemResponse.ReviewHistorySummary(
                        finalStatus,
                        verifiedLevel,
                        new ReviewHistoryItemResponse.ReviewHistoryFailureTaxonomy(bucket)),
                hasPatch);
    }

    private String deriveTitle(String codeText, String messageText) {
        if (messageText != null && !messageText.isBlank()) {
            String trimmed = messageText.trim();
            if (trimmed.length() <= 80) {
                return trimmed;
            }
            return trimmed.substring(0, 77) + "...";
        }
        if (codeText == null || codeText.isBlank()) {
            return "Untitled Review";
        }
        String[] lines = codeText.split("\\R");
        for (String line : lines) {
            String trimmed = line.trim();
            if (!trimmed.isBlank()) {
                if (trimmed.length() <= 80) {
                    return trimmed;
                }
                return trimmed.substring(0, 77) + "...";
            }
        }
        return "Untitled Review";
    }

    private String deriveConversationTitle(String messageText, String codeText) {
        return deriveTitle(codeText, messageText);
    }

    private Map<String, Object> mergedMetadata(
            CreateReviewRequest request,
            String conversationId,
            String messageId,
            String parentMessageId,
            Map<String, Object> threadState) {
        Map<String, Object> metadata = new HashMap<>();
        metadata.putAll(request.getMetadata() == null ? Map.of() : request.getMetadata());
        metadata.put("conversation_id", conversationId);
        metadata.put("message_id", messageId);
        if (parentMessageId != null) {
            metadata.put("parent_message_id", parentMessageId);
        }
        if (!metadata.containsKey("requested_by")) {
            metadata.put("requested_by", "backend-java");
        }
        Map<String, Object> latestVerifierFailure = asMap(threadState.get("latest_verifier_failure"));
        if (!latestVerifierFailure.isEmpty()) {
            metadata.put("latest_verifier_failure", latestVerifierFailure);
        }
        Map<String, Object> latestPatch = asMap(threadState.get("latest_patch"));
        if (!latestPatch.isEmpty()) {
            metadata.put("latest_patch", latestPatch);
        }
        String userConstraints = normalize(request.getMessageText());
        if (userConstraints != null) {
            metadata.put("user_constraints", userConstraints);
        }
        String repoProfileId = normalize(asText(metadata.get("repo_profile_id"), asText(threadState.get("repo_profile_id"), null)));
        String repoId = normalize(asText(metadata.get("repo_id"), asText(threadState.get("repo_id"), null)));
        if (repoProfileId != null) {
            metadata.put("repo_profile_id", repoProfileId);
        }
        if (repoId != null) {
            metadata.put("repo_id", repoId);
        }
        return metadata;
    }

    private Map<String, Object> mergedOptions(CreateReviewRequest request, Map<String, Object> metadata) {
        Map<String, Object> options = new HashMap<>();
        options.putAll(request.getOptions() == null ? Map.of() : request.getOptions());
        if (!options.containsKey("llm_enabled")) {
            options.put("llm_enabled", true);
        }
        if (metadata.containsKey("user_constraints")) {
            options.put("user_constraints", metadata.get("user_constraints"));
        }
        return options;
    }

    private String normalize(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }

    private String asText(Object value, String fallback) {
        if (value instanceof String text && !text.isBlank()) {
            return text;
        }
        return fallback;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> asMap(Object value) {
        if (value instanceof Map<?, ?> map) {
            return (Map<String, Object>) map;
        }
        return Map.of();
    }
}
