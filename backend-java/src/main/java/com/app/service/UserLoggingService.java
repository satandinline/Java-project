package com.app.service;

import com.app.entity.UserBehaviorLog;
import com.app.repository.UserBehaviorLogRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

@Service
public class UserLoggingService {
    @Autowired
    private UserBehaviorLogRepository logRepository;

    @Transactional
    public boolean logBehavior(Long userId, UserBehaviorLog.BehaviorType behaviorType, String content) {
        try {
            UserBehaviorLog log = new UserBehaviorLog();
            log.setUserId(userId);
            log.setBehaviorType(behaviorType);
            log.setContent(content);
            log.setTimestamp(LocalDateTime.now());
            logRepository.save(log);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    public boolean logLogin(Long userId, String account) {
        return logBehavior(userId, UserBehaviorLog.BehaviorType.交互, "用户登录：" + account);
    }

    public boolean logRegister(Long userId, String account) {
        return logBehavior(userId, UserBehaviorLog.BehaviorType.交互, "用户注册：" + account);
    }

    public boolean logUpload(Long userId, String fileName, String resourceType) {
        return logBehavior(userId, UserBehaviorLog.BehaviorType.交互, 
            "上传资源：" + fileName + "（类型：" + resourceType + "）");
    }

    public boolean logSearch(Long userId, String searchType, String query) {
        String content = "执行" + searchType + "搜索";
        if (query != null && !query.isEmpty()) {
            content += "（关键词：" + (query.length() > 50 ? query.substring(0, 50) + "..." : query) + "）";
        }
        return logBehavior(userId, UserBehaviorLog.BehaviorType.检索, content);
    }
}

