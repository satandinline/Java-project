package com.app.controller;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.Map;

@RestController
@RequestMapping("/api")
public class UploadController {

    @PostMapping("/upload")
    public ResponseEntity<Map<String, Object>> uploadResource(
            @RequestHeader(value = "X-User-Id", required = false) Long userId,
            @RequestParam(value = "userId", required = false) String userIdStr,
            @RequestParam("file") MultipartFile file,
            @RequestParam("resourceType") String resourceType,
            @RequestParam(value = "annotation", required = false) String annotationJson,
            @RequestParam(value = "textContent", required = false) String textContent) {
        
        if (userId == null && userIdStr != null) {
            try {
                userId = Long.parseLong(userIdStr);
            } catch (NumberFormatException e) {
                Map<String, Object> result = Map.of("success", false, "message", "无效的用户ID");
                return ResponseEntity.status(401).body(result);
            }
        }
        
        if (userId == null) {
            Map<String, Object> result = Map.of("success", false, "message", "请先登录");
            return ResponseEntity.status(401).body(result);
        }
        
        if (file == null || file.isEmpty()) {
            if (textContent == null || textContent.trim().isEmpty()) {
                Map<String, Object> result = Map.of("success", false, "message", "请选择要上传的文件或输入文本内容");
                return ResponseEntity.badRequest().body(result);
            }
        }
        
        if (resourceType == null || (!resourceType.equals("文本") && !resourceType.equals("图像"))) {
            Map<String, Object> result = Map.of("success", false, "message", "不支持的资源类型：仅支持\"文本\"或\"图像\"");
            return ResponseEntity.badRequest().body(result);
        }
        
        // TODO: 实现资源上传逻辑
        Map<String, Object> result = Map.of("success", true, "message", "资源上传成功", "resource_id", 0);
        return ResponseEntity.ok(result);
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> health() {
        Map<String, Object> result = Map.of(
            "status", "ok",
            "database_status", "connected"
        );
        return ResponseEntity.ok(result);
    }
}

