package com.backendjava.mcp;

import java.util.Map;

public record McpEnvelope(
        boolean ok,
        String kind,
        String name,
        String request_id,
        Object data,
        Map<String, Object> meta,
        Object error) {
}
