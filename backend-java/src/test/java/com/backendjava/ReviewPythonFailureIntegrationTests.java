package com.backendjava;

import static org.assertj.core.api.Assertions.assertThat;

import com.backendjava.api.dto.CreateReviewResponse;
import com.backendjava.api.dto.ReviewTaskResponse;
import com.backendjava.event.ReviewEvent;
import com.backendjava.task.ReviewTaskStatus;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.MediaType;
import org.springframework.test.web.reactive.server.FluxExchangeResult;
import org.springframework.test.web.reactive.server.WebTestClient;

@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = {
            "sentinel.ai.mode=python",
            "sentinel.ai.python-base-url=http://127.0.0.1:1",
            "sentinel.ai.python-connect-timeout-ms=200",
            "sentinel.ai.python-read-timeout-ms=200"
        })
class ReviewPythonFailureIntegrationTests {
    @LocalServerPort
    private int serverPort;

    @Test
    void shouldFailTaskWhenPythonEngineUnavailable() {
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
        assertThat(createResponse.taskId()).isNotBlank();

        FluxExchangeResult<ReviewEvent> streamResult = webTestClient.get()
                .uri("/api/reviews/{taskId}/events", createResponse.taskId())
                .accept(MediaType.TEXT_EVENT_STREAM)
                .exchange()
                .expectStatus()
                .isOk()
                .returnResult(ReviewEvent.class);

        List<ReviewEvent> events = streamResult.getResponseBody()
                .takeUntil(event -> "review_failed".equals(event.eventType()))
                .collectList()
                .block(Duration.ofSeconds(10));

        assertThat(events).isNotNull();
        assertThat(events).isNotEmpty();
        assertThat(events).extracting(ReviewEvent::eventType).contains("task_created", "review_failed");

        ReviewTaskResponse taskResponse = webTestClient.get()
                .uri("/api/reviews/{taskId}", createResponse.taskId())
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody(ReviewTaskResponse.class)
                .returnResult()
                .getResponseBody();

        assertThat(taskResponse).isNotNull();
        assertThat(taskResponse.status()).isEqualTo(ReviewTaskStatus.FAILED);
        assertThat(taskResponse.errorMessage()).isNotBlank();
    }
}
