package com.backendjava.engine;

import com.backendjava.task.ReviewTaskStatus;
import java.util.Locale;
import java.util.Map;
import org.springframework.stereotype.Component;

@Component
public class EngineEventMapper {

    public EngineEvent fromPythonEvent(String expectedTaskId, PythonEngineEvent pythonEvent) {
        if (pythonEvent == null) {
            throw new IllegalArgumentException("python engine event must not be null");
        }
        if (pythonEvent.taskId() == null || pythonEvent.taskId().isBlank()) {
            throw new IllegalArgumentException("python engine event missing taskId");
        }
        if (!expectedTaskId.equals(pythonEvent.taskId())) {
            throw new IllegalArgumentException(
                    "python engine taskId mismatch, expected=" + expectedTaskId + ", actual=" + pythonEvent.taskId());
        }
        if (pythonEvent.eventType() == null || pythonEvent.eventType().isBlank()) {
            throw new IllegalArgumentException("python engine event missing eventType");
        }
        if (pythonEvent.message() == null || pythonEvent.message().isBlank()) {
            throw new IllegalArgumentException("python engine event missing message");
        }

        ReviewTaskStatus status = parseStatus(pythonEvent.status());
        Map<String, Object> payload = pythonEvent.payload() == null ? Map.of() : pythonEvent.payload();

        return new EngineEvent(pythonEvent.eventType(), pythonEvent.message(), status, payload);
    }

    private ReviewTaskStatus parseStatus(String rawStatus) {
        if (rawStatus == null || rawStatus.isBlank()) {
            throw new IllegalArgumentException("python engine event missing status");
        }
        try {
            return ReviewTaskStatus.valueOf(rawStatus.trim().toUpperCase(Locale.ROOT));
        } catch (IllegalArgumentException ex) {
            throw new IllegalArgumentException("unknown python engine status: " + rawStatus, ex);
        }
    }
}
