package com.sentinel.case006;

public class UserQueryBuilder {
    public String queryById(String userId) {
        return "select * from users where id=? :: " + userId;
    }
}
