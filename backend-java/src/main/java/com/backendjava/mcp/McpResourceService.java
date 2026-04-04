package com.backendjava.mcp;

import com.backendjava.task.InMemoryTaskRepository;
import com.backendjava.task.ReviewTask;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import org.springframework.stereotype.Service;

@Service
public class McpResourceService {
    private static final Set<String> ALLOWED_TASK_FILES = Set.of("snippet.java", "Snippet.java");
    private static final Set<String> ALLOWED_SCHEMA_TYPES = Set.of("api_contract", "event_schema", "architecture");

    private final InMemoryTaskRepository taskRepository;

    public McpResourceService(InMemoryTaskRepository taskRepository) {
        this.taskRepository = taskRepository;
    }

    public McpEnvelope repoTree(String taskId, Integer depth) {
        long started = System.currentTimeMillis();
        ReviewTask task = findTask(taskId);
        if (task == null) {
            return error("resource", "repo-tree", "task_not_found", "task not found", started);
        }
        int safeDepth = depth == null ? 2 : Math.max(1, Math.min(depth, 5));
        Map<String, Object> tree = new LinkedHashMap<>();
        tree.put("name", "snippet-repo");
        tree.put("type", "directory");
        tree.put("depth", safeDepth);
        tree.put("children", List.of(Map.of(
                "name", "snippet.java",
                "type", "file",
                "size", task.getCodeText() == null ? 0 : task.getCodeText().length())));
        return ok("resource", "repo-tree", Map.of("tree", tree), started);
    }

    public McpEnvelope file(String taskId, String path, Integer startLine, Integer endLine) {
        long started = System.currentTimeMillis();
        ReviewTask task = findTask(taskId);
        if (task == null) {
            return error("resource", "file", "task_not_found", "task not found", started);
        }
        String targetPath = (path == null || path.isBlank()) ? "snippet.java" : path;
        String normalizedPath = normalizeAndValidatePath(targetPath);
        if (normalizedPath == null) {
            return error(
                    "resource",
                    "file",
                    "access_denied",
                    "Requested path is outside the allowed repository scope.",
                    started);
        }

        int from = startLine == null || startLine < 1 ? 1 : startLine;
        String[] lines = task.getCodeText().split("\\R", -1);
        int to = endLine == null || endLine < from ? lines.length : Math.min(endLine, lines.length);
        StringBuilder sb = new StringBuilder();
        for (int i = from; i <= to; i++) {
            sb.append(lines[i - 1]);
            if (i < to) {
                sb.append("\n");
            }
        }
        Map<String, Object> data = new HashMap<>();
        data.put("path", normalizedPath);
        data.put("startLine", from);
        data.put("endLine", to);
        data.put("truncated", false);
        data.put("content", sb.toString());
        data.put("lineCount", Math.max(0, to - from + 1));
        return ok("resource", "file", data, started);
    }

    public McpEnvelope schema(String taskId, String schemaType) {
        long started = System.currentTimeMillis();
        if (findTask(taskId) == null) {
            return error("resource", "schema", "task_not_found", "task not found", started);
        }
        String normalizedType = normalizeSchemaType(schemaType);
        if (!ALLOWED_SCHEMA_TYPES.contains(normalizedType)) {
            return error("resource", "schema", "invalid_schema_type", "Unsupported schema type.", started);
        }
        Path schemaPath = schemaPathFor(normalizedType);
        if (!Files.exists(schemaPath)) {
            return error("resource", "schema", "not_configured", "Schema file is not configured.", started);
        }
        try {
            String content = Files.readString(schemaPath, StandardCharsets.UTF_8);
            return ok(
                    "resource",
                    "schema",
                    Map.of(
                            "schema_type", normalizedType,
                            "content", content,
                            "content_length", content.length(),
                            "source", schemaPath.getFileName().toString()),
                    started);
        } catch (IOException ignored) {
            return error("resource", "schema", "not_configured", "Schema content is unavailable.", started);
        }
    }

    public McpEnvelope buildLogSummary(String taskId) {
        long started = System.currentTimeMillis();
        ReviewTask task = findTask(taskId);
        if (task == null) {
            return error("resource", "build-log-summary", "task_not_found", "task not found", started);
        }
        Map<String, Object> verification = asMap(task.getResult().get("verification"));
        Map<String, Object> compileResult = findStageResult(verification, "compile");
        boolean configured = !compileResult.isEmpty();

        Map<String, Object> latestBuild = new LinkedHashMap<>();
        latestBuild.put("command", "compile");
        latestBuild.put("exit_code", toNullableInt(compileResult.get("exit_code")));
        latestBuild.put("stdout_summary", asText(compileResult.get("stdout_summary"), ""));
        latestBuild.put("stderr_summary", asText(compileResult.get("stderr_summary"), ""));
        latestBuild.put("status", asText(compileResult.get("status"), configured ? "unknown" : "not_available"));
        latestBuild.put("updated_at", task.getUpdatedAt() == null ? Instant.now().toString() : task.getUpdatedAt().toString());
        latestBuild.put("task_status", task.getStatus().name());

        Map<String, Object> data = new LinkedHashMap<>();
        data.put("status", configured ? "available" : "partial");
        data.put("latest_build", latestBuild);
        return ok("resource", "build-log-summary", data, started);
    }

