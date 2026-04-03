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
        properties = {"sentinel.ai.mode=mock"})
class ReviewApiIntegrationTests {
    @LocalServerPort
    private int serverPort;

    @Test
    void shouldCreateReviewAndStreamDay0Events() {
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

        List<ReviewEvent> events =
                streamResult.getResponseBody().take(4).collectList().block(Duration.ofSeconds(10));

        assertThat(events).isNotNull();
        assertThat(events).hasSizeGreaterThanOrEqualTo(4);
        assertThat(events).extracting(ReviewEvent::eventType)
                .containsExactly("task_created", "analysis_started", "analysis_completed", "review_completed");
        assertThat(events).extracting(ReviewEvent::sequence).containsExactly(1L, 2L, 3L, 4L);
        Map<String, Object> reviewCompletedPayload = events.get(3).payload();
        assertThat(reviewCompletedPayload).containsKey("result");

        ReviewTaskResponse taskResponse = webTestClient.get()
                .uri("/api/reviews/{taskId}", createResponse.taskId())
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody(ReviewTaskResponse.class)
                .returnResult()
                .getResponseBody();

        assertThat(taskResponse).isNotNull();
        assertThat(taskResponse.status()).isEqualTo(ReviewTaskStatus.COMPLETED);
        assertThat(taskResponse.result()).isEqualTo(reviewCompletedPayload.get("result"));
    }

    @Test
    void shouldReplayDay0EventsWhenSubscribedAfterTaskCompleted() throws InterruptedException {
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

        Thread.sleep(3500);

        FluxExchangeResult<ReviewEvent> streamResult = webTestClient.get()
                .uri("/api/reviews/{taskId}/events", createResponse.taskId())
                .accept(MediaType.TEXT_EVENT_STREAM)
                .exchange()
                .expectStatus()
                .isOk()
                .returnResult(ReviewEvent.class);

        List<ReviewEvent> events =
                streamResult.getResponseBody().take(4).collectList().block(Duration.ofSeconds(5));

        assertThat(events).isNotNull();
        assertThat(events).hasSize(4);
        assertThat(events).extracting(ReviewEvent::eventType)
                .containsExactly("task_created", "analysis_started", "analysis_completed", "review_completed");
        assertThat(events).extracting(ReviewEvent::sequence).containsExactly(1L, 2L, 3L, 4L);
        assertThat(events.get(3).status()).isEqualTo(ReviewTaskStatus.COMPLETED);
    }

    @Test
    void shouldListReviewHistoryWithRequiredFields() {
        WebTestClient webTestClient = WebTestClient.bindToServer()
                .baseUrl("http://localhost:" + serverPort)
                .responseTimeout(Duration.ofSeconds(10))
                .build();

        webTestClient.post()
                .uri("/api/reviews")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(Map.of(
                        "codeText", "public class HistoryDemo { }",
                        "language", "java",
                        "sourceType", "snippet"))
                .exchange()
                .expectStatus()
                .isOk();

        List<Map> historyItems = webTestClient.get()
                .uri(uriBuilder -> uriBuilder.path("/api/reviews").queryParam("limit", 20).build())
                .exchange()
                .expectStatus()
                .isOk()
                .expectBodyList(Map.class)
                .returnResult()
                .getResponseBody();

        assertThat(historyItems).isNotNull();
        assertThat(historyItems).isNotEmpty();

        @SuppressWarnings("unchecked")
        Map<String, Object> item = (Map<String, Object>) historyItems.get(0);
        assertThat(item).containsKeys(
                "task_id",
                "status",
                "created_at",
                "updated_at",
                "title",
                "input_kind",
                "summary",
                "has_patch");
        assertThat(item.get("summary")).isInstanceOf(Map.class);
        @SuppressWarnings("unchecked")
        Map<String, Object> summary = (Map<String, Object>) item.get("summary");
        assertThat(summary).containsKeys("final_status", "verified_level", "failure_taxonomy");
        assertThat(summary.get("failure_taxonomy")).isInstanceOf(Map.class);
    }
}
