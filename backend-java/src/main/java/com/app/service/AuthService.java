package com.app.service;

import com.app.entity.User;
import com.app.repository.UserRepository;
import com.app.util.PasswordUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import java.util.Random;

@Service
public class AuthService {
    @Autowired
    private UserRepository userRepository;

    public Map<String, Object> register(String password, String nickname, String avatarPath,
                                       String securityQuestion, String securityAnswer) {
        Map<String, Object> result = new HashMap<>();
        
        if (password == null || password.isEmpty()) {
            result.put("success", false);
            result.put("message", "密码不能为空");
            return result;
        }
        
        if (password.length() < 6) {
            result.put("success", false);
            result.put("message", "密码至少需要6个字符");
            return result;
        }
        
        if (nickname == null || nickname.trim().isEmpty()) {
            nickname = generateRandomNickname();
        }
        
        if (avatarPath == null || avatarPath.trim().isEmpty()) {
            avatarPath = "/default.jpg";
        }
        
        String securityAnswerHash = null;
        if (securityQuestion != null && securityAnswer != null && !securityQuestion.trim().isEmpty() && !securityAnswer.trim().isEmpty()) {
            securityAnswerHash = PasswordUtil.hashPassword(securityAnswer);
        }
        
        String account = generateUniqueAccount();
        if (account == null) {
            result.put("success", false);
            result.put("message", "账号生成失败，请稍后重试");
            return result;
        }
        
        String passwordHash = PasswordUtil.hashPassword(password);
        
        User user = new User();
        user.setAccount(account);
        user.setPasswordHash(passwordHash);
        user.setRole(User.UserRole.普通用户);
        user.setNickname(nickname);
        user.setAvatarPath(avatarPath);
        user.setSecurityQuestion(securityQuestion);
        user.setSecurityAnswerHash(securityAnswerHash);
        user.setCreatedAt(LocalDateTime.now());
        
        try {
            user = userRepository.save(user);
            
            Map<String, Object> userInfo = new HashMap<>();
            userInfo.put("id", user.getId());
            userInfo.put("account", user.getAccount());
            userInfo.put("nickname", user.getNickname());
            userInfo.put("signature", user.getSignature());
            userInfo.put("avatar_path", user.getAvatarPath());
            userInfo.put("role", user.getRole().name());
            
            result.put("success", true);
            result.put("message", "注册成功！您的账号：" + account + "，请妥善保管，可直接登录");
            result.put("user_info", userInfo);
        } catch (Exception e) {
            result.put("success", false);
            result.put("message", "注册失败：" + e.getMessage());
        }
        
        return result;
    }

    @Transactional
    public Map<String, Object> login(String account, String password) {
        Map<String, Object> result = new HashMap<>();
        
        if (account == null || account.isEmpty() || password == null || password.isEmpty()) {
            result.put("success", false);
            result.put("message", "账号和密码不能为空");
            return result;
        }
        
        Optional<User> userOpt = userRepository.findByAccount(account);
        if (userOpt.isEmpty()) {
            result.put("success", false);
            result.put("message", "账号不存在，请先注册");
            return result;
        }
        
        User user = userOpt.get();
        String passwordHash = PasswordUtil.hashPassword(password);
        
        if (!user.getPasswordHash().equals(passwordHash)) {
            result.put("success", false);
            result.put("message", "密码错误，请重新尝试");
            return result;
        }
        
        // 更新在线状态
        user.setIsOnline(true);
        user.setLastActiveTime(LocalDateTime.now());
        userRepository.save(user);
        
        Map<String, Object> userInfo = new HashMap<>();
        userInfo.put("id", user.getId());
        userInfo.put("account", user.getAccount());
        userInfo.put("role", user.getRole().name());
        userInfo.put("nickname", user.getNickname() != null ? user.getNickname() : user.getAccount());
        userInfo.put("signature", user.getSignature());
        String avatarPath = user.getAvatarPath();
        if (avatarPath == null || avatarPath.equals("./default.jpg")) {
            avatarPath = "/default.jpg";
        }
        userInfo.put("avatar_path", avatarPath);
        
        result.put("success", true);
        result.put("message", "登录成功！欢迎回来，" + userInfo.get("nickname"));
        result.put("user_info", userInfo);
        
        return result;
    }

