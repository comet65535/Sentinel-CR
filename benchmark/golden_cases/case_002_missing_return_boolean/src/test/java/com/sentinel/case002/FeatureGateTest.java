package com.sentinel.case002;

import org.junit.jupiter.api.Test;

public class FeatureGateTest {
    @Test
    void shouldMatchGoldenExpectation() throws Exception {
        org.junit.jupiter.api.Assertions.assertFalse(new FeatureGate().enabled("base"));
    }
}
