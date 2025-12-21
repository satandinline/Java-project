package com.cultural.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 统计服务类
 */
@Service
public class StatisticsService {

    @Autowired
    private JdbcTemplate jdbcTemplate;

    /**
     * 获取所有统计数据
     */
    public Map<String, Object> getStatistics() {
        Map<String, Object> result = new HashMap<>();
        LocalDate today = LocalDate.now();

        try {
            // 1. 历史访问人次（去重的用户登录次数）
            Integer totalVisits = jdbcTemplate.queryForObject(
                "SELECT COUNT(DISTINCT user_id) FROM user_behavior_logs " +
                "WHERE behavior_type = '交互' AND content LIKE '用户登录%'",
                Integer.class
            );

            // 2. 今日访问人次
            Integer todayVisits = jdbcTemplate.queryForObject(
                "SELECT COUNT(DISTINCT user_id) FROM user_behavior_logs " +
                "WHERE behavior_type = '交互' AND content LIKE '用户登录%' " +
                "AND DATE(timestamp) = ?",
                Integer.class, today
            );

            // 3. 历史用户上传内容数量
            Integer totalUploads = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM cultural_resources_from_user",
                Integer.class
            );

            // 4. 今日用户上传数量
            Integer todayUploads = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM cultural_resources_from_user WHERE DATE(upload_time) = ?",
                Integer.class, today
            );

            // 5. 历史AIGC使用总量（文字+图片）
            Integer totalAigc = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM qa_messages WHERE model IN ('text', 'image')",
                Integer.class
            );

            // 6. 今日AIGC使用总量
            Integer todayAigc = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM qa_messages WHERE model IN ('text', 'image') " +
                "AND DATE(create_time) = ?",
                Integer.class, today
            );

            // 7. 历史文字AIGC使用量
            Integer totalTextAigc = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM qa_messages WHERE model = 'text'",
                Integer.class
            );

            // 8. 今日文字AIGC使用量
            Integer todayTextAigc = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM qa_messages WHERE model = 'text' AND DATE(create_time) = ?",
                Integer.class, today
            );

            // 9. 历史图片AIGC使用量
            Integer totalImageAigc = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM qa_messages WHERE model = 'image'",
                Integer.class
            );

            // 10. 今日图片AIGC使用量
            Integer todayImageAigc = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM qa_messages WHERE model = 'image' AND DATE(create_time) = ?",
                Integer.class, today
            );

            Map<String, Object> data = new HashMap<>();
            data.put("total_visits", totalVisits != null ? totalVisits : 0);
            data.put("today_visits", todayVisits != null ? todayVisits : 0);
            data.put("total_uploads", totalUploads != null ? totalUploads : 0);
            data.put("today_uploads", todayUploads != null ? todayUploads : 0);
            data.put("total_aigc", totalAigc != null ? totalAigc : 0);
            data.put("today_aigc", todayAigc != null ? todayAigc : 0);
            data.put("total_text_aigc", totalTextAigc != null ? totalTextAigc : 0);
            data.put("today_text_aigc", todayTextAigc != null ? todayTextAigc : 0);
            data.put("total_image_aigc", totalImageAigc != null ? totalImageAigc : 0);
            data.put("today_image_aigc", todayImageAigc != null ? todayImageAigc : 0);
            data.put("current_date", today.toString());

            result.put("success", true);
            result.put("data", data);
        } catch (Exception e) {
            result.put("success", false);
            result.put("error", e.getMessage());
        }

        return result;
    }
}

