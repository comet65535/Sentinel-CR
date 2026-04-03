package com.backendjava.mcp;

import java.util.Map;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/internal/mcp/tools")
public class McpToolController {
    private final McpToolService toolService;

    public McpToolController(McpToolService toolService) {
        this.toolService = toolService;
    }

    @PostMapping("/resolve-symbol")
    public McpEnvelope resolveSymbol(@RequestBody(required = false) Map<String, Object> body) {
        return toolService.resolveSymbol(body == null ? Map.of() : body);
    }

    @PostMapping("/find-references")
    public McpEnvelope findReferences(@RequestBody(required = false) Map<String, Object> body) {
        return toolService.findReferences(body == null ? Map.of() : body);
    }

    @PostMapping("/run-analyzer")
    public McpEnvelope runAnalyzer(@RequestBody(required = false) Map<String, Object> body) {
        return toolService.runAnalyzer(body == null ? Map.of() : body);
    }

    @PostMapping("/run-sandbox")
    public McpEnvelope runSandbox(@RequestBody(required = false) Map<String, Object> body) {
        return toolService.runSandbox(body == null ? Map.of() : body);
    }

    @PostMapping("/query-tests")
    public McpEnvelope queryTests(@RequestBody(required = false) Map<String, Object> body) {
        return toolService.queryTests(body == null ? Map.of() : body);
    }
}
