package com.app.controller;

import com.app.service.CommentService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/comments")
public class CommentController {
    @Autowired
    private CommentService commentService;

    @GetMapping
    public ResponseEntity<Map<String, Object>> getComments(@RequestParam("resource_id") Long resourceId) {
        if (resourceId == null) {
            Map<String, Object> result = Map.of("success", false, "message", "缺少resource_id参数");
            return ResponseEntity.badRequest().body(result);
        }
        
        Map<String, Object> result = commentService.getComments(resourceId);
        return ResponseEntity.ok(result);
    }

    @PostMapping
    public ResponseEntity<Map<String, Object>> createComment(@RequestBody Map<String, Object> request) {
        Long resourceId = request.get("resource_id") != null ? 
            Long.parseLong(request.get("resource_id").toString()) : null;
        Long userId = request.get("user_id") != null ? 
            Long.parseLong(request.get("user_id").toString()) : null;
        String commentContent = request.get("comment_content") != null ? 
            request.get("comment_content").toString() : null;
        
        if (resourceId == null || userId == null || commentContent == null) {
            Map<String, Object> result = Map.of("success", false, "message", "缺少必要参数");
            return ResponseEntity.badRequest().body(result);
        }
        
        Map<String, Object> result = commentService.createComment(resourceId, userId, commentContent);
        return ResponseEntity.ok(result);
    }

    @PostMapping("/{commentId}/reply")
    public ResponseEntity<Map<String, Object>> addReply(
            @PathVariable Long commentId,
            @RequestBody Map<String, Object> request) {
        Long userId = request.get("user_id") != null ? 
            Long.parseLong(request.get("user_id").toString()) : null;
        String replyContent = request.get("reply_content") != null ? 
            request.get("reply_content").toString() : null;
        
        if (userId == null || replyContent == null) {
            Map<String, Object> result = Map.of("success", false, "message", "缺少必要参数");
            return ResponseEntity.badRequest().body(result);
        }
        
        Map<String, Object> result = commentService.addReply(commentId, userId, replyContent);
        return ResponseEntity.ok(result);
    }

    @PostMapping("/{commentId}/like")
    public ResponseEntity<Map<String, Object>> likeComment(
            @PathVariable Long commentId,
            @RequestBody Map<String, Object> request) {
        // TODO: 实现点赞功能
        Map<String, Object> result = Map.of("success", true, "action", "liked", "like_count", 0);
        return ResponseEntity.ok(result);
    }
}

