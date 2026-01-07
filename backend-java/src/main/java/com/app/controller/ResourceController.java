package com.app.controller;

import com.app.entity.CulturalResource;
import com.app.repository.CulturalResourceRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api")
public class ResourceController {
    @Autowired
    private CulturalResourceRepository resourceRepository;

    @GetMapping("/home/resources")
    public ResponseEntity<Map<String, Object>> getHomeResources(
            @RequestParam(value = "page", defaultValue = "1") int page,
            @RequestParam(value = "page_size", defaultValue = "8") int pageSize) {
        try {
            // 检索结果每页8条数据
            if (pageSize <= 0) {
                pageSize = 8;
            }
            if (page < 1) {
                page = 1;
            }
            
            Pageable pageable = PageRequest.of(page - 1, pageSize);
            Page<CulturalResource> resources = resourceRepository.findAll(pageable);
            
            Map<String, Object> result = new HashMap<>();
            result.put("success", true);
            result.put("resources", resources.getContent());
            result.put("total", resources.getTotalElements());
            result.put("page", page);
            result.put("page_size", pageSize);
            result.put("total_pages", resources.getTotalPages());
            
            return ResponseEntity.ok(result);
        } catch (Exception e) {
            Map<String, Object> result = Map.of("success", false, "message", "获取资源失败：" + e.getMessage());
            return ResponseEntity.status(500).body(result);
        }
    }

    @GetMapping("/resource/detail")
    public ResponseEntity<Map<String, Object>> getResourceDetail(@RequestParam("resource_id") Long resourceId) {
        // TODO: 实现资源详情查询
        Map<String, Object> result = Map.of("success", true, "resource", Map.of());
        return ResponseEntity.ok(result);
    }

    @GetMapping("/search")
    public ResponseEntity<Map<String, Object>> search(
            @RequestParam(value = "keyword", required = false) String keyword,
            @RequestParam(value = "page", defaultValue = "1") int page,
            @RequestParam(value = "page_size", defaultValue = "8") int pageSize) {
        try {
            // 检索结果每页8条数据
            if (pageSize <= 0) {
                pageSize = 8;
            }
            if (page < 1) {
                page = 1;
            }
            
            Pageable pageable = PageRequest.of(page - 1, pageSize);
            Page<CulturalResource> resources;
            
            if (keyword != null && !keyword.trim().isEmpty()) {
                resources = resourceRepository.searchByKeyword(keyword.trim(), pageable);
            } else {
                resources = resourceRepository.findAll(pageable);
            }
            
            Map<String, Object> result = new HashMap<>();
            result.put("success", true);
            result.put("resources", resources.getContent());
            result.put("total", resources.getTotalElements());
            result.put("page", page);
            result.put("page_size", pageSize);
            result.put("total_pages", resources.getTotalPages());
            
            return ResponseEntity.ok(result);
        } catch (Exception e) {
            Map<String, Object> result = Map.of("success", false, "message", "搜索失败：" + e.getMessage());
            return ResponseEntity.status(500).body(result);
        }
    }
}

