package com.sentinel.case005;

public class UserService {
    public static class User {
        public Profile profile;
    }

    public static class Profile {
        public String name;
    }

    public String safeName(User user) {
        if (user == null || user.profile == null) { return ""; } return user.profile.name;
    }
}
