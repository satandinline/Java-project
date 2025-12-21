package com.cultural.entity;

import lombok.Data;
import java.time.LocalDateTime;

/**
 * 文化资源实体类
 */
@Data
public class CulturalResource {
    private Long id;
    private String title;
    private String resourceType;
    private String fileFormat;
    private String sourceFrom;
    private String sourceUrl;
    private String contentFeatureData;
    private Integer version;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
    private Long uploadUserId;
    private String aiReviewStatus;
    private String aiReviewRemark;
    private String manualReviewStatus;
    private String manualReviewRemark;
    private LocalDateTime uploadTime;
}

