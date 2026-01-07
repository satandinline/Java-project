package com.app.entity;

import jakarta.persistence.*;
import lombok.Data;
import java.time.LocalDateTime;

@Entity
@Table(name = "cultural_resources")
@Data
public class CulturalResource {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "title", length = 255)
    private String title;

    @Column(name = "resource_type", length = 50)
    private String resourceType;

    @Column(name = "file_format", length = 20)
    private String fileFormat;

    @Column(name = "source_from", length = 255)
    private String sourceFrom;

    @Column(name = "source_url", columnDefinition = "TEXT")
    private String sourceUrl;

    @Column(name = "content_feature_data", columnDefinition = "LONGTEXT")
    private String contentFeatureData;

    @Column(name = "version")
    private Integer version = 1;

    @Column(name = "created_at")
    private LocalDateTime createdAt;

    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    @Column(name = "upload_user_id")
    private Long uploadUserId;

    @Column(name = "ai_review_status", length = 20)
    private String aiReviewStatus = "pending";

    @Column(name = "ai_review_remark", columnDefinition = "TEXT")
    private String aiReviewRemark;

    @Column(name = "manual_review_status", length = 20)
    private String manualReviewStatus = "pending";

    @Column(name = "manual_review_remark", columnDefinition = "TEXT")
    private String manualReviewRemark;

    @Column(name = "upload_time")
    private LocalDateTime uploadTime;
}

