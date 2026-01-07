package com.app.entity;

import jakarta.persistence.*;
import lombok.Data;
import java.time.LocalDateTime;

@Entity
@Table(name = "user_comments")
@Data
public class UserComment {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "resource_id", nullable = false)
    private Long resourceId;

    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Column(name = "comment_content", columnDefinition = "TEXT", nullable = false)
    private String commentContent;

    @Enumerated(EnumType.STRING)
    @Column(name = "comment_status", length = 20)
    private CommentStatus commentStatus = CommentStatus.approved;

    @Column(name = "is_academic_discussion")
    private Boolean isAcademicDiscussion = false;

    @Column(name = "created_at")
    private LocalDateTime createdAt;

    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    public enum CommentStatus {
        approved, pending, rejected
    }
}

