package com.app.service;

import com.app.entity.CommentReply;
import com.app.entity.UserComment;
import com.app.repository.CommentReplyRepository;
import com.app.repository.UserCommentRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Service
public class CommentService {
    @Autowired
    private UserCommentRepository commentRepository;
    
    @Autowired
    private CommentReplyRepository replyRepository;

    public Map<String, Object> getComments(Long resourceId) {
        Map<String, Object> result = new HashMap<>();
        try {
            List<UserComment> comments = commentRepository.findApprovedCommentsByResourceId(
                resourceId, UserComment.CommentStatus.approved);
            
            List<Map<String, Object>> commentList = comments.stream().map(comment -> {
                Map<String, Object> commentMap = new HashMap<>();
                commentMap.put("id", comment.getId());
                commentMap.put("resource_id", comment.getResourceId());
                commentMap.put("user_id", comment.getUserId());
                commentMap.put("comment_content", comment.getCommentContent());
                commentMap.put("created_at", comment.getCreatedAt());
                commentMap.put("like_count", 0); // TODO: 实现点赞数统计
                
                // 获取回复
                List<CommentReply> replies = replyRepository.findByCommentIdOrderByCreatedAtAsc(comment.getId());
                List<Map<String, Object>> replyList = replies.stream().map(reply -> {
                    Map<String, Object> replyMap = new HashMap<>();
                    replyMap.put("id", reply.getId());
                    replyMap.put("comment_id", reply.getCommentId());
                    replyMap.put("reply_user_id", reply.getReplyUserId());
                    replyMap.put("reply_content", reply.getReplyContent());
                    replyMap.put("created_at", reply.getCreatedAt());
                    replyMap.put("like_count", 0); // TODO: 实现点赞数统计
                    return replyMap;
                }).collect(Collectors.toList());
                commentMap.put("replies", replyList);
                
                return commentMap;
            }).collect(Collectors.toList());
            
            result.put("success", true);
            result.put("comments", commentList);
        } catch (Exception e) {
            result.put("success", false);
            result.put("message", "获取评论失败：" + e.getMessage());
        }
        return result;
    }

    @Transactional
    public Map<String, Object> createComment(Long resourceId, Long userId, String commentContent) {
        Map<String, Object> result = new HashMap<>();
        
        if (commentContent == null || commentContent.trim().isEmpty()) {
            result.put("success", false);
            result.put("message", "评论内容不能为空");
            return result;
        }
        
        try {
            UserComment comment = new UserComment();
            comment.setResourceId(resourceId);
            comment.setUserId(userId);
            comment.setCommentContent(commentContent.trim());
            comment.setCommentStatus(UserComment.CommentStatus.approved);
            comment.setCreatedAt(LocalDateTime.now());
            comment.setUpdatedAt(LocalDateTime.now());
            
            comment = commentRepository.save(comment);
            
            Map<String, Object> commentMap = new HashMap<>();
            commentMap.put("id", comment.getId());
            commentMap.put("resource_id", comment.getResourceId());
            commentMap.put("user_id", comment.getUserId());
            commentMap.put("comment_content", comment.getCommentContent());
            commentMap.put("created_at", comment.getCreatedAt());
            commentMap.put("like_count", 0);
            commentMap.put("replies", List.of());
            
            result.put("success", true);
            result.put("comment", commentMap);
            result.put("message", "评论发布成功");
        } catch (Exception e) {
            result.put("success", false);
            result.put("message", "创建评论失败：" + e.getMessage());
        }
        
        return result;
    }

    @Transactional
    public Map<String, Object> addReply(Long commentId, Long userId, String replyContent) {
        Map<String, Object> result = new HashMap<>();
        
        if (replyContent == null || replyContent.trim().isEmpty()) {
            result.put("success", false);
            result.put("message", "回复内容不能为空");
            return result;
        }
        
        try {
            CommentReply reply = new CommentReply();
            reply.setCommentId(commentId);
            reply.setReplyUserId(userId);
            reply.setReplyContent(replyContent.trim());
            reply.setCreatedAt(LocalDateTime.now());
            
            reply = replyRepository.save(reply);
            
            Map<String, Object> replyMap = new HashMap<>();
            replyMap.put("id", reply.getId());
            replyMap.put("comment_id", reply.getCommentId());
            replyMap.put("reply_user_id", reply.getReplyUserId());
            replyMap.put("reply_content", reply.getReplyContent());
            replyMap.put("created_at", reply.getCreatedAt());
            replyMap.put("like_count", 0);
            
            result.put("success", true);
            result.put("reply", replyMap);
            result.put("message", "回复添加成功");
        } catch (Exception e) {
            result.put("success", false);
            result.put("message", "添加回复失败：" + e.getMessage());
        }
        
        return result;
    }
}

