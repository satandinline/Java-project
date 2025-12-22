package com.cultural.controller;

import com.cultural.service.AuthService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 认证控制器
 * 处理用户注册、登录等API请求
 */
@RestController
@RequestMapping("/api/auth")
public class AuthController {

    @Autowired
    private AuthService authService;

    /**
     * 用户注册
     * POST /api/auth/register
     */
    @PostMapping("/register")
    public ResponseEntity<Map<String, Object>> register(@RequestBody Map<String, String> request) {
        String password = request.get("password");
        String nickname = request.get("nickname");
        String avatarPath = request.get("avatar_path");
        String securityQuestion = request.get("security_question");
        String securityAnswer = request.get("security_answer");

        Map<String, Object> result = authService.register(password, nickname, avatarPath, 
                                                          securityQuestion, securityAnswer);
        
        if ((Boolean) result.get("success")) {
            return ResponseEntity.ok(result);
        } else {
            return ResponseEntity.badRequest().body(result);
        }
    }

    /**
     * 用户登录
     * POST /api/auth/login
     */
    @PostMapping("/login")
    public ResponseEntity<Map<String, Object>> login(@RequestBody Map<String, String> request) {
        String account = request.get("account");
        String password = request.get("password");

        Map<String, Object> result = authService.login(account, password);
        
        if ((Boolean) result.get("success")) {
            return ResponseEntity.ok(result);
        } else {
            return ResponseEntity.badRequest().body(result);
        }
    }

    /**
     * 获取用户信息
     * GET /api/auth/user
     */
    @GetMapping("/user")
    public ResponseEntity<Map<String, Object>> getUserInfo(@RequestParam Long userId) {
        Map<String, Object> result = authService.getUserInfo(userId);
        
        if ((Boolean) result.get("success")) {
            return ResponseEntity.ok(result);
        } else {
            return ResponseEntity.badRequest().body(result);
        }
    }

    /**
     * 用户登出
     * POST /api/auth/logout
     */
    @PostMapping("/logout")
    public ResponseEntity<Map<String, Object>> logout(@RequestBody Map<String, Long> request) {
        Long userId = request.get("user_id");
        Map<String, Object> result = authService.logout(userId);
        
        if ((Boolean) result.get("success")) {
            return ResponseEntity.ok(result);
        } else {
            return ResponseEntity.badRequest().body(result);
        }
    }

    /**
     * 获取所有用户列表（仅超级管理员）
     * GET /api/auth/users
     */
    @GetMapping("/users")
    public ResponseEntity<Map<String, Object>> getAllUsers(@RequestParam Long userId) {
        Map<String, Object> result = authService.getAllUsers(userId);
        
        if ((Boolean) result.get("success")) {
            return ResponseEntity.ok(result);
        } else {
            // 如果是权限错误，返回403
            if (result.containsKey("message") && result.get("message").toString().contains("权限")) {
                return ResponseEntity.status(403).body(result);
            }
            return ResponseEntity.badRequest().body(result);
        }
    }

    /**
     * 切换用户身份（仅超级管理员）
     * POST /api/auth/switch-role
     */
    @PostMapping("/switch-role")
    public ResponseEntity<Map<String, Object>> switchUserRole(@RequestBody Map<String, Object> request) {
        Long currentUserId = ((Number) request.get("current_user_id")).longValue();
        Long targetUserId = ((Number) request.get("target_user_id")).longValue();
        String newRole = (String) request.get("new_role");
        
        Map<String, Object> result = authService.switchUserRole(currentUserId, targetUserId, newRole);
        
        if ((Boolean) result.get("success")) {
            return ResponseEntity.ok(result);
        } else {
            return ResponseEntity.badRequest().body(result);
        }
    }

}

