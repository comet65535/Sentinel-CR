package com.sentinel.case001;

import org.junit.jupiter.api.Test;

public class GreetingPolicyTest {
    @Test
    void shouldMatchGoldenExpectation() throws Exception {
        org.junit.jupiter.api.Assertions.assertEquals("unknown", new GreetingPolicy().resolve(0));
    }
}
