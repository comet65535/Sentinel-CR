package com.backendjava.service;

import com.backendjava.api.dto.CreateReviewRequest;
import com.backendjava.api.dto.CreateReviewResponse;
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
                new ReviewTask(taskId, request.getCodeText(), request.getLanguage(), request.getSourceType());
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
                .doOnError(throwable -> handleEngineFailure(task, throwable))
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
            task.markCompleted(engineEvent.payload());
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

    private String generateTaskId() {
        String timestamp = TASK_ID_DATE_FORMATTER.format(Instant.now());
        String suffix = UUID.randomUUID().toString().replace("-", "").substring(0, 6);
        return "rev_" + timestamp + "_" + suffix;
    }
}
