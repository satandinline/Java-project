package com.cultural.controller;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * 文件上传控制器
 * 
 * 【注意】此控制器当前未被前端使用，且实现不完整（只有TODO注释）。
 * 前端通过vite代理将所有 /api 请求转发到 http://localhost:7200（Python后端）。
 * 实际使用的上传API在 Python 后端（AIGC/aigc_api_server.py）中实现，功能完整。
 * 
 * 此控制器保留用于：
 * 1. 未来可能的Java后端迁移
 * 2. 直接访问Java后端的场景（不通过前端代理）
 * 
 * 【待实现】需要完成以下功能：
 * - 保存到数据库
 * - 创建标注任务
 * - 文件类型验证
 * - 文件大小限制
 */
@RestController
@RequestMapping("/api")
public class UploadController {

    @Value("${file.upload.path:./uploads}")
    private String uploadPath;

    /**
     * 文件上传接口
     * POST /api/upload
     */
    @PostMapping("/upload")
    public ResponseEntity<Map<String, Object>> uploadFile(
            @RequestParam("file") MultipartFile file,
            @RequestParam("resourceType") String resourceType,
            @RequestParam("userId") Long userId) {
        
        Map<String, Object> result = new HashMap<>();
        
        if (file.isEmpty()) {
            result.put("success", false);
            result.put("message", "文件不能为空");
            return ResponseEntity.badRequest().body(result);
        }
        
        try {
            // 确保上传目录存在
            Path uploadDir = Paths.get(uploadPath);
            if (!Files.exists(uploadDir)) {
                Files.createDirectories(uploadDir);
            }
            
            // 生成唯一文件名
            String originalFilename = file.getOriginalFilename();
            String fileExtension = "";
            if (originalFilename != null && originalFilename.contains(".")) {
                fileExtension = originalFilename.substring(originalFilename.lastIndexOf("."));
            }
            
            String uniqueFilename = "unknown-" + 
                LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd-HH-mm-ss")) +
                fileExtension;
            
            // 保存文件
            Path filePath = uploadDir.resolve(uniqueFilename);
            file.transferTo(filePath.toFile());
            
            // TODO: 保存到数据库、创建标注任务等
            // 这里需要实现完整的业务逻辑
            
            result.put("success", true);
            result.put("message", "文件上传成功");
            result.put("filename", uniqueFilename);
            
            return ResponseEntity.ok(result);
            
        } catch (IOException e) {
            result.put("success", false);
            result.put("message", "文件上传失败：" + e.getMessage());
            return ResponseEntity.status(500).body(result);
        }
    }
}

