package com.sentinel.case006;

import org.junit.jupiter.api.Test;

public class UserQueryBuilderTest {
    @Test
    void shouldMatchGoldenExpectation() throws Exception {
        org.junit.jupiter.api.Assertions.assertTrue(new UserQueryBuilder().queryById("1").contains("?"));
    }
}
