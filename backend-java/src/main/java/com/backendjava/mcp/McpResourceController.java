package com.backendjava.mcp;

import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/internal/mcp/resources")
public class McpResourceController {
    private final McpResourceService resourceService;

    public McpResourceController(McpResourceService resourceService) {
        this.resourceService = resourceService;
    }

    @GetMapping("/repo-tree")
    public McpEnvelope repoTree(
            @RequestParam String taskId,
            @RequestParam(required = false) Integer depth) {
        return resourceService.repoTree(taskId, depth);
    }

    @GetMapping("/file")
    public McpEnvelope file(
            @RequestParam String taskId,
            @RequestParam String path,
            @RequestParam(required = false) Integer startLine,
            @RequestParam(required = false) Integer endLine) {
        return resourceService.file(taskId, path, startLine, endLine);
    }

    @GetMapping("/schema")
    public McpEnvelope schema(
            @RequestParam String taskId,
            @RequestParam(required = false) String schemaType) {
        return resourceService.schema(taskId, schemaType);
    }

    @GetMapping("/build-log-summary")
    public McpEnvelope buildLogSummary(@RequestParam String taskId) {
        return resourceService.buildLogSummary(taskId);
    }

    @GetMapping("/test-summary")
    public McpEnvelope testSummary(@RequestParam String taskId) {
        return resourceService.testSummary(taskId);
    }

    @PostMapping("/pr-diff/parse")
    public McpEnvelope parsePrDiff(@RequestBody(required = false) Map<String, Object> body) {
        Map<String, Object> safeBody = body == null ? Map.of() : body;
        return resourceService.parsePrDiff(String.valueOf(safeBody.getOrDefault("taskId", "")), safeBody);
    }
}
