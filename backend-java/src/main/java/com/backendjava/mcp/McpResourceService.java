package com.backendjava.mcp;

import com.backendjava.task.InMemoryTaskRepository;
import com.backendjava.task.ReviewTask;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Service;

@Service
public class McpResourceService {
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
        List<Map<String, Object>> entries = new ArrayList<>();
        entries.add(Map.of("path", "snippet.java", "kind", "file"));
        return ok("resource", "repo-tree", Map.of("root", "/workspace/" + task.getTaskId(), "entries", entries), started);
    }

    public McpEnvelope file(String taskId, String path, Integer startLine, Integer endLine) {
        long started = System.currentTimeMillis();
        ReviewTask task = findTask(taskId);
        if (task == null) {
            return error("resource", "file", "task_not_found", "task not found", started);
        }
        String targetPath = (path == null || path.isBlank()) ? "snippet.java" : path;
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
        data.put("path", targetPath);
        data.put("startLine", from);
        data.put("endLine", to);
        data.put("truncated", false);
        data.put("content", sb.toString());
        return ok("resource", "file", data, started);
    }

    public McpEnvelope schema(String taskId, String schemaType) {
        long started = System.currentTimeMillis();
        if (findTask(taskId) == null) {
            return error("resource", "schema", "task_not_found", "task not found", started);
        }
        return ok(
                "resource",
                "schema",
                Map.of(
                        "schemaType", schemaType == null || schemaType.isBlank() ? "api_contract" : schemaType,
                        "version", "day6.v1",
                        "summary", "Sentinel-CR Day6 schema summary"),
                started);
    }

    public McpEnvelope buildLogSummary(String taskId) {
        long started = System.currentTimeMillis();
        ReviewTask task = findTask(taskId);
        if (task == null) {
            return error("resource", "build-log-summary", "task_not_found", "task not found", started);
        }
        Map<String, Object> data = Map.of(
                "status", "available",
                "latest_build", Map.of(
                        "command", "javac snippet.java",
                        "exit_code", 0,
                        "stderr_summary", "",
                        "updated_at", Instant.now().toString(),
                        "task_status", task.getStatus().name()));
        return ok("resource", "build-log-summary", data, started);
    }

    public McpEnvelope testSummary(String taskId) {
        long started = System.currentTimeMillis();
        if (findTask(taskId) == null) {
            return error("resource", "test-summary", "task_not_found", "task not found", started);
        }
        return ok(
                "resource",
                "test-summary",
                Map.of(
                        "status", "available",
                        "suggested_test_commands", List.of("mvn -q -Dtest=SnippetTest test"),
                        "last_result", Map.of("passed", 0, "failed", 0, "skipped", 1)),
                started);
    }

    public McpEnvelope parsePrDiff(String taskId, Map<String, Object> body) {
        long started = System.currentTimeMillis();
        if (findTask(taskId) == null) {
            return error("resource", "pr-diff/parse", "task_not_found", "task not found", started);
        }
        String diffText = body == null ? "" : String.valueOf(body.getOrDefault("diff_text", ""));
        List<Map<String, Object>> changedFiles = new ArrayList<>();
        if (!diffText.isBlank()) {
            changedFiles.add(
                    Map.of(
                            "path", "snippet.java",
                            "hunks", List.of(Map.of("old_start", 1, "new_start", 1, "header", "@@ -1,1 +1,1 @@"))));
        }
        return ok("resource", "pr-diff/parse", Map.of("changed_files", changedFiles), started);
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
                Map.of("code", code, "message", message));
    }
}
