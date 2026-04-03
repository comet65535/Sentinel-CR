package com.backendjava.mcp;

import com.backendjava.task.InMemoryTaskRepository;
import com.backendjava.task.ReviewTask;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import org.springframework.stereotype.Service;

@Service
public class McpToolService {
    private static final Set<String> SANDBOX_STAGES = Set.of("patch_apply", "compile", "lint", "test", "security_rescan");
    private static final Set<String> SANDBOX_ACTIONS = Set.of("validate", "run");

    private final InMemoryTaskRepository taskRepository;

    public McpToolService(InMemoryTaskRepository taskRepository) {
        this.taskRepository = taskRepository;
    }

    public McpEnvelope resolveSymbol(Map<String, Object> body) {
        long started = System.currentTimeMillis();
        ReviewTask task = findTask(String.valueOf(body.getOrDefault("taskId", "")));
        if (task == null) {
            return error("tool", "resolve-symbol", "task_not_found", "task not found", started);
        }
        return error(
                "tool",
                "resolve-symbol",
                "not_configured",
                "Symbol index is not configured for this task type.",
                started);
    }

    public McpEnvelope findReferences(Map<String, Object> body) {
        long started = System.currentTimeMillis();
        ReviewTask task = findTask(String.valueOf(body.getOrDefault("taskId", "")));
        if (task == null) {
            return error("tool", "find-references", "task_not_found", "task not found", started);
        }
        return error(
                "tool",
                "find-references",
                "not_configured",
                "Reference search is not configured for this task type.",
                started);
    }

    public McpEnvelope runAnalyzer(Map<String, Object> body) {
        long started = System.currentTimeMillis();
        if (findTask(String.valueOf(body.getOrDefault("taskId", ""))) == null) {
            return error("tool", "run-analyzer", "task_not_found", "task not found", started);
        }
        return error(
                "tool",
                "run-analyzer",
                "not_configured",
                "Analyzer execution via MCP tool is not configured.",
                started);
    }

    public McpEnvelope runSandbox(Map<String, Object> body) {
        long started = System.currentTimeMillis();
        ReviewTask task = findTask(String.valueOf(body.getOrDefault("taskId", "")));
        if (task == null) {
            return error("tool", "run-sandbox", "task_not_found", "task not found", started);
        }
        if (body.containsKey("command") || body.containsKey("shell") || body.containsKey("script")) {
            return error(
                    "tool",
                    "run-sandbox",
                    "invalid_request",
                    "Direct shell command execution is not allowed.",
                    started);
        }
        String stage = String.valueOf(body.getOrDefault("stage", "")).trim().toLowerCase();
        String action = String.valueOf(body.getOrDefault("action", "run")).trim().toLowerCase();
        if (!SANDBOX_STAGES.contains(stage)) {
            return error("tool", "run-sandbox", "invalid_stage", "Unsupported sandbox stage.", started);
        }
        if (!SANDBOX_ACTIONS.contains(action)) {
            return error("tool", "run-sandbox", "invalid_action", "Unsupported sandbox action.", started);
        }

        if (!stage.equals("patch_apply") && !stage.equals("compile")) {
            return error(
                    "tool",
                    "run-sandbox",
                    "not_configured",
                    "Sandbox stage is not configured for execution.",
                    started);
        }

        Map<String, Object> stageData = stageResult(
                stage,
                "passed",
                0,
                "Sandbox execution is controlled and mocked for snippet tasks.",
                "",
                null,
                false);
        stageData.put("action", action);
        stageData.put("task_status", task.getStatus().name());
        return ok("tool", "run-sandbox", stageData, started);
    }

    public McpEnvelope queryTests(Map<String, Object> body) {
        long started = System.currentTimeMillis();
        if (findTask(String.valueOf(body.getOrDefault("taskId", ""))) == null) {
            return error("tool", "query-tests", "task_not_found", "task not found", started);
        }
        return error(
                "tool",
                "query-tests",
                "not_configured",
                "Test discovery tool is not configured for this task type.",
                started);
    }

    private ReviewTask findTask(String taskId) {
        return taskRepository.findByTaskId(taskId).orElse(null);
    }

    private Map<String, Object> stageResult(
            String stage,
            String status,
            Integer exitCode,
            String stdoutSummary,
            String stderrSummary,
            String reason,
            boolean retryable) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("stage", stage);
        result.put("status", status);
        result.put("exit_code", exitCode);
        result.put("stdout_summary", stdoutSummary);
        result.put("stderr_summary", stderrSummary);
        result.put("reason", reason);
        result.put("retryable", retryable);
        return result;
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
        return message
                .replaceAll("([A-Za-z]:\\\\[^\\s]+)", "[redacted_path]")
                .replaceAll("(/[^\\s]+)+", "[redacted_path]")
                .replaceAll("(AKIA|sk-|api[_-]?key|token|secret)[^\\s]*", "[redacted_secret]");
    }
}
