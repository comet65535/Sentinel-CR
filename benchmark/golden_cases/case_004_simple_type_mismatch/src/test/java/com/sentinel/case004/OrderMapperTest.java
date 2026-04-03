package com.sentinel.case004;

import org.junit.jupiter.api.Test;

public class OrderMapperTest {
    @Test
    void shouldMatchGoldenExpectation() throws Exception {
        org.junit.jupiter.api.Assertions.assertEquals(42, new OrderMapper().toId("42"));
    }
}
