package com.cultural.controller;

import com.cultural.service.StatisticsService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 统计API控制器
 */
@RestController
@RequestMapping("/api/statistics")
public class StatisticsController {

    @Autowired
    private StatisticsService statisticsService;

    /**
     * 获取统计数据（需要管理员或超级管理员权限）
     * GET /api/statistics
     */
    @GetMapping
    public ResponseEntity<Map<String, Object>> getStatistics(@RequestParam(required = false) Long userId) {
        Map<String, Object> result = statisticsService.getStatistics(userId);
        if ((Boolean) result.get("success")) {
            return ResponseEntity.ok(result);
        } else {
            // 如果是权限错误，返回403
            if (result.containsKey("message") && result.get("message").toString().contains("权限")) {
                return ResponseEntity.status(403).body(result);
            }
            return ResponseEntity.status(500).body(result);
        }
    }
}

