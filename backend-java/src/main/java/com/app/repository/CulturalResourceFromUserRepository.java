package com.app.repository;

import com.app.entity.CulturalResourceFromUser;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface CulturalResourceFromUserRepository extends JpaRepository<CulturalResourceFromUser, Long> {
}