    public Map<String, Object> getUserById(Long userId) {
        Map<String, Object> result = new HashMap<>();
        Optional<User> userOpt = userRepository.findById(userId);
        if (userOpt.isEmpty()) {
            return null;
        }
        
        User user = userOpt.get();
        Map<String, Object> userInfo = new HashMap<>();
        userInfo.put("id", user.getId());
        userInfo.put("account", user.getAccount());
        userInfo.put("role", user.getRole().name());
        userInfo.put("nickname", user.getNickname() != null ? user.getNickname() : user.getAccount());
        userInfo.put("signature", user.getSignature());
        userInfo.put("avatar_path", user.getAvatarPath() != null ? user.getAvatarPath() : "./default.jpg");
        userInfo.put("security_question", user.getSecurityQuestion());
        
        return userInfo;
    }

    @Transactional
    public Map<String, Object> updateNickname(Long userId, String nickname) {
        Map<String, Object> result = new HashMap<>();
        
        if (nickname == null || nickname.trim().isEmpty()) {
            result.put("success", false);
            result.put("message", "昵称不能为空");
            return result;
        }
        
        if (nickname.trim().length() > 100) {
            result.put("success", false);
            result.put("message", "昵称长度不能超过100个字符");
            return result;
        }
        
        Optional<User> userOpt = userRepository.findById(userId);
        if (userOpt.isEmpty()) {
            result.put("success", false);
            result.put("message", "用户不存在");
            return result;
        }
        
        User user = userOpt.get();
        user.setNickname(nickname.trim());
        userRepository.save(user);
        
        result.put("success", true);
        result.put("message", "昵称修改成功");
        return result;
    }

    @Transactional
    public Map<String, Object> updatePassword(Long userId, String oldPassword, String newPassword) {
        Map<String, Object> result = new HashMap<>();
        
        if (newPassword == null || newPassword.length() < 6) {
            result.put("success", false);
            result.put("message", "新密码至少需要6个字符");
            return result;
        }
        
        Optional<User> userOpt = userRepository.findById(userId);
        if (userOpt.isEmpty()) {
            result.put("success", false);
            result.put("message", "用户不存在");
            return result;
        }
        
        User user = userOpt.get();
        String oldPasswordHash = PasswordUtil.hashPassword(oldPassword);
        if (!user.getPasswordHash().equals(oldPasswordHash)) {
            result.put("success", false);
            result.put("message", "旧密码错误");
            return result;
        }
        
        String newPasswordHash = PasswordUtil.hashPassword(newPassword);
        user.setPasswordHash(newPasswordHash);
        userRepository.save(user);
        
        result.put("success", true);
        result.put("message", "密码修改成功");
        return result;
    }

    @Transactional
    public Map<String, Object> resetPassword(String account, String newPassword) {
        Map<String, Object> result = new HashMap<>();
        
        if (newPassword == null || newPassword.length() < 6) {
            result.put("success", false);
            result.put("message", "密码至少需要6个字符");
            return result;
        }
        
        Optional<User> userOpt = userRepository.findByAccount(account);
        if (userOpt.isEmpty()) {
            result.put("success", false);
            result.put("message", "用户不存在");
            return result;
        }
        
        User user = userOpt.get();
        String newPasswordHash = PasswordUtil.hashPassword(newPassword);
        user.setPasswordHash(newPasswordHash);
        userRepository.save(user);
        
        result.put("success", true);
        result.put("message", "密码重置成功");
        return result;
    }