    public McpEnvelope testSummary(String taskId) {
        long started = System.currentTimeMillis();
        ReviewTask task = findTask(taskId);
        if (task == null) {
            return error("resource", "test-summary", "task_not_found", "task not found", started);
        }

        Map<String, Object> verification = asMap(task.getResult().get("verification"));
        Map<String, Object> testResult = findStageResult(verification, "test");
        boolean configured = !testResult.isEmpty();

        Map<String, Object> data = new LinkedHashMap<>();
        data.put("status", configured ? "available" : "partial");
        data.put("suggested_test_commands", List.of("mvn -q test"));
        Map<String, Object> lastResult = new LinkedHashMap<>();
        lastResult.put("status", asText(testResult.get("status"), configured ? "unknown" : "not_available"));
        lastResult.put("exit_code", toNullableInt(testResult.get("exit_code")));
        lastResult.put("stdout_summary", asText(testResult.get("stdout_summary"), ""));
        lastResult.put("stderr_summary", asText(testResult.get("stderr_summary"), ""));
        data.put("last_result", lastResult);
        data.put("verified_level", asText(verification.get("verified_level"), "L0"));
        return ok("resource", "test-summary", data, started);
    }

    public McpEnvelope parsePrDiff(String taskId, Map<String, Object> body) {
        long started = System.currentTimeMillis();
        if (findTask(taskId) == null) {
            return error("resource", "pr-diff", "task_not_found", "task not found", started);
        }
        return error(
                "resource",
                "pr-diff",
                "not_configured",
                "PR diff parsing is not configured for this task type.",
                started);
    }

    private ReviewTask findTask(String taskId) {
        return taskRepository.findByTaskId(taskId).orElse(null);
    }

    private McpEnvelope ok(String kind, String name, Object data, long startedMs) {
        return new McpEnvelope(
                true,
                kind,
                name,
                "mcp_" + UUID.randomUUID().toString().replace("-", "").substring(0, 10),
                data,
                Map.of("latency_ms", Math.max(0, System.currentTimeMillis() - startedMs), "cache_hit", false),
                null);
    }

    private McpEnvelope error(String kind, String name, String code, String message, long startedMs) {
        return new McpEnvelope(
                false,
                kind,
                name,
                "mcp_" + UUID.randomUUID().toString().replace("-", "").substring(0, 10),
                null,
                Map.of("latency_ms", Math.max(0, System.currentTimeMillis() - startedMs), "cache_hit", false),
                Map.of("code", sanitizeCode(code), "message", sanitizeMessage(message)));
    }

    private String normalizeAndValidatePath(String path) {
        if (path == null || path.isBlank()) {
            return null;
        }
        String compact = path.replace('\\', '/').trim();
        if (compact.startsWith("/") || compact.contains("..") || compact.contains(":") || compact.contains("\u0000")) {
            return null;
        }
        Path normalized = Path.of(compact).normalize();
        if (normalized.isAbsolute()) {
            return null;
        }
        String normalizedPath = normalized.toString().replace('\\', '/');
        if (!ALLOWED_TASK_FILES.contains(normalizedPath)) {
            return null;
        }
        return normalizedPath;
    }

    private String normalizeSchemaType(String rawSchemaType) {
        if (rawSchemaType == null || rawSchemaType.isBlank()) {
            return "api_contract";
        }
        return rawSchemaType.trim().toLowerCase();
    }

    private Path schemaPathFor(String schemaType) {
        return switch (schemaType) {
            case "api_contract" -> Path.of("..", "docs", "api-contract.md").normalize();
            case "event_schema" -> Path.of("..", "docs", "event-schema.md").normalize();
            case "architecture" -> Path.of("..", "docs", "architecture.md").normalize();
            default -> Path.of("..", "docs", "api-contract.md").normalize();
        };
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> asMap(Object value) {
        if (value instanceof Map<?, ?> raw) {
            return (Map<String, Object>) raw;
        }
        return Map.of();
    }

    private String asText(Object value, String fallback) {
        if (value instanceof String text && !text.isBlank()) {
            return text;
        }
        return fallback;
    }

    private Integer toNullableInt(Object value) {
        if (value instanceof Number number) {
            return number.intValue();
        }
        if (value instanceof String text) {
            try {
                return Integer.parseInt(text);
            } catch (NumberFormatException ignored) {
                return null;
            }
        }
        return null;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> findStageResult(Map<String, Object> verification, String targetStage) {
        Object stagesValue = verification.get("stages");
        if (!(stagesValue instanceof List<?> stages)) {
            return Map.of();
        }
        for (Object item : stages) {
            if (!(item instanceof Map<?, ?> raw)) {
                continue;
            }
            Map<String, Object> stage = (Map<String, Object>) raw;
            if (!targetStage.equals(String.valueOf(stage.getOrDefault("stage", "")))) {
                continue;
            }
            return stage;
        }
        return Map.of();
    }

    private String sanitizeCode(String code) {
        if (code == null || code.isBlank()) {
            return "unknown_error";
        }
        return code.toLowerCase().replaceAll("[^a-z0-9_]+", "_");
    }

    private String sanitizeMessage(String message) {
        if (message == null || message.isBlank()) {
            return "Request failed.";
        }
        String sanitized = message
                .replaceAll("([A-Za-z]:\\\\[^\\s]+)", "[redacted_path]")
                .replaceAll("(/[^\\s]+)+", "[redacted_path]")
                .replaceAll("(AKIA|sk-|api[_-]?key|token|secret)[^\\s]*", "[redacted_secret]");
        return sanitized;
    }
}
