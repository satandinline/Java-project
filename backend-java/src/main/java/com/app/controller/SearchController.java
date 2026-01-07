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
public class SearchController {
    @Autowired
    private CulturalResourceRepository resourceRepository;

    @GetMapping("/ai_search")
    public ResponseEntity<Map<String, Object>> aiSearch(
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

