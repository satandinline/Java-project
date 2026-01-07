package com.app.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class StatisticsService {
    @Autowired
    private JdbcTemplate jdbcTemplate;

    public Map<String, Object> getStatistics() {
        Map<String, Object> result = new HashMap<>();
        
        try {
            // 历史访问人次
            Long totalUsers = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM user_behavior_logs WHERE behavior_type = '交互' AND content LIKE '用户登录%'",
                Long.class);
            
            // 今日访问人次
            Long todayUsers = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM user_behavior_logs WHERE behavior_type = '交互' AND content LIKE '用户登录%' AND DATE(timestamp) = CURDATE()",
                Long.class);
            
            // 历史文字AIGC使用人次
            Long totalTextCount = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM qa_messages WHERE model = 'text'",
                Long.class);
            Long totalTextUsers = totalTextCount;
            
            // 今日文字AIGC使用人次
            Long todayTextCount = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM qa_messages WHERE model = 'text' AND DATE(create_time) = CURDATE()",
                Long.class);
            Long todayTextUsers = todayTextCount;
            
            // 历史图片AIGC使用人次
            Long totalImageCount = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM qa_messages WHERE model = 'image'",
                Long.class);
            Long totalImageUsers = totalImageCount;
            
            // 今日图片AIGC使用人次
            Long todayImageCount = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM qa_messages WHERE model = 'image' AND DATE(create_time) = CURDATE()",
                Long.class);
            Long todayImageUsers = todayImageCount;
            
            // 最近7天趋势数据
            List<Map<String, Object>> trendData = new ArrayList<>();
            for (int i = 6; i >= 0; i--) {
                LocalDate targetDate = LocalDate.now().minusDays(i);
                String dateStr = targetDate.toString();
                
                Long dailyUsers = jdbcTemplate.queryForObject(
                    i == 0 ? 
                        "SELECT COUNT(*) FROM user_behavior_logs WHERE behavior_type = '交互' AND content LIKE '用户登录%' AND DATE(timestamp) = CURDATE()" :
                        "SELECT COUNT(*) FROM user_behavior_logs WHERE behavior_type = '交互' AND content LIKE '用户登录%' AND DATE(timestamp) = DATE_SUB(CURDATE(), INTERVAL ? DAY)",
                    Long.class,
                    i == 0 ? new Object[]{} : new Object[]{i});
                
                Long textCount = jdbcTemplate.queryForObject(
                    i == 0 ?
                        "SELECT COUNT(*) FROM qa_messages WHERE model = 'text' AND DATE(create_time) = CURDATE()" :
                        "SELECT COUNT(*) FROM qa_messages WHERE model = 'text' AND DATE(create_time) = DATE_SUB(CURDATE(), INTERVAL ? DAY)",
                    Long.class,
                    i == 0 ? new Object[]{} : new Object[]{i});
                
                Long imageCount = jdbcTemplate.queryForObject(
                    i == 0 ?
                        "SELECT COUNT(*) FROM qa_messages WHERE model = 'image' AND DATE(create_time) = CURDATE()" :
                        "SELECT COUNT(*) FROM qa_messages WHERE model = 'image' AND DATE(create_time) = DATE_SUB(CURDATE(), INTERVAL ? DAY)",
                    Long.class,
                    i == 0 ? new Object[]{} : new Object[]{i});
                
                Map<String, Object> dayData = new HashMap<>();
                dayData.put("date", dateStr);
                dayData.put("daily_users", dailyUsers != null ? dailyUsers : 0);
                dayData.put("text_count", textCount != null ? textCount : 0);
                dayData.put("image_count", imageCount != null ? imageCount : 0);
                dayData.put("total_aigc_count", (textCount != null ? textCount : 0) + (imageCount != null ? imageCount : 0));
                trendData.add(dayData);
            }
            
            Map<String, Object> data = new HashMap<>();
            data.put("total_users", totalUsers != null ? totalUsers : 0);
            data.put("today_users", todayUsers != null ? todayUsers : 0);
            data.put("total_text_users", totalTextUsers != null ? totalTextUsers : 0);
            data.put("total_text_count", totalTextCount != null ? totalTextCount : 0);
            data.put("today_text_users", todayTextUsers != null ? todayTextUsers : 0);
            data.put("today_text_count", todayTextCount != null ? todayTextCount : 0);
            data.put("total_image_users", totalImageUsers != null ? totalImageUsers : 0);
            data.put("total_image_count", totalImageCount != null ? totalImageCount : 0);
            data.put("today_image_users", todayImageUsers != null ? todayImageUsers : 0);
            data.put("today_image_count", todayImageCount != null ? todayImageCount : 0);
            data.put("trend_data", trendData);
            data.put("current_date", LocalDate.now().toString());
            
            result.put("success", true);
            result.put("data", data);
        } catch (Exception e) {
            result.put("success", false);
            result.put("error", e.getMessage());
        }
        
        return result;
    }
}

