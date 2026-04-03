package com.backendjava;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.backendjava.engine.EngineEvent;
import com.backendjava.engine.EngineEventMapper;
import com.backendjava.engine.PythonAiEngineAdapter;
import com.backendjava.engine.PythonEngineProperties;
import com.backendjava.task.ReviewTask;
import com.backendjava.task.ReviewTaskStatus;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;

class PythonAiEngineAdapterTests {

    @Test
    void shouldMapNdjsonEventsFromPythonEngine() throws Exception {
        AtomicReference<String> capturedBody = new AtomicReference<>();
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/internal/reviews/run", exchange -> {
            if (!"POST".equalsIgnoreCase(exchange.getRequestMethod())) {
                exchange.sendResponseHeaders(405, -1);
                exchange.close();
                return;
            }
            capturedBody.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));

            String ndjson = String.join(
                            "\n",
                            "{\"taskId\":\"rev_test_001\",\"eventType\":\"analysis_started\",\"message\":\"python engine started state graph\",\"status\":\"RUNNING\",\"payload\":{\"source\":\"python-engine\",\"stage\":\"bootstrap_state\"}}",
                            "{\"taskId\":\"rev_test_001\",\"eventType\":\"analysis_completed\",\"message\":\"python analysis stub completed\",\"status\":\"RUNNING\",\"payload\":{\"source\":\"python-engine\",\"stage\":\"run_analysis_stub\"}}",
                            "{\"taskId\":\"rev_test_001\",\"eventType\":\"review_completed\",\"message\":\"review completed\",\"status\":\"COMPLETED\",\"payload\":{\"source\":\"python-engine\",\"stage\":\"finalize_result\",\"result\":{\"summary\":\"ok\"}}}")
                    + "\n";

            byte[] body = ndjson.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/x-ndjson");
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        server.start();

        try {
            PythonEngineProperties properties = new PythonEngineProperties();
            properties.setMode("python");
            properties.setPythonBaseUrl("http://127.0.0.1:" + server.getAddress().getPort());
            properties.setPythonConnectTimeoutMs(1000);
            properties.setPythonReadTimeoutMs(3000);

            PythonAiEngineAdapter adapter = new PythonAiEngineAdapter(properties, new EngineEventMapper());
            ReviewTask task = new ReviewTask(
                    "rev_test_001",
                    "public class Demo {}",
                    "java",
                    "snippet",
                    Map.of("enable_verifier", true, "enable_mcp", true, "max_retries", 2),
                    Map.of("requested_by", "backend-java-test", "debug_mode", true));

            List<EngineEvent> events =
                    adapter.startReview(task).collectList().block(Duration.ofSeconds(5));

            assertThat(events).isNotNull();
            assertThat(events).hasSize(3);
            assertThat(events).extracting(EngineEvent::eventType)
                    .containsExactly("analysis_started", "analysis_completed", "review_completed");
            assertThat(events.get(2).status()).isEqualTo(ReviewTaskStatus.COMPLETED);
            assertThat(events.get(0).payload()).containsEntry("source", "python-engine");

            assertThat(capturedBody.get()).contains("\"options\"");
            assertThat(capturedBody.get()).contains("\"enable_verifier\":true");
            assertThat(capturedBody.get()).contains("\"enable_mcp\":true");
            assertThat(capturedBody.get()).contains("\"max_retries\":2");
            assertThat(capturedBody.get()).contains("\"metadata\"");
            assertThat(capturedBody.get()).contains("\"requested_by\":\"backend-java-test\"");
            assertThat(capturedBody.get()).contains("\"debug_mode\":true");
        } finally {
            server.stop(0);
        }
    }

    @Test
    void shouldRaiseErrorWhenPythonEngineIsUnreachable() {
        PythonEngineProperties properties = new PythonEngineProperties();
        properties.setMode("python");
        properties.setPythonBaseUrl("http://127.0.0.1:1");
        properties.setPythonConnectTimeoutMs(150);
        properties.setPythonReadTimeoutMs(150);

        PythonAiEngineAdapter adapter = new PythonAiEngineAdapter(properties, new EngineEventMapper());
        ReviewTask task = new ReviewTask("rev_unreachable_001", "public class Demo {}", "java", "snippet");

        assertThatThrownBy(() -> adapter.startReview(task).collectList().block(Duration.ofSeconds(3)))
                .isInstanceOf(RuntimeException.class);
    }

    @Test
    void shouldAllowSlowNdjsonStreamWhenReadTimeoutDisabled() throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/internal/reviews/run", exchange -> {
            if (!"POST".equalsIgnoreCase(exchange.getRequestMethod())) {
                exchange.sendResponseHeaders(405, -1);
                exchange.close();
                return;
            }

            exchange.getResponseHeaders().add("Content-Type", "application/x-ndjson");
            exchange.sendResponseHeaders(200, 0);

            try {
                Thread.sleep(300);
                exchange.getResponseBody()
                        .write(("{\"taskId\":\"rev_slow_stream\",\"eventType\":\"analysis_started\",\"message\":\"started\",\"status\":\"RUNNING\",\"payload\":{}}\n")
                                .getBytes(StandardCharsets.UTF_8));
                exchange.getResponseBody().flush();

                Thread.sleep(300);
                exchange.getResponseBody()
                        .write(("{\"taskId\":\"rev_slow_stream\",\"eventType\":\"review_completed\",\"message\":\"done\",\"status\":\"COMPLETED\",\"payload\":{\"result\":{\"summary\":\"ok\"}}}\n")
                                .getBytes(StandardCharsets.UTF_8));
                exchange.getResponseBody().flush();
            } catch (InterruptedException interruptedException) {
                Thread.currentThread().interrupt();
            } finally {
                exchange.close();
            }
        });
        server.start();

        try {
            PythonEngineProperties properties = new PythonEngineProperties();
            properties.setMode("python");
            properties.setPythonBaseUrl("http://127.0.0.1:" + server.getAddress().getPort());
            properties.setPythonConnectTimeoutMs(1000);
            properties.setPythonReadTimeoutMs(0);

            PythonAiEngineAdapter adapter = new PythonAiEngineAdapter(properties, new EngineEventMapper());
            ReviewTask task = new ReviewTask("rev_slow_stream", "public class Demo {}", "java", "snippet");

            List<EngineEvent> events = adapter.startReview(task).collectList().block(Duration.ofSeconds(5));
            assertThat(events).isNotNull();
            assertThat(events).extracting(EngineEvent::eventType)
                    .containsExactly("analysis_started", "review_completed");
            assertThat(events.get(1).status()).isEqualTo(ReviewTaskStatus.COMPLETED);
        } finally {
            server.stop(0);
        }
    }
}
