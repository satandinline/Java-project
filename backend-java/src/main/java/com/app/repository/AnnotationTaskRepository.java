package com.app.repository;

import com.app.entity.AnnotationTask;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface AnnotationTaskRepository extends JpaRepository<AnnotationTask, Long> {
    @Query("SELECT t FROM AnnotationTask t WHERE t.status = :status")
    Page<AnnotationTask> findByStatus(@Param("status") String status, Pageable pageable);
    
    // 使用原生SQL查询，因为涉及多表关联
    @Query(value = "SELECT t.* FROM annotation_tasks t " +
            "INNER JOIN cultural_resources_from_user r ON t.resource_id = r.id " +
            "WHERE t.resource_source = 'cultural_resources_from_user' AND r.user_id = :userId",
            nativeQuery = true,
            countQuery = "SELECT COUNT(*) FROM annotation_tasks t " +
                    "INNER JOIN cultural_resources_from_user r ON t.resource_id = r.id " +
                    "WHERE t.resource_source = 'cultural_resources_from_user' AND r.user_id = :userId")
    Page<AnnotationTask> findByUserId(@Param("userId") Long userId, Pageable pageable);
    
    @Query(value = "SELECT t.* FROM annotation_tasks t " +
            "INNER JOIN cultural_resources_from_user r ON t.resource_id = r.id " +
            "WHERE t.status = :status AND t.resource_source = 'cultural_resources_from_user' AND r.user_id = :userId",
            nativeQuery = true,
            countQuery = "SELECT COUNT(*) FROM annotation_tasks t " +
                    "INNER JOIN cultural_resources_from_user r ON t.resource_id = r.id " +
                    "WHERE t.status = :status AND t.resource_source = 'cultural_resources_from_user' AND r.user_id = :userId")
    Page<AnnotationTask> findByUserIdAndStatus(@Param("userId") Long userId, @Param("status") String status, Pageable pageable);
}

