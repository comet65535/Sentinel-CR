package com.sentinel.case005;

import org.junit.jupiter.api.Test;

public class UserServiceTest {
    @Test
    void shouldMatchGoldenExpectation() throws Exception {
        org.junit.jupiter.api.Assertions.assertEquals("", new UserService().safeName(null));
    }
}
