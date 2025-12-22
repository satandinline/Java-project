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
    private String role; // 普通用户、管理员 或 超级管理员
    private String nickname;
    private String signature;
    private String avatarPath;
    private String securityQuestion;
    private String securityAnswerHash;
    private Boolean isOnline; // 是否在线
    private LocalDateTime lastActiveTime; // 最后活跃时间
    private LocalDateTime createdAt;
}

