package com.backendjava.service;

import com.backendjava.api.dto.CreateReviewRequest;
import com.backendjava.api.dto.CreateReviewResponse;
import com.backendjava.api.dto.ReviewHistoryItemResponse;
import com.backendjava.api.dto.ReviewTaskResponse;
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

    public ReviewService(
            InMemoryTaskRepository taskRepository,
            ReviewEventBus reviewEventBus,
            AiEngineAdapter aiEngineAdapter,
            PythonEngineProperties aiProperties) {
        this.taskRepository = taskRepository;
        this.reviewEventBus = reviewEventBus;
        this.aiEngineAdapter = aiEngineAdapter;
        this.aiProperties = aiProperties;
    }

    public CreateReviewResponse createReviewTask(CreateReviewRequest request) {
        validateReviewRequest(request);

        String taskId = generateTaskId();
        ReviewTask task =
                new ReviewTask(
                        taskId,
                        request.getCodeText(),
                        request.getLanguage(),
                        request.getSourceType(),
                        request.getOptions(),
                        request.getMetadata());
        taskRepository.save(task);
        reviewEventBus.initializeTaskStream(taskId);

        publishTaskEvent(
                task,
                "task_created",
                "task created",
                ReviewTaskStatus.CREATED,
                Map.of("source", "backend", "engine", aiProperties.getMode()));
        startReviewPipeline(task);

        return new CreateReviewResponse(taskId, task.getStatus(), "review task created");
    }

    public ReviewTaskResponse getTaskDetail(String taskId) {
        ReviewTask task =
                taskRepository
                        .findByTaskId(taskId)
                        .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "task not found"));

        return new ReviewTaskResponse(
                task.getTaskId(),
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
    }

    private void handleEngineFailure(ReviewTask task, Throwable throwable) {
        String errorMessage = throwable.getMessage() == null ? "unknown engine failure" : throwable.getMessage();
        task.markFailed(errorMessage);

        publishTaskEvent(
                task,
                "review_failed",
                "review failed",
                ReviewTaskStatus.FAILED,
                Map.of(
                        "source", "backend",
                        "stage", "engine_error",
                        "engine", aiProperties.getMode(),
                        "errorType", classifyEngineError(errorMessage),
                        "error", errorMessage));

        reviewEventBus.completeTaskStream(task.getTaskId());
    }

    private void publishTaskEvent(
            ReviewTask task,
            String eventType,
            String message,
            ReviewTaskStatus status,
            Map<String, Object> payload) {
        ReviewEvent event =
                new ReviewEvent(
                        task.getTaskId(),
                        eventType,
                        message,
                        Instant.now(),
                        task.nextSequence(),
                        status,
                        payload == null ? Map.of() : payload);
        reviewEventBus.publish(event);
    }

    private void validateReviewRequest(CreateReviewRequest request) {
        if (!"java".equalsIgnoreCase(request.getLanguage())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Day1 only supports language=java");
        }
        if (!"snippet".equalsIgnoreCase(request.getSourceType())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Day1 only supports sourceType=snippet");
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

        String title = deriveTitle(task.getCodeText());
        boolean hasPatch = !asText(patch.get("unified_diff"), "").isBlank() || !asText(patch.get("content"), "").isBlank();

        return new ReviewHistoryItemResponse(
                task.getTaskId(),
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

    private String deriveTitle(String codeText) {
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
