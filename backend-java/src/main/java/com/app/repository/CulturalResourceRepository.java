package com.app.repository;

import com.app.entity.CulturalResource;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface CulturalResourceRepository extends JpaRepository<CulturalResource, Long> {
    Page<CulturalResource> findByResourceType(String resourceType, Pageable pageable);
    
    @Query("SELECT cr FROM CulturalResource cr WHERE cr.title LIKE %:keyword% OR cr.contentFeatureData LIKE %:keyword%")
    Page<CulturalResource> searchByKeyword(@Param("keyword") String keyword, Pageable pageable);
}

