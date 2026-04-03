package com.backendjava;

import static org.assertj.core.api.Assertions.assertThat;

import com.backendjava.api.dto.CreateReviewResponse;
import java.time.Duration;
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
        assertThat(repoTreeEnvelope).containsEntry("ok", true);
        assertThat(repoTreeEnvelope).containsEntry("kind", "resource");
        assertThat(repoTreeEnvelope.get("data")).isInstanceOf(Map.class);

        Map<String, Object> sandboxEnvelope = webTestClient.post()
                .uri("/internal/mcp/tools/run-sandbox")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(Map.of("taskId", taskId, "stage", "compile"))
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody(Map.class)
                .returnResult()
                .getResponseBody();

        assertThat(sandboxEnvelope).isNotNull();
        assertThat(sandboxEnvelope).containsEntry("ok", true);
        assertThat(sandboxEnvelope).containsEntry("kind", "tool");
        assertThat(((Map<String, Object>) sandboxEnvelope.get("data")).get("status")).isEqualTo("skipped");
    }
}
