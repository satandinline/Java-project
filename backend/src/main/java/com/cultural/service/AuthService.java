package com.cultural.service;

import com.cultural.dao.UserDao;
import com.cultural.entity.User;
import com.cultural.util.AccountUtil;
import com.cultural.util.PasswordUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * 认证服务类
 * 处理用户注册、登录等认证相关业务
 */
@Service
public class AuthService {

    @Autowired
    private UserDao userDao;

    /**
     * 用户注册
     */
    @Transactional
    public Map<String, Object> register(String password, String nickname, 
                                        String avatarPath, String securityQuestion, 
                                        String securityAnswer) {
        Map<String, Object> result = new HashMap<>();
        
        if (password == null || password.length() < 6) {
            result.put("success", false);
            result.put("message", "密码至少需要6个字符");
            return result;
        }

        // 如果没有提供昵称，生成随机昵称
        if (nickname == null || nickname.trim().isEmpty()) {
            nickname = AccountUtil.generateRandomNickname();
        }

        // 如果没有提供头像路径，使用默认头像
        if (avatarPath == null || avatarPath.trim().isEmpty()) {
            avatarPath = "/default.jpg";
        }

        // 生成唯一的账号
        String account = null;
        int maxAttempts = 100;
        for (int i = 0; i < maxAttempts; i++) {
            String candidateAccount = AccountUtil.generateRandomAccount();
            if (!userDao.accountExists(candidateAccount)) {
                account = candidateAccount;
                break;
            }
        }

        if (account == null) {
            result.put("success", false);
            result.put("message", "账号生成失败，请稍后重试");
            return result;
        }

        // 创建用户对象
        User user = new User();
        user.setAccount(account);
        user.setPasswordHash(PasswordUtil.hashPassword(password));
        user.setRole("普通用户");
        user.setNickname(nickname);
        user.setSignature(null);
        user.setAvatarPath(avatarPath);
        user.setSecurityQuestion(securityQuestion);
        
        if (securityAnswer != null && !securityAnswer.trim().isEmpty()) {
            user.setSecurityAnswerHash(PasswordUtil.hashPassword(securityAnswer));
        }

        try {
            Long userId = userDao.createUser(user);
            
            Map<String, Object> userInfo = new HashMap<>();
            userInfo.put("id", userId);
            userInfo.put("account", account);
            userInfo.put("nickname", nickname);
            userInfo.put("signature", null);
            userInfo.put("avatar_path", avatarPath);
            userInfo.put("role", "普通用户");

            result.put("success", true);
            result.put("message", String.format("注册成功！您的账号：%s，请妥善保管，可直接登录", account));
            result.put("user_info", userInfo);
        } catch (Exception e) {
            result.put("success", false);
            result.put("message", "注册失败：" + e.getMessage());
        }

        return result;
    }

    /**
     * 用户登录
     */
    public Map<String, Object> login(String account, String password) {
        Map<String, Object> result = new HashMap<>();
        
        if (account == null || password == null) {
            result.put("success", false);
            result.put("message", "账号和密码不能为空");
            return result;
        }

        Optional<User> userOpt = userDao.findByAccount(account);
        if (userOpt.isEmpty()) {
            result.put("success", false);
            result.put("message", "账号不存在");
            return result;
        }

        User user = userOpt.get();
        if (!PasswordUtil.verifyPassword(password, user.getPasswordHash())) {
            result.put("success", false);
            result.put("message", "密码错误");
            return result;
        }

        // 更新在线状态
        userDao.updateOnlineStatus(user.getId(), true);

        // 构建用户信息
        Map<String, Object> userInfo = new HashMap<>();
        userInfo.put("id", user.getId());
        userInfo.put("account", user.getAccount());
        userInfo.put("nickname", user.getNickname());
        userInfo.put("signature", user.getSignature());
        userInfo.put("avatar_path", user.getAvatarPath());
        userInfo.put("role", user.getRole());
        userInfo.put("is_online", true);

        result.put("success", true);
        result.put("message", "登录成功");
        result.put("user_info", userInfo);

        return result;
    }

