package com.app.entity;

import jakarta.persistence.*;
import lombok.Data;
import java.time.LocalDateTime;

@Entity
@Table(name = "cultural_resources_from_user")
@Data
public class CulturalResourceFromUser {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Column(name = "title", length = 255)
    private String title;

    @Column(name = "resource_type", length = 50)
    private String resourceType;

    @Column(name = "file_format", length = 20)
    private String fileFormat;

    @Column(name = "content_feature_data", columnDefinition = "LONGTEXT")
    private String contentFeatureData;

    @Column(name = "content_hash", length = 255)
    private String contentHash;

    @Column(name = "storage_path", length = 500)
    private String storagePath;

    @Column(name = "upload_time")
    private LocalDateTime uploadTime;

    @Column(name = "ai_review_status", length = 20)
    private String aiReviewStatus = "pending";

    @Column(name = "manual_review_status", length = 20)
    private String manualReviewStatus = "pending";
}

