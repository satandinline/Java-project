package com.cultural.entity;

import lombok.Data;
import java.time.LocalDateTime;

/**
 * 用户实体类
 */
@Data
public class User {
    private Long id;
    private String account;
    private String passwordHash;
    private String role; // 普通用户 或 管理员
    private String nickname;
    private String signature;
    private String avatarPath;
    private String securityQuestion;
    private String securityAnswerHash;
    private LocalDateTime createdAt;
}

