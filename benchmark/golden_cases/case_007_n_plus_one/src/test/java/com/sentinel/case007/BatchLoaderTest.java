package com.sentinel.case007;

import org.junit.jupiter.api.Test;

public class BatchLoaderTest {
    @Test
    void shouldMatchGoldenExpectation() throws Exception {
        org.junit.jupiter.api.Assertions.assertEquals(3, new BatchLoader().batchSize(java.util.List.of(1,2,3)));
    }
}
