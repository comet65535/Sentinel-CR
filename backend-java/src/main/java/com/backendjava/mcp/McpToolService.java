package com.backendjava.mcp;

import com.backendjava.task.InMemoryTaskRepository;
import com.backendjava.task.ReviewTask;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
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
        String symbol = String.valueOf(body.getOrDefault("symbol", body.getOrDefault("name", ""))).trim();
        if (symbol.isBlank()) {
            return error("tool", "resolve-symbol", "invalid_request", "symbol/name is required", started);
        }

        List<Map<String, Object>> matches = findSymbolOccurrences(task.getCodeText(), symbol, 20);
        return ok("tool", "resolve-symbol", Map.of("symbol", symbol, "matches", matches), started);
    }

    public McpEnvelope findReferences(Map<String, Object> body) {
        long started = System.currentTimeMillis();
        ReviewTask task = findTask(String.valueOf(body.getOrDefault("taskId", "")));
        if (task == null) {
            return error("tool", "find-references", "task_not_found", "task not found", started);
        }
        String symbol = String.valueOf(body.getOrDefault("symbol", body.getOrDefault("name", ""))).trim();
        if (symbol.isBlank()) {
            return error("tool", "find-references", "invalid_request", "symbol/name is required", started);
        }

        List<Map<String, Object>> refs = findSymbolOccurrences(task.getCodeText(), symbol, 100);
        return ok("tool", "find-references", Map.of("symbol", symbol, "references", refs), started);
    }

    public McpEnvelope runAnalyzer(Map<String, Object> body) {
        long started = System.currentTimeMillis();
        ReviewTask task = findTask(String.valueOf(body.getOrDefault("taskId", "")));
        if (task == null) {
            return error("tool", "run-analyzer", "task_not_found", "task not found", started);
        }
        String code = task.getCodeText() == null ? "" : task.getCodeText();
        int lineCount = code.isBlank() ? 0 : code.split("\\R", -1).length;
        int classCount = countRegex(code, "\\bclass\\s+[A-Za-z_][A-Za-z0-9_]*");
        int methodCount = countRegex(code, "\\b[A-Za-z_][A-Za-z0-9_<>\\[\\]]*\\s+[A-Za-z_][A-Za-z0-9_]*\\s*\\(");

        return ok(
                "tool",
                "run-analyzer",
                Map.of(
                        "status", "available",
                        "summary", Map.of(
                                "line_count", lineCount,
                                "class_count", classCount,
                                "method_count", Math.max(methodCount - classCount, 0))),
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

        if (stage.equals("patch_apply")) {
            String patch = String.valueOf(body.getOrDefault("patch", ""));
            boolean valid = patch.startsWith("diff --git a/") && patch.contains("--- a/") && patch.contains("+++ b/");
            Map<String, Object> stageData = stageResult(
                    stage,
                    valid ? "passed" : "failed",
                    valid ? 0 : 1,
                    valid ? "Patch format looks valid." : "",
                    valid ? "" : "Invalid unified diff format.",
                    valid ? null : "invalid_diff",
                    !valid);
            stageData.put("action", action);
            stageData.put("task_status", task.getStatus().name());
            return ok("tool", "run-sandbox", stageData, started);
        }

        if (stage.equals("compile")) {
            String codeText = String.valueOf(body.getOrDefault("codeText", task.getCodeText() == null ? "" : task.getCodeText()));
            Map<String, Object> compile = runCompile(codeText);
            compile.put("action", action);
            compile.put("task_status", task.getStatus().name());
            return ok("tool", "run-sandbox", compile, started);
        }

        return error(
                "tool",
                "run-sandbox",
                "not_configured",
                "Sandbox stage is not configured for execution.",
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
                        "status", "available",
                        "suggested", List.of("mvn -q test"),
                        "note", "Snippet task has no dedicated test files by default."),
                started);
    }

    private ReviewTask findTask(String taskId) {
        return taskRepository.findByTaskId(taskId).orElse(null);
    }

    private List<Map<String, Object>> findSymbolOccurrences(String codeText, String symbol, int limit) {
        List<Map<String, Object>> hits = new ArrayList<>();
        if (codeText == null || codeText.isBlank()) {
            return hits;
        }
        Pattern pattern = Pattern.compile("\\b" + Pattern.quote(symbol) + "\\b");
        String[] lines = codeText.split("\\R", -1);
        for (int i = 0; i < lines.length; i++) {
            Matcher matcher = pattern.matcher(lines[i]);
            while (matcher.find()) {
                Map<String, Object> hit = new LinkedHashMap<>();
                hit.put("line", i + 1);
                hit.put("column", matcher.start() + 1);
                hit.put("text", lines[i]);
                hits.add(hit);
                if (hits.size() >= limit) {
                    return hits;
                }
            }
        }
        return hits;
    }

    private int countRegex(String text, String regex) {
        Pattern pattern = Pattern.compile(regex);
        Matcher matcher = pattern.matcher(text == null ? "" : text);
        int count = 0;
        while (matcher.find()) {
            count++;
        }
        return count;
    }

    private Map<String, Object> runCompile(String codeText) {
        Path tempDir = null;
        try {
            tempDir = Files.createTempDirectory("sentinel-mcp-compile-");
            Path source = tempDir.resolve("snippet.java");
            Files.writeString(source, codeText == null ? "" : codeText, StandardCharsets.UTF_8);
            Process process = new ProcessBuilder("javac", "snippet.java")
                    .directory(tempDir.toFile())
                    .start();
            int exitCode = process.waitFor();
            String stdout = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
            String stderr = new String(process.getErrorStream().readAllBytes(), StandardCharsets.UTF_8);
            return stageResult(
                    "compile",
                    exitCode == 0 ? "passed" : "failed",
                    exitCode,
                    compact(stdout),
                    compact(stderr),
                    exitCode == 0 ? null : "compile_failed",
                    exitCode != 0);
        } catch (Exception ex) {
            return stageResult(
                    "compile",
                    "failed",
                    1,
                    "",
                    compact(ex.getMessage()),
                    "compile_exec_error",
                    true);
        } finally {
            if (tempDir != null) {
                try {
                    Files.walk(tempDir)
                            .sorted((a, b) -> b.getNameCount() - a.getNameCount())
                            .forEach(path -> {
                                try {
                                    Files.deleteIfExists(path);
                                } catch (IOException ignored) {
                                }
                            });
                } catch (IOException ignored) {
                }
            }
        }
    }

    private String compact(String text) {
        if (text == null || text.isBlank()) {
            return "";
        }
        String normalized = text.replace("\r", " ").replace("\n", " | ").trim();
        return normalized.length() > 500 ? normalized.substring(0, 497) + "..." : normalized;
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
