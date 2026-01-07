package com.app.entity;

import jakarta.persistence.*;
import lombok.Data;
import java.time.LocalDateTime;

@Entity
@Table(name = "users")
@Data
public class User {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "account", unique = true, nullable = false, length = 20)
    private String account;

    @Column(name = "password_hash", nullable = false, length = 255)
    private String passwordHash;

    @Enumerated(EnumType.STRING)
    @Column(name = "role", nullable = false, length = 20)
    private UserRole role = UserRole.普通用户;

    @Column(name = "nickname", length = 100)
    private String nickname;

    @Column(name = "signature", length = 500)
    private String signature;

    @Column(name = "avatar_path", length = 255)
    private String avatarPath = "/default.jpg";

    @Column(name = "security_question", length = 255)
    private String securityQuestion;

    @Column(name = "security_answer_hash", length = 255)
    private String securityAnswerHash;

    @Column(name = "is_online")
    private Boolean isOnline = false;

    @Column(name = "last_active_time")
    private LocalDateTime lastActiveTime;

    @Column(name = "created_at")
    private LocalDateTime createdAt;

    public enum UserRole {
        普通用户, 管理员, 超级管理员
    }
}