    /**
     * 获取用户信息
     */
    public Map<String, Object> getUserInfo(Long userId) {
        Map<String, Object> result = new HashMap<>();
        
        Optional<User> userOpt = userDao.findById(userId);
        if (userOpt.isEmpty()) {
            result.put("success", false);
            result.put("message", "用户不存在");
            return result;
        }

        User user = userOpt.get();
        Map<String, Object> userInfo = new HashMap<>();
        userInfo.put("id", user.getId());
        userInfo.put("account", user.getAccount());
        userInfo.put("nickname", user.getNickname());
        userInfo.put("signature", user.getSignature());
        userInfo.put("avatar_path", user.getAvatarPath());
        userInfo.put("role", user.getRole());

        result.put("success", true);
        result.put("user_info", userInfo);

        return result;
    }

    /**
     * 用户登出
     */
    @Transactional
    public Map<String, Object> logout(Long userId) {
        Map<String, Object> result = new HashMap<>();
        
        Optional<User> userOpt = userDao.findById(userId);
        if (userOpt.isEmpty()) {
            result.put("success", false);
            result.put("message", "用户不存在");
            return result;
        }

        // 更新在线状态为离线
        userDao.updateOnlineStatus(userId, false);

        result.put("success", true);
        result.put("message", "登出成功");
        return result;
    }

    /**
     * 获取所有用户列表（仅超级管理员）
     */
    public Map<String, Object> getAllUsers(Long currentUserId) {
        Map<String, Object> result = new HashMap<>();
        
        // 检查当前用户是否为超级管理员
        Optional<User> currentUserOpt = userDao.findById(currentUserId);
        if (currentUserOpt.isEmpty()) {
            result.put("success", false);
            result.put("message", "用户不存在");
            return result;
        }

        User currentUser = currentUserOpt.get();
        if (!"超级管理员".equals(currentUser.getRole())) {
            result.put("success", false);
            result.put("message", "权限不足，仅超级管理员可查看");
            return result;
        }

        List<User> users = userDao.getAllUsers();
        List<Map<String, Object>> userList = new ArrayList<>();
        for (User user : users) {
            Map<String, Object> userInfo = new HashMap<>();
            userInfo.put("id", user.getId());
            userInfo.put("account", user.getAccount());
            userInfo.put("nickname", user.getNickname());
            userInfo.put("signature", user.getSignature());
            userInfo.put("avatar_path", user.getAvatarPath());
            userInfo.put("role", user.getRole());
            userInfo.put("is_online", user.getIsOnline() != null && user.getIsOnline());
            userInfo.put("last_active_time", user.getLastActiveTime());
            userInfo.put("created_at", user.getCreatedAt());
            userList.add(userInfo);
        }

        result.put("success", true);
        result.put("users", userList);
        return result;
    }

    /**
     * 切换用户身份（仅超级管理员）
     */
    @Transactional
    public Map<String, Object> switchUserRole(Long currentUserId, Long targetUserId, String newRole) {
        Map<String, Object> result = new HashMap<>();
        
        // 检查当前用户是否为超级管理员
        Optional<User> currentUserOpt = userDao.findById(currentUserId);
        if (currentUserOpt.isEmpty()) {
            result.put("success", false);
            result.put("message", "当前用户不存在");
            return result;
        }

        User currentUser = currentUserOpt.get();
        if (!"超级管理员".equals(currentUser.getRole())) {
            result.put("success", false);
            result.put("message", "权限不足，仅超级管理员可操作");
            return result;
        }

        // 检查目标用户是否存在
        Optional<User> targetUserOpt = userDao.findById(targetUserId);
        if (targetUserOpt.isEmpty()) {
            result.put("success", false);
            result.put("message", "目标用户不存在");
            return result;
        }

        User targetUser = targetUserOpt.get();
        
        // 不能修改超级管理员的身份
        if ("超级管理员".equals(targetUser.getRole())) {
            result.put("success", false);
            result.put("message", "不能修改超级管理员的身份");
            return result;
        }

        // 验证新角色
        if (!"管理员".equals(newRole) && !"普通用户".equals(newRole)) {
            result.put("success", false);
            result.put("message", "无效的角色，只能切换为管理员或普通用户");
            return result;
        }

        // 更新用户角色
        userDao.updateUserRole(targetUserId, newRole);

        result.put("success", true);
        result.put("message", "用户身份切换成功");
        return result;
    }
}

