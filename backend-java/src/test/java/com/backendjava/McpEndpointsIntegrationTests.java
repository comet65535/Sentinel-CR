package com.backendjava;

import static org.assertj.core.api.Assertions.assertThat;

import com.backendjava.api.dto.CreateReviewResponse;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.MediaType;
import org.springframework.test.web.reactive.server.WebTestClient;

@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = {"sentinel.ai.mode=mock"})
class McpEndpointsIntegrationTests {
    @LocalServerPort
    private int serverPort;

    @Test
    void shouldServeInternalMcpResourceAndToolEnvelopes() {
        WebTestClient webTestClient = WebTestClient.bindToServer()
                .baseUrl("http://localhost:" + serverPort)
                .responseTimeout(Duration.ofSeconds(10))
                .build();

        CreateReviewResponse createResponse = webTestClient.post()
                .uri("/api/reviews")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(Map.of(
                        "codeText", "public class Demo { }",
                        "language", "java",
                        "sourceType", "snippet"))
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody(CreateReviewResponse.class)
                .returnResult()
                .getResponseBody();

        assertThat(createResponse).isNotNull();
        String taskId = createResponse.taskId();

        Map<String, Object> repoTreeEnvelope = webTestClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path("/internal/mcp/resources/repo-tree")
                        .queryParam("taskId", taskId)
                        .build())
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody(Map.class)
                .returnResult()
                .getResponseBody();

        assertThat(repoTreeEnvelope).isNotNull();
        assertThat(repoTreeEnvelope).containsEntry("ok", false);
        assertThat(repoTreeEnvelope).containsEntry("kind", "resource");
        assertEnvelopeErrorCode(repoTreeEnvelope, "not_configured");

        Map<String, Object> fileEnvelope = webTestClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path("/internal/mcp/resources/file")
                        .queryParam("taskId", taskId)
                        .queryParam("path", "snippet.java")
                        .queryParam("startLine", 1)
                        .queryParam("endLine", 1)
                        .build())
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody(Map.class)
                .returnResult()
                .getResponseBody();
        assertThat(fileEnvelope).isNotNull();
        assertThat(fileEnvelope).containsEntry("ok", true);
        assertThat(fileEnvelope).containsEntry("name", "file");
        assertThat(fileEnvelope.get("data")).isInstanceOf(Map.class);

        Map<String, Object> invalidPathEnvelope = webTestClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path("/internal/mcp/resources/file")
                        .queryParam("taskId", taskId)
                        .queryParam("path", "../secrets.txt")
                        .build())
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody(Map.class)
                .returnResult()
                .getResponseBody();
        assertThat(invalidPathEnvelope).isNotNull();
        assertThat(invalidPathEnvelope).containsEntry("ok", false);
        assertEnvelopeErrorCode(invalidPathEnvelope, "access_denied");
        assertNoPathLeak(invalidPathEnvelope);

        Map<String, Object> schemaEnvelope = webTestClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path("/internal/mcp/resources/schema")
                        .queryParam("taskId", taskId)
                        .queryParam("schemaType", "api_contract")
                        .build())
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody(Map.class)
                .returnResult()
                .getResponseBody();
        assertThat(schemaEnvelope).isNotNull();
        assertThat(schemaEnvelope).containsEntry("ok", true);
        assertThat(schemaEnvelope).containsEntry("name", "schema");

        Map<String, Object> buildEnvelope = webTestClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path("/internal/mcp/resources/build-log-summary")
                        .queryParam("taskId", taskId)
                        .build())
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody(Map.class)
                .returnResult()
                .getResponseBody();
        assertThat(buildEnvelope).isNotNull();
        assertThat(buildEnvelope).containsEntry("ok", true);
        assertThat(buildEnvelope).containsEntry("name", "build-log-summary");

        Map<String, Object> testSummaryEnvelope = webTestClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path("/internal/mcp/resources/test-summary")
                        .queryParam("taskId", taskId)
                        .build())
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody(Map.class)
                .returnResult()
                .getResponseBody();
        assertThat(testSummaryEnvelope).isNotNull();
        assertThat(testSummaryEnvelope).containsEntry("ok", true);
        assertThat(testSummaryEnvelope).containsEntry("name", "test-summary");

        Map<String, Object> prDiffEnvelope = webTestClient.post()
                .uri("/internal/mcp/resources/pr-diff")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(Map.of("taskId", taskId, "diff_text", "diff --git a b"))
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody(Map.class)
                .returnResult()
                .getResponseBody();
        assertThat(prDiffEnvelope).isNotNull();
        assertThat(prDiffEnvelope).containsEntry("ok", false);
        assertEnvelopeErrorCode(prDiffEnvelope, "not_configured");

        Map<String, Object> sandboxEnvelope = webTestClient.post()
                .uri("/internal/mcp/tools/run-sandbox")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(Map.of("taskId", taskId, "stage", "compile", "action", "run"))
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody(Map.class)
                .returnResult()
                .getResponseBody();

        assertThat(sandboxEnvelope).isNotNull();
        assertThat(sandboxEnvelope).containsEntry("ok", true);
        assertThat(sandboxEnvelope).containsEntry("kind", "tool");
        assertThat(((Map<String, Object>) sandboxEnvelope.get("data")).get("status")).isEqualTo("passed");

        Map<String, Object> sandboxRejectedEnvelope = webTestClient.post()
                .uri("/internal/mcp/tools/run-sandbox")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(Map.of("taskId", taskId, "stage", "compile", "command", "whoami"))
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody(Map.class)
                .returnResult()
                .getResponseBody();
        assertThat(sandboxRejectedEnvelope).isNotNull();
        assertThat(sandboxRejectedEnvelope).containsEntry("ok", false);
        assertEnvelopeErrorCode(sandboxRejectedEnvelope, "invalid_request");
        assertNoPathLeak(sandboxRejectedEnvelope);

        List<String> toolEndpoints = List.of(
                "/internal/mcp/tools/resolve-symbol",
                "/internal/mcp/tools/find-references",
                "/internal/mcp/tools/run-analyzer",
                "/internal/mcp/tools/query-tests");
        for (String endpoint : toolEndpoints) {
            Map<String, Object> envelope = webTestClient.post()
                    .uri(endpoint)
                    .contentType(MediaType.APPLICATION_JSON)
                    .bodyValue(Map.of("taskId", taskId, "symbol", "Demo"))
                    .exchange()
                    .expectStatus()
                    .isOk()
                    .expectBody(Map.class)
                    .returnResult()
                    .getResponseBody();
            assertThat(envelope).isNotNull();
            assertThat(envelope).containsEntry("ok", false);
            assertEnvelopeErrorCode(envelope, "not_configured");
        }
    }

    @SuppressWarnings("unchecked")
    private void assertEnvelopeErrorCode(Map<String, Object> envelope, String expectedCode) {
        assertThat(envelope.get("error")).isInstanceOf(Map.class);
        Map<String, Object> error = (Map<String, Object>) envelope.get("error");
        assertThat(error.get("code")).isEqualTo(expectedCode);
        assertThat(error.get("message")).isInstanceOf(String.class);
    }

    @SuppressWarnings("unchecked")
    private void assertNoPathLeak(Map<String, Object> envelope) {
        Map<String, Object> error = (Map<String, Object>) envelope.get("error");
        String message = String.valueOf(error.getOrDefault("message", ""));
        assertThat(message).doesNotContain("G:\\");
        assertThat(message).doesNotContain("C:\\");
        assertThat(message).doesNotContain("/Users/");
    }
}
