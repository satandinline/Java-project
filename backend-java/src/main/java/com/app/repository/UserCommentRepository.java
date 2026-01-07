package com.app.repository;

import com.app.entity.UserComment;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface UserCommentRepository extends JpaRepository<UserComment, Long> {
    List<UserComment> findByResourceIdAndCommentStatus(Long resourceId, UserComment.CommentStatus status);
    
    Page<UserComment> findByUserId(Long userId, Pageable pageable);
    
    @Query("SELECT c FROM UserComment c WHERE c.resourceId = :resourceId AND c.commentStatus = :status ORDER BY c.createdAt DESC")
    List<UserComment> findApprovedCommentsByResourceId(@Param("resourceId") Long resourceId, @Param("status") UserComment.CommentStatus status);
}