    public Map<String, Object> getSecurityQuestion(String account) {
        Map<String, Object> result = new HashMap<>();
        Optional<User> userOpt = userRepository.findByAccount(account);
        if (userOpt.isEmpty()) {
            result.put("success", false);
            result.put("message", "用户不存在");
            return result;
        }
        
        User user = userOpt.get();
        if (user.getSecurityQuestion() == null || user.getSecurityQuestion().isEmpty()) {
            result.put("success", false);
            result.put("message", "该用户未设置安全问题");
            return result;
        }
        
        result.put("success", true);
        result.put("user_id", user.getId());
        result.put("security_question", user.getSecurityQuestion());
        return result;
    }

    public Map<String, Object> verifySecurityAnswer(String account, String answer) {
        Map<String, Object> result = new HashMap<>();
        Optional<User> userOpt = userRepository.findByAccount(account);
        if (userOpt.isEmpty()) {
            result.put("success", false);
            result.put("message", "用户不存在");
            return result;
        }
        
        User user = userOpt.get();
        if (user.getSecurityAnswerHash() == null || user.getSecurityAnswerHash().isEmpty()) {
            result.put("success", false);
            result.put("message", "该用户未设置安全问题");
            return result;
        }
        
        String answerHash = PasswordUtil.hashPassword(answer);
        if (answerHash.equals(user.getSecurityAnswerHash())) {
            result.put("success", true);
            result.put("user_id", user.getId());
        } else {
            result.put("success", false);
            result.put("message", "答案错误");
        }
        
        return result;
    }

    public Map<String, Object> verifySecurityQuestion(Long userId, String answer) {
        Map<String, Object> result = new HashMap<>();
        Optional<User> userOpt = userRepository.findById(userId);
        if (userOpt.isEmpty()) {
            result.put("success", false);
            result.put("message", "用户不存在");
            return result;
        }
        
        User user = userOpt.get();
        if (user.getSecurityAnswerHash() == null || user.getSecurityAnswerHash().isEmpty()) {
            result.put("success", false);
            result.put("message", "用户未设置安全问题");
            return result;
        }
        
        String answerHash = PasswordUtil.hashPassword(answer);
        if (answerHash.equals(user.getSecurityAnswerHash())) {
            result.put("success", true);
            result.put("message", "验证成功");
        } else {
            result.put("success", false);
            result.put("message", "答案错误");
        }
        
        return result;
    }

    @Transactional
    public Map<String, Object> updateSecurityQuestion(Long userId, String question, String answer) {
        Map<String, Object> result = new HashMap<>();
        Optional<User> userOpt = userRepository.findById(userId);
        if (userOpt.isEmpty()) {
            result.put("success", false);
            result.put("message", "用户不存在");
            return result;
        }
        
        User user = userOpt.get();
        String answerHash = PasswordUtil.hashPassword(answer);
        user.setSecurityQuestion(question);
        user.setSecurityAnswerHash(answerHash);
        userRepository.save(user);
        
        result.put("success", true);
        result.put("message", "安全问题更新成功");
        return result;
    }

    private String generateUniqueAccount() {
        Random random = new Random();
        for (int i = 0; i < 100; i++) {
            int length = random.nextInt(3) + 8; // 8-10位
            int firstDigit = random.nextInt(9) + 1; // 1-9
            StringBuilder account = new StringBuilder(String.valueOf(firstDigit));
            for (int j = 1; j < length; j++) {
                account.append(random.nextInt(10));
            }
            String accountStr = account.toString();
            if (!userRepository.existsByAccount(accountStr)) {
                return accountStr;
            }
        }
        return null;
    }

    private String generateRandomNickname() {
        String chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";
        Random random = new Random();
        StringBuilder nickname = new StringBuilder();
        for (int i = 0; i < 10; i++) {
            nickname.append(chars.charAt(random.nextInt(chars.length())));
        }
        return nickname.toString();
    }
}

