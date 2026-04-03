package com.sentinel.case003;

import org.junit.jupiter.api.Test;

public class GreeterTest {
    @Test
    void shouldMatchGoldenExpectation() throws Exception {
        org.junit.jupiter.api.Assertions.assertEquals("Hi user", new Greeter().greet(false));
    }
}
