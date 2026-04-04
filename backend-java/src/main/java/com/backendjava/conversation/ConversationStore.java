package com.backendjava.conversation;

import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.ObjectMapper;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Repository;

@Repository
public class ConversationStore {
    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {};

    private final String jdbcUrl;
    private final ObjectMapper objectMapper;

    public ConversationStore(
            @Value("${sentinel.state.db-path:data/state/sentinel.db}") String dbPath,
            ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
        this.jdbcUrl = "jdbc:sqlite:" + Path.of(dbPath).toAbsolutePath();
        ensureParentDirectory(dbPath);
        initializeSchema();
    }

    public String createConversation(String title) {
        String conversationId = "conv_" + UUID.randomUUID().toString().replace("-", "").substring(0, 12);
        Instant now = Instant.now();
        String sql = """
                INSERT INTO conversations(conversation_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """;
        try (Connection connection = openConnection();
             PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, conversationId);
            statement.setString(2, title == null || title.isBlank() ? "New Conversation" : title);
            statement.setString(3, now.toString());
            statement.setString(4, now.toString());
            statement.executeUpdate();
        } catch (SQLException ex) {
            throw new IllegalStateException("failed to create conversation", ex);
        }
        return conversationId;
    }

    public void ensureConversation(String conversationId, String title) {
        String sql = """
                INSERT INTO conversations(conversation_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(conversation_id) DO UPDATE SET
                    title = COALESCE(NULLIF(excluded.title, ''), conversations.title),
                    updated_at = excluded.updated_at
                """;
        Instant now = Instant.now();
        try (Connection connection = openConnection();
             PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, conversationId);
            statement.setString(2, title == null || title.isBlank() ? "New Conversation" : title);
            statement.setString(3, now.toString());
            statement.setString(4, now.toString());
            statement.executeUpdate();
        } catch (SQLException ex) {
            throw new IllegalStateException("failed to upsert conversation", ex);
        }
    }

    public String addMessage(
            String conversationId,
            String parentMessageId,
            String role,
            String messageText,
            String codeText,
            String taskId,
            String messageId) {
        String resolvedMessageId =
                (messageId == null || messageId.isBlank())
                        ? "msg_" + UUID.randomUUID().toString().replace("-", "").substring(0, 12)
                        : messageId;
        String sql = """
                INSERT INTO messages(message_id, conversation_id, parent_message_id, role, message_text, code_text, task_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """;
        try (Connection connection = openConnection();
             PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, resolvedMessageId);
            statement.setString(2, conversationId);
            statement.setString(3, parentMessageId);
            statement.setString(4, role);
            statement.setString(5, messageText);
            statement.setString(6, codeText);
            statement.setString(7, taskId);
            statement.setString(8, Instant.now().toString());
            statement.executeUpdate();
        } catch (SQLException ex) {
            throw new IllegalStateException("failed to add message", ex);
        }
        touchConversation(conversationId);
        return resolvedMessageId;
    }

    public List<Map<String, Object>> listConversations(int limit) {
        String sql = """
                SELECT c.conversation_id, c.title, c.created_at, c.updated_at,
                       m.message_text AS latest_message,
                       m.task_id AS latest_task_id
                FROM conversations c
                LEFT JOIN messages m ON m.message_id = (
                    SELECT m2.message_id
                    FROM messages m2
                    WHERE m2.conversation_id = c.conversation_id
                    ORDER BY m2.created_at DESC
                    LIMIT 1
                )
                ORDER BY c.updated_at DESC
                LIMIT ?
                """;
        List<Map<String, Object>> results = new ArrayList<>();
        try (Connection connection = openConnection();
             PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setInt(1, Math.max(1, Math.min(limit, 500)));
            try (ResultSet rs = statement.executeQuery()) {
                while (rs.next()) {
                    Map<String, Object> row = new HashMap<>();
                    row.put("conversation_id", rs.getString("conversation_id"));
                    row.put("title", rs.getString("title"));
                    row.put("created_at", rs.getString("created_at"));
                    row.put("updated_at", rs.getString("updated_at"));
                    row.put("latest_message", rs.getString("latest_message"));
                    row.put("latest_task_id", rs.getString("latest_task_id"));
                    results.add(row);
                }
            }
        } catch (SQLException ex) {
            throw new IllegalStateException("failed to list conversations", ex);
        }
        return results;
    }

    public List<Map<String, Object>> listMessages(String conversationId, int limit) {
        String sql = """
                SELECT message_id, conversation_id, parent_message_id, role, message_text, code_text, task_id, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
                LIMIT ?
                """;
        List<Map<String, Object>> results = new ArrayList<>();
        try (Connection connection = openConnection();
             PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, conversationId);
            statement.setInt(2, Math.max(1, Math.min(limit, 2000)));
            try (ResultSet rs = statement.executeQuery()) {
                while (rs.next()) {
                    Map<String, Object> row = new HashMap<>();
                    row.put("message_id", rs.getString("message_id"));
                    row.put("conversation_id", rs.getString("conversation_id"));
                    row.put("parent_message_id", rs.getString("parent_message_id"));
                    row.put("role", rs.getString("role"));
                    row.put("message_text", rs.getString("message_text"));
                    row.put("code_text", rs.getString("code_text"));
                    row.put("task_id", rs.getString("task_id"));
                    row.put("created_at", rs.getString("created_at"));
                    results.add(row);
                }
            }
        } catch (SQLException ex) {
            throw new IllegalStateException("failed to list messages", ex);
        }
        return results;
    }

    public Map<String, Object> getThreadState(String conversationId) {
        String sql = """
                SELECT latest_code, latest_patch, latest_verifier_failure, short_term_memory, repo_profile_id, repo_id, updated_at
                FROM thread_state
                WHERE conversation_id = ?
                """;
        try (Connection connection = openConnection();
             PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, conversationId);
            try (ResultSet rs = statement.executeQuery()) {
                if (!rs.next()) {
                    return Map.of();
                }
                Map<String, Object> row = new HashMap<>();
                row.put("latest_code", rs.getString("latest_code"));
                row.put("latest_patch", readJsonMap(rs.getString("latest_patch")));
                row.put("latest_verifier_failure", readJsonMap(rs.getString("latest_verifier_failure")));
                row.put("short_term_memory", readJsonMap(rs.getString("short_term_memory")));
                row.put("repo_profile_id", rs.getString("repo_profile_id"));
                row.put("repo_id", rs.getString("repo_id"));
                row.put("updated_at", rs.getString("updated_at"));
                return row;
            }
        } catch (SQLException ex) {
            throw new IllegalStateException("failed to read thread_state", ex);
        }
    }

    public void upsertThreadState(
            String conversationId,
            String latestCode,
            Map<String, Object> latestPatch,
            Map<String, Object> latestVerifierFailure,
            Map<String, Object> shortTermMemory,
            String repoProfileId,
            String repoId) {
        String sql = """
                INSERT INTO thread_state(
                    conversation_id, latest_code, latest_patch, latest_verifier_failure, short_term_memory,
                    repo_profile_id, repo_id, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(conversation_id) DO UPDATE SET
                    latest_code = excluded.latest_code,
                    latest_patch = excluded.latest_patch,
                    latest_verifier_failure = excluded.latest_verifier_failure,
                    short_term_memory = excluded.short_term_memory,
                    repo_profile_id = excluded.repo_profile_id,
                    repo_id = excluded.repo_id,
                    updated_at = excluded.updated_at
                """;
        try (Connection connection = openConnection();
             PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, conversationId);
            statement.setString(2, latestCode);
            statement.setString(3, writeJson(latestPatch));
            statement.setString(4, writeJson(latestVerifierFailure));
            statement.setString(5, writeJson(shortTermMemory));
            statement.setString(6, repoProfileId);
            statement.setString(7, repoId);
            statement.setString(8, Instant.now().toString());
            statement.executeUpdate();
        } catch (SQLException ex) {
            throw new IllegalStateException("failed to upsert thread_state", ex);
        }
        touchConversation(conversationId);
    }

    public void appendEventLog(String taskId, String conversationId, long sequence, String eventType, Map<String, Object> payload) {
        String sql = """
                INSERT INTO event_log(task_id, conversation_id, sequence, event_type, payload, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """;
        try (Connection connection = openConnection();
             PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, taskId);
            statement.setString(2, conversationId);
            statement.setLong(3, sequence);
            statement.setString(4, eventType);
            statement.setString(5, writeJson(payload));
            statement.setString(6, Instant.now().toString());
            statement.executeUpdate();
        } catch (SQLException ex) {
            throw new IllegalStateException("failed to append event_log", ex);
        }
    }

    public void appendPatchHistory(String taskId, String conversationId, Map<String, Object> patch, Map<String, Object> verification) {
        String sql = """
                INSERT INTO patch_history(task_id, conversation_id, patch_id, patch_content, verification, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """;
        try (Connection connection = openConnection();
             PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, taskId);
            statement.setString(2, conversationId);
            statement.setString(3, patch == null ? null : String.valueOf(patch.getOrDefault("patch_id", "")));
            statement.setString(4, writeJson(patch));
            statement.setString(5, writeJson(verification));
            statement.setString(6, Instant.now().toString());
            statement.executeUpdate();
        } catch (SQLException ex) {
            throw new IllegalStateException("failed to append patch_history", ex);
        }
    }

    private void touchConversation(String conversationId) {
        String sql = "UPDATE conversations SET updated_at = ? WHERE conversation_id = ?";
        try (Connection connection = openConnection();
             PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, Instant.now().toString());
            statement.setString(2, conversationId);
            statement.executeUpdate();
        } catch (SQLException ex) {
            throw new IllegalStateException("failed to touch conversation", ex);
        }
    }

    private Connection openConnection() throws SQLException {
        Connection connection = DriverManager.getConnection(jdbcUrl);
        try (Statement statement = connection.createStatement()) {
            statement.execute("PRAGMA journal_mode=WAL");
            statement.execute("PRAGMA synchronous=NORMAL");
        }
        return connection;
    }

    private void initializeSchema() {
        try (Connection connection = openConnection(); Statement statement = connection.createStatement()) {
            statement.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        conversation_id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """);
            statement.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        message_id TEXT PRIMARY KEY,
                        conversation_id TEXT NOT NULL,
                        parent_message_id TEXT,
                        role TEXT NOT NULL,
                        message_text TEXT,
                        code_text TEXT,
                        task_id TEXT,
                        created_at TEXT NOT NULL
                    )
                    """);
            statement.execute("""
                    CREATE TABLE IF NOT EXISTS thread_state (
                        conversation_id TEXT PRIMARY KEY,
                        latest_code TEXT,
                        latest_patch TEXT,
                        latest_verifier_failure TEXT,
                        short_term_memory TEXT,
                        repo_profile_id TEXT,
                        repo_id TEXT,
                        updated_at TEXT NOT NULL
                    )
                    """);
            statement.execute("""
                    CREATE TABLE IF NOT EXISTS event_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task_id TEXT NOT NULL,
                        conversation_id TEXT,
                        sequence INTEGER,
                        event_type TEXT,
                        payload TEXT,
                        created_at TEXT NOT NULL
                    )
                    """);
            statement.execute("""
                    CREATE TABLE IF NOT EXISTS patch_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task_id TEXT NOT NULL,
                        conversation_id TEXT,
                        patch_id TEXT,
                        patch_content TEXT,
                        verification TEXT,
                        created_at TEXT NOT NULL
                    )
                    """);
            statement.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at)");
            statement.execute("CREATE INDEX IF NOT EXISTS idx_event_log_task ON event_log(task_id, sequence)");
        } catch (SQLException ex) {
            throw new IllegalStateException("failed to initialize sqlite schema", ex);
        }
    }

    private void ensureParentDirectory(String dbPath) {
        try {
            Path parent = Path.of(dbPath).toAbsolutePath().getParent();
            if (parent != null) {
                Files.createDirectories(parent);
            }
        } catch (Exception ex) {
            throw new IllegalStateException("failed to create database directory", ex);
        }
    }

    private String writeJson(Map<String, Object> value) {
        if (value == null || value.isEmpty()) {
            return "{}";
        }
        try {
            return objectMapper.writeValueAsString(value);
        } catch (Exception ex) {
            return "{}";
        }
    }

    private Map<String, Object> readJsonMap(String value) {
        if (value == null || value.isBlank()) {
            return Map.of();
        }
        try {
            Map<String, Object> parsed = objectMapper.readValue(value, MAP_TYPE);
            return parsed == null ? Map.of() : parsed;
        } catch (Exception ex) {
            return Map.of();
        }
    }
}
