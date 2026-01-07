package com.app.service;

import com.app.entity.AnnotationTask;
import com.app.entity.User;
import com.app.repository.AnnotationTaskRepository;
import com.app.repository.UserRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Service
public class AnnotationTaskService {
    @Autowired
    private AnnotationTaskRepository taskRepository;
    
    @Autowired
    private UserRepository userRepository;

    public Map<String, Object> getAnnotationTasks(Long userId, String status, int page, int pageSize) {
        Map<String, Object> result = new HashMap<>();
        
        // 默认每页12条
        if (pageSize <= 0) {
            pageSize = 12;
        }
        if (page < 1) {
            page = 1;
        }
        
        try {
            Optional<User> userOpt = userRepository.findById(userId);
            if (userOpt.isEmpty()) {
                result.put("success", false);
                result.put("message", "用户不存在");
                return result;
            }
            
            User user = userOpt.get();
            String userRole = user.getRole().name();
            
            Pageable pageable = PageRequest.of(page - 1, pageSize);
            Page<AnnotationTask> taskPage;
            
            // 管理员可以看到所有任务，普通用户只能看到自己上传的资源对应的任务
            if ("管理员".equals(userRole) || "超级管理员".equals(userRole)) {
                if (status != null && !status.trim().isEmpty()) {
                    taskPage = taskRepository.findByStatus(status.trim(), pageable);
                } else {
                    taskPage = taskRepository.findAll(pageable);
                }
            } else {
                // 普通用户只能看到自己上传的资源对应的任务
                if (status != null && !status.trim().isEmpty()) {
                    taskPage = taskRepository.findByUserIdAndStatus(userId, status.trim(), pageable);
                } else {
                    taskPage = taskRepository.findByUserId(userId, pageable);
                }
            }
            
            List<Map<String, Object>> taskList = taskPage.getContent().stream().map(task -> {
                Map<String, Object> taskMap = new HashMap<>();
                taskMap.put("id", task.getId());
                taskMap.put("resource_id", task.getResourceId());
                taskMap.put("resource_source", task.getResourceSource());
                taskMap.put("task_type", task.getTaskType());
                taskMap.put("status", task.getStatus());
                taskMap.put("annotation_method", task.getAnnotationMethod());
                taskMap.put("created_at", task.getCreatedAt());
                taskMap.put("updated_at", task.getUpdatedAt());
                // TODO: 添加资源详情信息（title, resource_type, content_feature_data等）
                return taskMap;
            }).toList();
            
            result.put("success", true);
            result.put("tasks", taskList);
            result.put("total", taskPage.getTotalElements());
            result.put("page", page);
            result.put("page_size", pageSize);
            result.put("total_pages", taskPage.getTotalPages());
            
        } catch (Exception e) {
            result.put("success", false);
            result.put("message", "获取任务失败：" + e.getMessage());
        }
        
        return result;
    }
}

