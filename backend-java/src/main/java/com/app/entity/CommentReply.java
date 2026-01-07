package com.app.entity;

import jakarta.persistence.*;
import lombok.Data;
import java.time.LocalDateTime;

@Entity
@Table(name = "comment_replies")
@Data
public class CommentReply {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "comment_id", nullable = false)
    private Long commentId;

    @Column(name = "reply_user_id", nullable = false)
    private Long replyUserId;

    @Column(name = "reply_content", columnDefinition = "TEXT", nullable = false)
    private String replyContent;

    @Column(name = "created_at")
    private LocalDateTime createdAt;
}

