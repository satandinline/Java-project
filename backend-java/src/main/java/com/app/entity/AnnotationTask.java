package com.app.entity;

import jakarta.persistence.*;
import lombok.Data;
import java.time.LocalDateTime;

@Entity
@Table(name = "annotation_tasks")
@Data
public class AnnotationTask {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "resource_id", nullable = false)
    private Long resourceId;

    @Column(name = "resource_source", length = 50, nullable = false)
    private String resourceSource;

    @Column(name = "task_type", length = 50)
    private String taskType;

    @Column(name = "status", length = 50)
    private String status;

    @Column(name = "annotation_method", length = 50)
    private String annotationMethod;

    @Column(name = "created_at")
    private LocalDateTime createdAt;

    @Column(name = "updated_at")
    private LocalDateTime updatedAt;
}

