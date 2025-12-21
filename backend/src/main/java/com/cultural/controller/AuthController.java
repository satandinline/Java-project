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

}

