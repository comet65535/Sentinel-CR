package com.backendjava.mcp;

import com.backendjava.task.InMemoryTaskRepository;
import com.backendjava.task.ReviewTask;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Service;

@Service
public class McpToolService {
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
        String symbol = String.valueOf(body.getOrDefault("symbol", ""));
        int line = findLine(task.getCodeText(), symbol);
        return ok(
                "tool",
                "resolve-symbol",
                Map.of("definitions", List.of(Map.of("path", "snippet.java", "line", line, "kind", "method"))),
                started);
    }

    public McpEnvelope findReferences(Map<String, Object> body) {
        long started = System.currentTimeMillis();
        ReviewTask task = findTask(String.valueOf(body.getOrDefault("taskId", "")));
        if (task == null) {
            return error("tool", "find-references", "task_not_found", "task not found", started);
        }
        String symbol = String.valueOf(body.getOrDefault("symbol", ""));
        List<Map<String, Object>> refs = new ArrayList<>();
        String[] lines = task.getCodeText().split("\\R");
        for (int i = 0; i < lines.length; i++) {
            if (!symbol.isBlank() && lines[i].contains(symbol)) {
                refs.add(Map.of("path", "snippet.java", "line", i + 1, "kind", "call"));
            }
        }
        return ok("tool", "find-references", Map.of("references", refs), started);
    }

    public McpEnvelope runAnalyzer(Map<String, Object> body) {
        long started = System.currentTimeMillis();
        if (findTask(String.valueOf(body.getOrDefault("taskId", ""))) == null) {
            return error("tool", "run-analyzer", "task_not_found", "task not found", started);
        }
        return ok("tool", "run-analyzer", Map.of("issues", List.of(), "symbols", List.of(), "summary", Map.of()), started);
    }

    public McpEnvelope runSandbox(Map<String, Object> body) {
        long started = System.currentTimeMillis();
        if (findTask(String.valueOf(body.getOrDefault("taskId", ""))) == null) {
            return error("tool", "run-sandbox", "task_not_found", "task not found", started);
        }
        String stage = String.valueOf(body.getOrDefault("stage", "sandbox"));
        String command = String.valueOf(body.getOrDefault("command", ""));
        String workingDirectory = String.valueOf(body.getOrDefault("working_directory", ""));
        if (command.isBlank() || workingDirectory.isBlank()) {
            return ok(
                    "tool",
                    "run-sandbox",
                    stageResult(stage, "skipped", null, "", "", "not_applicable", false),
                    started);
        }
        return ok(
                "tool",
                "run-sandbox",
                stageResult(stage, "passed", 0, "sandbox command execution is mocked in day6", "", null, false),
                started);
    }

    public McpEnvelope queryTests(Map<String, Object> body) {
        long started = System.currentTimeMillis();
        if (findTask(String.valueOf(body.getOrDefault("taskId", ""))) == null) {
            return error("tool", "query-tests", "task_not_found", "task not found", started);
        }
        return ok(
                "tool",
                "query-tests",
                Map.of(
                        "suggested_tests", List.of("SnippetTest"),
                        "commands", List.of("mvn -q -Dtest=SnippetTest test")),
                started);
    }

    private ReviewTask findTask(String taskId) {
        return taskRepository.findByTaskId(taskId).orElse(null);
    }

    private int findLine(String codeText, String keyword) {
        if (keyword == null || keyword.isBlank()) {
            return 1;
        }
        String[] lines = codeText.split("\\R");
        for (int i = 0; i < lines.length; i++) {
            if (lines[i].contains(keyword)) {
                return i + 1;
            }
        }
        return 1;
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
                Map.of("code", code, "message", message));
    }
}
